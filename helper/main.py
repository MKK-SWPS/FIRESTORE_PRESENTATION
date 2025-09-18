"""
Windows Desktop Helper for Student Tap System

This module orchestrates:
- Global hotkey registration (Ctrl+B)
- Screen capture and upload to Firebase Storage
- Firestore document updates for session state
- Real-time monitoring of student tap responses
- Overlay window management for displaying tap dots

Requirements:
- Windows only
- Python 3.11+
- Service account JSON file for Firebase Admin SDK
- config.json with session and Firebase settings
"""

# Version info for compiled executable
try:
    from version_info import VERSION_INFO
except ImportError:
    VERSION_INFO = {
        'version': 'dev',
        'build_date': 'unknown',
        'commit': 'unknown',
        'branch': 'unknown'
    }

import json
import os
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
import logging

# Windows-specific imports
import win32gui
import win32con
import win32api
from ctypes import windll, wintypes, c_int, byref

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.firestore_v1 import ArrayUnion, SERVER_TIMESTAMP

# Screenshot and monitor detection
import mss
import screeninfo

# Qt for overlay window
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QThread, Signal
from PySide6.QtGui import QPixmap

# Local imports
from overlay import OverlayWindow

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FirestoreWatcher(QThread):
    """Thread to watch Firestore changes without blocking the main thread."""
    
    session_changed = Signal(dict)
    new_response = Signal(dict, int)  # response_data, slide_index
    
    def __init__(self, db, session_id):
        super().__init__()
        self.db = db
        self.session_id = session_id
        self.current_slide_index = -1
        self.responses_listener = None
        self._stop_event = threading.Event()
        
    def run(self):
        """Start watching Firestore documents."""
        try:
            # Watch session document
            session_ref = self.db.collection('sessions').document(self.session_id)
            session_listener = session_ref.on_snapshot(self._on_session_snapshot)
            
            # Keep thread alive
            while not self._stop_event.wait(0.1):
                pass
                
        except Exception as e:
            logger.error(f"Firestore watcher error: {e}")
    
    def _on_session_snapshot(self, doc_snapshot, changes, read_time):
        """Handle session document changes."""
        for doc in doc_snapshot:
            if doc.exists:
                data = doc.to_dict()
                self.session_changed.emit(data)
                
                # Update responses listener if slide index changed
                new_slide_index = data.get('slideIndex', 0)
                if new_slide_index != self.current_slide_index:
                    self._update_responses_listener(new_slide_index)
    
    def _update_responses_listener(self, slide_index):
        """Update the responses listener for the current slide."""
        try:
            # Stop previous listener
            if self.responses_listener:
                self.responses_listener.unsubscribe()
                self.responses_listener = None
            
            # Start new listener for current slide
            self.current_slide_index = slide_index
            responses_ref = (self.db.collection('sessions')
                           .document(self.session_id)
                           .collection('slides')
                           .document(str(slide_index))
                           .collection('responses'))
            
            self.responses_listener = responses_ref.on_snapshot(self._on_responses_snapshot)
            logger.info(f"Started watching responses for slide {slide_index}")
            
        except Exception as e:
            logger.error(f"Error updating responses listener: {e}")
    
    def _on_responses_snapshot(self, doc_snapshot, changes, read_time):
        """Handle new tap responses."""
        for change in changes:
            if change.type.name == 'ADDED':  # New response
                response_data = change.document.to_dict()
                self.new_response.emit(response_data, self.current_slide_index)
    
    def stop(self):
        """Stop the watcher thread."""
        self._stop_event.set()
        if self.responses_listener:
            self.responses_listener.unsubscribe()


class HotkeyManager:
    """Manages Windows global hotkeys using RegisterHotKey."""
    
    # Virtual key codes
    VK_B = 0x42
    MOD_CONTROL = 0x0002
    WM_HOTKEY = 0x0312
    
    def __init__(self):
        self.hotkey_id = 1
        self.callback = None
        self.hwnd = None
        self._setup_message_window()
    
    def _setup_message_window(self):
        """Create a hidden window to receive hotkey messages."""
        # Create a simple window class
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = self._wnd_proc
        wc.lpszClassName = "HotkeyManagerWindow"
        wc.hInstance = win32gui.GetModuleHandle(None)
        
        class_atom = win32gui.RegisterClass(wc)
        
        # Create the window
        self.hwnd = win32gui.CreateWindow(
            class_atom, "Hotkey Manager", 0, 0, 0, 0, 0,
            None, None, win32gui.GetModuleHandle(None), None
        )
    
    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """Window procedure to handle messages."""
        if msg == self.WM_HOTKEY:
            if self.callback:
                self.callback()
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
    
    def register_hotkey(self, callback, key=None, modifiers=None):
        """Register a global hotkey."""
        if key is None:
            key = self.VK_B
        if modifiers is None:
            modifiers = self.MOD_CONTROL
            
        self.callback = callback
        
        if not windll.user32.RegisterHotKeyW(self.hwnd, self.hotkey_id, modifiers, key):
            raise Exception(f"Failed to register hotkey. Error: {win32api.GetLastError()}")
        
        logger.info(f"Registered global hotkey: Ctrl+B")
    
    def unregister_hotkey(self):
        """Unregister the hotkey."""
        if self.hwnd:
            windll.user32.UnregisterHotKeyW(self.hwnd, self.hotkey_id)


