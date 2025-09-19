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
import platform
from datetime import datetime
from pathlib import Path
import logging

# Windows-specific imports (only on Windows)
HAS_WIN32 = False
if platform.system() == "Windows":
    try:
        import win32gui
        import win32con
        import win32api
        from ctypes import windll, wintypes, c_int, c_bool, byref
        HAS_WIN32 = True
    except ImportError:
        print("Warning: Windows API modules not available")
        HAS_WIN32 = False

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
# Overlay classes are imported lazily inside _setup_overlay to allow platform-specific selection
from alternative_triggers import ScreenshotHTTPServer, FileWatcherTrigger

# Configure logging
def setup_logging(debug: bool = False):
    """Configure logging to file with continuous flushing.

    When frozen (PyInstaller), place logs next to the executable in a 'logs' folder.
    When running from source, place logs relative to this file as before.
    """
    try:
        if getattr(sys, 'frozen', False):  # Running as bundled exe
            base_dir = Path(sys.executable).parent
        else:
            base_dir = Path(__file__).parent
        log_dir = base_dir / 'logs'
        log_dir.mkdir(exist_ok=True)
    except Exception:
        # Fallback to current working directory
        log_dir = Path.cwd() / 'logs'
        log_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = log_dir / f'slide_tap_helper_{timestamp}.log'

    log_format = '%(asctime)s - %(levelname)s - %(message)s'

    class FlushFileHandler(logging.FileHandler):
        def emit(self, record):
            super().emit(record)
            try:
                self.flush()
            except Exception:
                pass

    file_handler = FlushFileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)

    # Mirror latest file info (avoid symlink for Windows)
    try:
        latest_log = log_dir / 'latest.log'
        with open(latest_log, 'w', encoding='utf-8') as f:
            f.write(f"Current log file: {log_file.name}\n")
            f.write(f"Full path: {log_file.absolute()}\n")
            f.write(f"Running frozen: {getattr(sys,'frozen',False)}\n")
    except Exception:
        pass

    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info(f"Log file created: {log_file.absolute()}")
    logger.info(f"Logs directory: {log_dir.absolute()}")
    logger.info(f"Frozen mode: {getattr(sys,'frozen',False)} executable={getattr(sys,'executable',None)}")
    logger.info("=" * 60)
    logger.debug("First flush test entry - if you see this promptly, flushing works.")
    return logger

# Initialize logger (will be replaced in main)
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
        self.hotkey_registered = False
        self._setup_message_window()
    
    def _setup_message_window(self):
        """Create a hidden window to receive hotkey messages."""
        try:
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
            logger.info(f"Created message window for hotkeys: HWND={self.hwnd}")
        except Exception as e:
            logger.error(f"Failed to create message window: {e}")
            self.hwnd = None
    
    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        """Window procedure to handle messages."""
        if msg == self.WM_HOTKEY:
            if self.callback:
                self.callback()
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
    
    def register_hotkey(self, callback, key=None, modifiers=None):
        """Register a global hotkey."""
        if not self.hwnd:
            logger.error("Cannot register hotkey: no message window")
            return False
            
        if key is None:
            key = self.VK_B
        if modifiers is None:
            modifiers = self.MOD_CONTROL
            
        self.callback = callback
        
        try:
            # Try different approaches for Windows API
            import ctypes
            from ctypes import wintypes
            
            # Method 1: Direct RegisterHotKey (most compatible)
            try:
                user32 = ctypes.windll.user32
                result = user32.RegisterHotKeyW(
                    ctypes.wintypes.HWND(self.hwnd),
                    ctypes.c_int(self.hotkey_id),
                    ctypes.c_uint(modifiers),
                    ctypes.c_uint(key)
                )
                
                if result:
                    self.hotkey_registered = True
                    logger.info(f"Successfully registered global hotkey: Ctrl+B (Method 1)")
                    return True
                else:
                    error_code = user32.GetLastError()
                    logger.warning(f"Method 1 failed with error {error_code}, trying Method 2...")
            except Exception as e1:
                logger.warning(f"Method 1 exception: {e1}, trying Method 2...")
            
            # Method 2: Using win32api if available
            try:
                import win32api
                import win32con
                
                result = win32api.RegisterHotKey(
                    self.hwnd,
                    self.hotkey_id, 
                    modifiers,
                    key
                )
                
                if result:
                    self.hotkey_registered = True
                    logger.info(f"Successfully registered global hotkey: Ctrl+B (Method 2)")
                    return True
                else:
                    logger.warning("Method 2 also failed, trying alternative keys...")
            except Exception as e2:
                logger.warning(f"Method 2 exception: {e2}")
            
            # Method 3: Try alternative key combinations
            alternative_keys = [
                (self.MOD_CONTROL, 0x43),  # Ctrl+C (if available)
                (self.MOD_CONTROL, 0x53),  # Ctrl+S (if available) 
                (self.MOD_CONTROL, 0x50),  # Ctrl+P (if available)
                (0x0001 | 0x0002, self.VK_B),  # Alt+Ctrl+B
            ]
            
            for alt_mod, alt_key in alternative_keys:
                try:
                    result = user32.RegisterHotKeyW(
                        ctypes.wintypes.HWND(self.hwnd),
                        ctypes.c_int(self.hotkey_id + 1),  # Different ID
                        ctypes.c_uint(alt_mod),
                        ctypes.c_uint(alt_key)
                    )
                    
                    if result:
                        self.hotkey_id += 1  # Update to the working ID
                        self.hotkey_registered = True
                        key_name = f"Alternative hotkey (mod:{alt_mod}, key:{alt_key})"
                        logger.info(f"Successfully registered {key_name}")
                        return True
                except Exception as e3:
                    continue
            
            logger.error("All hotkey registration methods failed")
            return False
            
        except Exception as e:
            logger.error(f"Fatal exception in hotkey registration: {e}")
            return False
    
    def unregister_hotkey(self):
        """Unregister the hotkey."""
        if self.hwnd and self.hotkey_registered:
            try:
                from ctypes import windll
                windll.user32.UnregisterHotKeyW(self.hwnd, self.hotkey_id)
                self.hotkey_registered = False
                logger.info("Hotkey unregistered successfully")
            except Exception as e:
                logger.error(f"Error unregistering hotkey: {e}")