class DesktopHelper:
    """Main application class coordinating all components."""
    
    def __init__(self, config_path='config.json'):
        self.config = self._load_config(config_path)
        self.app = QApplication(sys.argv)
        
        # Firebase setup
        self.db = None
        self.bucket = None
        self._init_firebase()
        
        # Components
        self.overlay = None
        self.hotkey_manager = HotkeyManager()
        self.firestore_watcher = None
        
        # State
        self.monitors = screeninfo.get_monitors()
        self.current_session = {}
        self.current_slide_index = -1
        
    def _load_config(self, config_path):
        """Load configuration from JSON file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Validate required fields
        required_fields = ['session_id', 'service_account_path', 'storage_bucket', 'monitor_index']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")
        
        return config
    
    def _init_firebase(self):
        """Initialize Firebase Admin SDK."""
        try:
            # Initialize with service account
            cred = credentials.Certificate(self.config['service_account_path'])
            firebase_admin.initialize_app(cred, {
                'storageBucket': self.config['storage_bucket']
            })
            
            # Get Firestore and Storage clients
            self.db = firestore.client()
            self.bucket = storage.bucket()
            
            logger.info("Firebase Admin SDK initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            raise
    
    def _get_monitor_info(self):
        """Get information about the target monitor."""
        monitor_index = self.config.get('monitor_index', 0)
        
        if monitor_index >= len(self.monitors):
            logger.warning(f"Monitor index {monitor_index} not found, using primary monitor")
            monitor_index = 0
        
        monitor = self.monitors[monitor_index]
        logger.info(f"Using monitor {monitor_index}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
        
        return monitor, monitor_index
    
    def _capture_screenshot(self):
        """Capture screenshot of the target monitor."""
        monitor, monitor_index = self._get_monitor_info()
        
        with mss.mss() as sct:
            # mss monitor indexing: 0=all monitors, 1=first monitor, etc.
            # screeninfo indexing: 0=first monitor, 1=second monitor, etc.
            mss_monitor_index = monitor_index + 1
            
            if mss_monitor_index >= len(sct.monitors):
                logger.error(f"MSS monitor index {mss_monitor_index} out of range")
                return None, None
            
            # Capture the screen
            screenshot = sct.grab(sct.monitors[mss_monitor_index])
            
            # Convert to PIL Image for saving
            from PIL import Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "BGRX")
            
            return img, monitor
    
    def _upload_screenshot(self, img, monitor):
        """Upload screenshot to Firebase Storage and return download URL."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # millisecond precision
            filename = f"{timestamp}.jpg"
            blob_path = f"sessions/{self.config['session_id']}/slides/{filename}"
            
            # Save image to temporary bytes
            from io import BytesIO
            img_bytes = BytesIO()
            img.save(img_bytes, format='JPEG', quality=85)
            img_bytes.seek(0)
            
            # Upload to Storage
            blob = self.bucket.blob(blob_path)
            blob.upload_from_file(img_bytes, content_type='image/jpeg')
            
            # Get download URL
            blob.make_public()
            download_url = blob.public_url
            
            logger.info(f"Screenshot uploaded: {blob_path}")
            return download_url, {
                'width': monitor.width,
                'height': monitor.height,
                'monitorIndex': self.config['monitor_index']
            }
            
        except Exception as e:
            logger.error(f"Failed to upload screenshot: {e}")
            return None, None
    
    def _update_session_document(self, image_url, screenshot_meta):
        """Update Firestore session document with new slide."""
        try:
            session_ref = self.db.collection('sessions').document(self.config['session_id'])
            
            # Get current session to determine new slide index
            doc = session_ref.get()
            if doc.exists:
                current_slides = doc.to_dict().get('slides', [])
                new_slide_index = len(current_slides)
            else:
                current_slides = []
                new_slide_index = 0
            
            # Update document
            session_ref.set({
                'slides': ArrayUnion([image_url]),
                'slideIndex': new_slide_index,
                'screenshotMeta': screenshot_meta,
                'lastUpdated': SERVER_TIMESTAMP
            }, merge=True)
            
            logger.info(f"Session updated: slide {new_slide_index + 1}")
            return new_slide_index
            
        except Exception as e:
            logger.error(f"Failed to update session document: {e}")
            return None
    
    def _on_hotkey_pressed(self):
        """Handle Ctrl+B hotkey press."""
        logger.info("Hotkey pressed - capturing screenshot")
        
        try:
            # Clear overlay dots immediately
            if self.overlay:
                self.overlay.clear_dots()
            
            # Capture screenshot
            img, monitor = self._capture_screenshot()
            if img is None:
                logger.error("Failed to capture screenshot")
                return
            
            # Upload to Firebase
            image_url, screenshot_meta = self._upload_screenshot(img, monitor)
            if image_url is None:
                logger.error("Failed to upload screenshot")
                return
            
            # Update Firestore
            new_slide_index = self._update_session_document(image_url, screenshot_meta)
            if new_slide_index is not None:
                self.current_slide_index = new_slide_index
                logger.info(f"Successfully created slide {new_slide_index + 1}")
            
        except Exception as e:
            logger.error(f"Error processing hotkey: {e}")
    
    def _on_session_changed(self, session_data):
        """Handle session document changes from Firestore."""
        self.current_session = session_data
        
        slide_index = session_data.get('slideIndex', 0)
        slides = session_data.get('slides', [])
        
        logger.info(f"Session updated: slide {slide_index + 1}/{len(slides)}")
        
        # If slide index changed away from our current overlay, clear dots
        if slide_index != self.current_slide_index and self.overlay:
            self.overlay.clear_dots()
            logger.info("Cleared overlay dots due to slide change")
    
    def _on_new_response(self, response_data, slide_index):
        """Handle new tap responses from students."""
        if slide_index != self.current_slide_index:
            # Response is for a different slide, ignore
            return
        
        # Get normalized coordinates
        x = response_data.get('x', 0)
        y = response_data.get('y', 0)
        
        # Convert to absolute coordinates based on current monitor
        monitor, _ = self._get_monitor_info()
        abs_x = int(x * monitor.width) + monitor.x
        abs_y = int(y * monitor.height) + monitor.y
        
        # Add dot to overlay
        if self.overlay:
            self.overlay.add_dot(abs_x, abs_y)
        
        logger.debug(f"Added dot at ({abs_x}, {abs_y}) from normalized ({x:.3f}, {y:.3f})")
    
    def _setup_overlay(self):
        """Create and show the overlay window."""
        monitor, monitor_index = self._get_monitor_info()
        
        self.overlay = OverlayWindow(
            monitor.x, monitor.y, monitor.width, monitor.height,
            self.config.get('dot_color', '#8E4EC6'),
            self.config.get('dot_radius_px', 8),
            self.config.get('fade_ms', 10000)
        )
        
        self.overlay.show()
        logger.info(f"Overlay window created on monitor {monitor_index}")
    
    def _setup_firestore_watcher(self):
        """Setup Firestore document watchers."""
        self.firestore_watcher = FirestoreWatcher(self.db, self.config['session_id'])
        
        # Connect signals
        self.firestore_watcher.session_changed.connect(self._on_session_changed)
        self.firestore_watcher.new_response.connect(self._on_new_response)
        
        # Start watching
        self.firestore_watcher.start()
        logger.info("Started Firestore watchers")
    
    def run(self):
        """Start the desktop helper application."""
        try:
            logger.info("Starting Desktop Helper...")
            logger.info(f"Version: {VERSION_INFO.get('version', 'unknown')}")
            logger.info(f"Session ID: {self.config['session_id']}")
            logger.info(f"Monitor: {self.config['monitor_index']}")
            
            # Setup components
            self._setup_overlay()
            self._setup_firestore_watcher()
            
            # Register hotkey
            self.hotkey_manager.register_hotkey(self._on_hotkey_pressed)
            logger.info("Press Ctrl+B to capture screenshot")
            
            # Create a timer to handle Windows messages for hotkeys
            self.message_timer = QTimer()
            self.message_timer.timeout.connect(self._pump_messages)
            self.message_timer.start(10)  # Check every 10ms
            
            # Start Qt event loop
            return self.app.exec()
            
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            return 0
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            return 1
        finally:
            self._cleanup()
    
    def _pump_messages(self):
        """Pump Windows messages in a thread-safe way."""        
        try:
            # This needs to be called from the main thread
            import win32gui
            import ctypes
            from ctypes import wintypes
            
            msg = wintypes.MSG()
            bRet = ctypes.windll.user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1)  # PM_REMOVE
            if bRet != 0:  # Message available
                ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
                ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as e:
            # Don't spam the logs with message pump errors
            pass
    
    def _cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")
        
        # Stop message timer
        if hasattr(self, 'message_timer') and self.message_timer:
            self.message_timer.stop()
        
        if self.hotkey_manager:
            self.hotkey_manager.unregister_hotkey()
        
        if self.firestore_watcher:
            self.firestore_watcher.stop()
            self.firestore_watcher.wait(5000)  # Wait up to 5 seconds
        
        if self.overlay:
            self.overlay.close()


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        config_path = sys.argv[1]
    else:
        config_path = 'config.json'
    
    try:
        helper = DesktopHelper(config_path)
        return helper.run()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Please create a config.json file. See config.example.json for reference.")
        return 1
    except Exception as e:
        print(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())