class DesktopHelper:
    """Main application class coordinating all components."""
    
    def __init__(self, config_path='config.json'):
        self.config = self._load_config(config_path)
        # Track startup time to ignore stale Firestore responses
        self.start_time = time.time()
        self.app = QApplication(sys.argv)
        
        # Firebase setup
        self.db = None
        self.bucket = None
        self._init_firebase()
        
        # Components
        self.overlay = None
        self.hotkey_manager = HotkeyManager()
        self.firestore_watcher = None
        
        # Alternative triggers
        self.http_server = None
        self.file_watcher = None
        
        # State
        self.monitors = screeninfo.get_monitors()
        self.current_session = {}
        self.current_slide_index = -1
        
    def _load_config(self, config_path):
        """Load configuration from JSON file."""
        # Check if custom config exists, otherwise use example
        if not os.path.exists(config_path):
            if config_path == 'config.json' and os.path.exists('config.example.json'):
                logger.warning("config.json not found, using config.example.json template")
                logger.warning("Please copy config.example.json to config.json and update with your Firebase details")
                config_path = 'config.example.json'
            else:
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
        """Get information about the target monitor with auto-detection."""
        monitor_index = self.config.get('monitor_index', 'auto')
        
        if monitor_index == 'auto':
            # Auto-detect: prefer primary monitor, or if no primary, use the largest one
            primary_monitor = None
            largest_monitor = None
            largest_area = 0
            
            for i, mon in enumerate(self.monitors):
                area = mon.width * mon.height
                if area > largest_area:
                    largest_area = area
                    largest_monitor = (mon, i)
                
                # screeninfo sometimes marks primary with is_primary attribute
                if hasattr(mon, 'is_primary') and mon.is_primary:
                    primary_monitor = (mon, i)
                # Also check if monitor is at origin (0,0) which usually indicates primary
                elif mon.x == 0 and mon.y == 0:
                    primary_monitor = (mon, i)
            
            if primary_monitor:
                monitor, monitor_index = primary_monitor
                logger.info(f"Auto-detected primary monitor {monitor_index}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
            elif largest_monitor:
                monitor, monitor_index = largest_monitor
                logger.info(f"Auto-detected largest monitor {monitor_index}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
            else:
                monitor, monitor_index = self.monitors[0], 0
                logger.info(f"Fallback to first monitor {monitor_index}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
        else:
            # Manual monitor index specified
            if monitor_index >= len(self.monitors):
                logger.warning(f"Monitor index {monitor_index} not found, using primary monitor")
                monitor_index = 0
            
            monitor = self.monitors[monitor_index]
            logger.info(f"Using specified monitor {monitor_index}: {monitor.width}x{monitor.height} at ({monitor.x}, {monitor.y})")
        
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
            
            try:
                # Method 1: Try direct BGRX conversion
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "BGRX")
                logger.info("✅ Screenshot captured using BGRX method")
            except (ValueError, OSError) as e:
                logger.warning(f"BGRX conversion failed ({e}), trying manual method...")
                try:
                    # Method 2: Manual BGRA to RGB conversion (no numpy needed)
                    bgra_data = screenshot.bgra
                    rgb_data = bytearray()
                    
                    # Convert BGRA to RGB manually
                    for i in range(0, len(bgra_data), 4):
                        b, g, r, a = bgra_data[i:i+4]
                        rgb_data.extend([r, g, b])  # RGB, skip alpha
                    
                    img = Image.frombytes("RGB", screenshot.size, bytes(rgb_data))
                    logger.info("✅ Screenshot captured using manual conversion")
                except Exception as e2:
                    logger.error(f"Manual conversion failed ({e2}), trying raw method...")
                    try:
                        # Method 3: Try different PIL modes
                        img = Image.frombytes("RGBA", screenshot.size, screenshot.bgra)
                        img = img.convert("RGB")  # Convert RGBA to RGB
                        logger.info("✅ Screenshot captured using RGBA conversion")
                    except Exception as e3:
                        logger.error(f"All conversion methods failed: {e3}")
                        return None, None
            
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
        
        logger.info(f"📊 Session updated: slide {slide_index + 1}/{len(slides)}")
        logger.info(f"🎯 Setting current_slide_index to: {slide_index}")
        
        # If slide index changed away from our current overlay, clear dots
        if slide_index != self.current_slide_index and self.overlay:
            self.overlay.clear_dots()
            logger.info("🧹 Cleared overlay dots due to slide change")
        
        # Update current slide index
        self.current_slide_index = slide_index
    
    def _on_new_response(self, response_data, slide_index):
        """Handle new tap responses from students."""
        logger.info(f"🔍 New response received: slide_index={slide_index}, current_slide_index={self.current_slide_index}")
        logger.info(f"🎯 Response data: {response_data}")

        # Ignore stale responses from before startup (replay noise)
        ignore_seconds = self.config.get('ignore_past_responses_seconds', 0)
        if ignore_seconds > 0:
            ts = response_data.get('timestamp')
            try:
                if hasattr(ts, 'timestamp'):
                    ts_val = ts.timestamp()
                elif isinstance(ts, (int, float)):
                    ts_val = float(ts)
                else:
                    ts_val = None
                if ts_val and ts_val < (self.start_time - ignore_seconds):
                    logger.info(f"🚫 Ignoring old response from {int(self.start_time - ts_val)} seconds before app start")
                    return
            except Exception:
                pass
        
        if slide_index != self.current_slide_index:
            # Response is for a different slide, ignore
            logger.warning(f"⚠️ Response ignored - slide mismatch (response:{slide_index} vs current:{self.current_slide_index})")
            return
        
        # Get normalized coordinates
        x = response_data.get('x', 0)
        y = response_data.get('y', 0)
        
        logger.info(f"📐 Normalized coordinates: x={x:.3f}, y={y:.3f}")
        
        # Get monitor info - use PHYSICAL dimensions for coordinate mapping
        monitor, _ = self._get_monitor_info()
        
        # Convert normalized coordinates (0-1) to physical monitor pixels
        # This should be independent of Windows DPI scaling or Qt logical pixels
        physical_x = int(x * monitor.width)
        physical_y = int(y * monitor.height)
        logger.info(f"🖥️ Physical monitor coordinates: ({physical_x}, {physical_y}) within {monitor.width}x{monitor.height}")
        
        # If overlay exists, get its DPI info for diagnostic purposes
        if self.overlay:
            try:
                dpr = self.overlay.devicePixelRatioF() if hasattr(self.overlay, 'devicePixelRatioF') else 1.0
                logical_w = self.overlay.width()
                logical_h = self.overlay.height()
                logger.info(f"🔍 Overlay DPI info: logical={logical_w}x{logical_h}, dpr={dpr:.2f}, physical_expected={logical_w*dpr:.0f}x{logical_h*dpr:.0f}")
                
                # Convert physical monitor coordinates to overlay widget coordinates
                # If overlay uses logical pixels, we need to convert from physical
                if dpr > 1.01:  # High DPI
                    # Physical monitor coords -> logical overlay coords
                    overlay_x = physical_x / dpr
                    overlay_y = physical_y / dpr
                    logger.info(f"🎯 DPI-adjusted overlay coordinates: ({overlay_x:.1f}, {overlay_y:.1f}) from physical ({physical_x}, {physical_y})")
                else:
                    # Standard DPI - use physical coordinates directly
                    overlay_x = physical_x
                    overlay_y = physical_y
                    logger.info(f"🎯 Standard DPI overlay coordinates: ({overlay_x}, {overlay_y})")
                
                self.overlay.add_dot(overlay_x, overlay_y)
                logger.info(f"✅ Dot added to overlay at ({overlay_x:.1f}, {overlay_y:.1f})")
                
            except Exception as e:
                logger.error(f"❌ Error adding dot with DPI handling: {e}")
                # Fallback to simple mapping
                self.overlay.add_dot(physical_x, physical_y)
        else:
            logger.error("❌ Overlay is None - cannot add dot!")
        
        # Ensure overlay is visible (but don't force focus in production)
        if self.config.get('overlay_debug_bg', False):
            self.overlay.raise_()
            self.overlay.activateWindow()

    def _setup_overlay(self):
        """Create and show the overlay window with proper transparency and emergency exit."""
        try:
            import platform
            mode = self.config.get('overlay_mode', 'simple')  # Default to simple for safety
            debug_bg = self.config.get('overlay_debug_bg', False)
            monitor, monitor_index = self._get_monitor_info()
            
            # Emergency close function
            def emergency_close():
                if self.overlay:
                    logger.info("🚨 Emergency close triggered - closing overlay!")
                    self.overlay.close()
                    self.overlay = None
            
            if platform.system() == 'Windows':
                from overlay import OverlayWindow, SimpleOverlayWindow
                
                # Always use simple mode for now to prevent blocking
                self.overlay = SimpleOverlayWindow(
                    monitor.x, monitor.y, monitor.width, monitor.height,
                    self.config.get('dot_color', '#FFFF00'),  # Yellow highlighter default
                    self.config.get('dot_radius_px', 20),  # Larger for visibility
                    self.config.get('fade_ms', 10000), 
                    debug_bg=debug_bg,
                    force_basic=self.config.get('overlay_force_basic', True)
                )
                
                # Add multiple emergency exit shortcuts
                from PySide6.QtCore import Qt
                from PySide6.QtGui import QShortcut, QKeySequence
                
                # ESC key
                self.esc_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self.overlay)
                self.esc_shortcut.activated.connect(emergency_close)
                
                # Ctrl+Alt+X
                self.ctrl_alt_x = QShortcut(QKeySequence("Ctrl+Alt+X"), self.overlay)
                self.ctrl_alt_x.activated.connect(emergency_close)
                
                # Alt+F4 (should work by default, but let's ensure it)
                self.alt_f4 = QShortcut(QKeySequence("Alt+F4"), self.overlay)
                self.alt_f4.activated.connect(emergency_close)

                logger.info(f"✅ Simple overlay created on monitor {monitor_index} (debug={debug_bg})")
                logger.info("📌 Emergency exits: ESC, Ctrl+Alt+X, or Alt+F4")
                # We'll place test dot after initial show & clear for accurate geometry
                
            else:
                # Linux fallback
                from overlay_linux import LinuxOverlayWindow
                self.overlay = LinuxOverlayWindow(monitor.x, monitor.y, monitor.width, monitor.height,
                                                 self.config.get('dot_color', '#FF0000'),
                                                 self.config.get('dot_radius_px', 15),
                                                 self.config.get('fade_ms', 10000))
                logger.info(f"✅ Linux overlay window created on monitor {monitor_index}")
                
            self.overlay.show()
            # Ensure any residual state is cleared then optionally place startup test dot using widget dimensions
            try:
                self.overlay.clear_dots()
            except Exception:
                pass
            if self.config.get('overlay_test_dot', True):
                try:
                    # Use overlay widget dimensions (after show) rather than monitor in case of DPI scaling
                    w = self.overlay.width()
                    h = self.overlay.height()
                    cx = w // 2
                    cy = h // 2
                    self.overlay.add_dot(cx, cy)
                    logger.info(f"🟡 Placed startup test dot at widget center ({cx},{cy}) size={w}x{h}. Disable with overlay_test_dot:false in config.json")
                except Exception as e:
                    logger.warning(f"Failed to place test dot: {e}")
                
        except Exception as e:
            logger.error(f"Failed to create overlay window: {e}")
            self.overlay = None
    
    def _setup_firestore_watcher(self):
        """Setup Firestore document watchers."""
        self.firestore_watcher = FirestoreWatcher(self.db, self.config['session_id'])
        
        # Connect signals
        self.firestore_watcher.session_changed.connect(self._on_session_changed)
        self.firestore_watcher.new_response.connect(self._on_new_response)
        
        # Start watching
        self.firestore_watcher.start()
        logger.info("Started Firestore watchers")
    
    def _setup_alternative_triggers(self):
        """Setup alternative screenshot triggers."""
        # Setup HTTP server trigger
        http_port = self.config.get('http_trigger_port', 8889)
        self.http_server = ScreenshotHTTPServer(port=http_port, callback=self._on_hotkey_pressed)
        self.http_server.start()
        
        # Setup file watcher trigger
        trigger_file = self.config.get('trigger_file', 'capture_now.txt')
        self.file_watcher = FileWatcherTrigger(trigger_file=trigger_file, callback=self._on_hotkey_pressed)
        self.file_watcher.start()
    
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
            
            # Register hotkey if enabled
            hotkey_success = False
            if self.config.get('enable_hotkey', False):
                try:
                    hotkey_success = self.hotkey_manager.register_hotkey(self._on_hotkey_pressed)
                except Exception as e:
                    logger.debug(f"Hotkey exception: {e}")
            else:
                logger.info("Hotkey disabled by configuration")
            
            # Setup alternative triggers
            self._setup_alternative_triggers()
            
            if hotkey_success:
                logger.info("✅ Global hotkey registered successfully")
            elif self.config.get('enable_hotkey', False):
                logger.info("Hotkey unavailable - relying on HTTP/file triggers")
            
            logger.info("📸 Screenshot triggers available:")
            if hotkey_success:
                logger.info("  • Press Ctrl+B (or alternative hotkey)")
            logger.info("  • Visit: http://localhost:8889 in your browser") 
            logger.info("  • Create file: capture_now.txt in this directory")
            
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
        
        if self.http_server:
            self.http_server.stop()
            
        if self.file_watcher:
            self.file_watcher.stop()
        
        if self.firestore_watcher:
            self.firestore_watcher.stop()
            self.firestore_watcher.wait(5000)  # Wait up to 5 seconds
        
        if self.overlay:
            self.overlay.close()


def main():
    """Main entry point."""
    import argparse
    import sys
    
    # Quick check for help before creating GUI
    if '--help' in sys.argv or '-h' in sys.argv:
        print("Student Tap Helper - Interactive Presentation System")
        print("Usage: slide_tap_helper.exe [config_file]")
        print("")
        print("Arguments:")
        print("  config_file         Path to configuration JSON file (default: config.json)")
        print("")
        print("Options:")
        print("  -h, --help          Show this help message and exit")
        print("  --version           Show version information and exit")
        print("")
        print("Examples:")
        print("  slide_tap_helper.exe                  # Use config.json")
        print("  slide_tap_helper.exe custom.json      # Use custom config file")
        print("")
        print("Requirements:")
        print("  - Windows 10/11")
        print("  - Firebase project with Firestore and Storage enabled")
        print("  - Service account JSON file (serviceAccount.json)")
        print("  - config.json with session and Firebase settings")
        print("")
        print("For setup instructions, see: https://github.com/MKK-SWPS/FIRESTORE_PRESENTATION")
        return 0
    
    parser = argparse.ArgumentParser(
        description="Desktop Helper for Student Tap Interactive Presentation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  slide_tap_helper.exe                  # Use config.json
  slide_tap_helper.exe custom.json      # Use custom config file

Requirements:
  - Windows 10/11
  - Firebase project with Firestore and Storage enabled
  - Service account JSON file
  - config.json with session and Firebase settings

For setup instructions, see: https://github.com/MKK-SWPS/FIRESTORE_PRESENTATION
        """
    )
    
    parser.add_argument(
        'config', 
        nargs='?', 
        default='config.json',
        help='Path to configuration JSON file (default: config.json)'
    )
    
    parser.add_argument(
        '--version', 
        action='version',
        version=f"Slide Tap Helper v{VERSION_INFO.get('version', 'unknown')} (built {VERSION_INFO.get('build_date', 'unknown')})"
    )
    
    # Parse arguments
    args = parser.parse_args()
    config_path = args.config
    
    # Check for debug flag
    debug = '--debug' in sys.argv or '_debug' in sys.argv[0].lower()
    
    # Set up file logging with auto-flush
    global logger
    logger = setup_logging(debug=debug)
    
    logger.info("=" * 60)
    logger.info("Starting Slide Tap Helper")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"Python: {sys.version}")
    logger.info(f"Platform: {platform.system()} {platform.release()}")
    logger.info(f"Working directory: {Path.cwd()}")
    logger.info(f"Executable path: {Path(sys.argv[0]).absolute()}")
    logger.info("=" * 60)
    
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