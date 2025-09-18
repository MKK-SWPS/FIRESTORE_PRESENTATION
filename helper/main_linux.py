#!/usr/bin/env python3
"""
Simplified Student Tap Helper for Linux Testing

This is a simplified version for testing in the Linux dev container.
It removes Windows-specific hotkey functionality but keeps the Firebase
integration and overlay testing.
"""

import sys
import os
import platform
import logging
import time
import json
from pathlib import Path

# Add the helper directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore, storage

# Qt imports
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtCore import QThread, QTimer, Signal, QObject
from PySide6.QtGui import QIcon, QPixmap, QAction

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('student_tap_helper.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class FirestoreWatcher(QObject):
    """Watch for student tap responses in Firestore."""
    
    tap_received = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self.db = None
        self.listener = None
        self.running = False
        
    def start_watching(self):
        """Start watching for Firestore changes."""
        try:
            # Initialize Firebase
            if not firebase_admin._apps:
                # Try to load credentials from file
                cred_path = Path(__file__).parent / "firebase_credentials.json"
                if cred_path.exists():
                    cred = credentials.Certificate(str(cred_path))
                    firebase_admin.initialize_app(cred)
                    logger.info("✅ Firebase initialized with credentials file")
                else:
                    # Try with default credentials
                    firebase_admin.initialize_app()
                    logger.info("✅ Firebase initialized with default credentials")
            
            # Get Firestore client
            self.db = firestore.client()
            
            # Set up listener for student responses
            self.listener = self.db.collection('student_responses').on_snapshot(self._on_snapshot)
            self.running = True
            
            logger.info("✅ Started watching for student tap responses")
            
        except Exception as e:
            logger.error(f"❌ Failed to start Firestore watcher: {e}")
    
    def _on_snapshot(self, col_snapshot, changes, read_time):
        """Handle Firestore snapshot changes."""
        for change in changes:
            if change.type.name == 'ADDED':
                doc_data = change.document.to_dict()
                logger.info(f"📍 New student tap: {doc_data}")
                
                # Extract coordinates
                if 'position' in doc_data:
                    position = doc_data['position']
                    if 'x' in position and 'y' in position:
                        # Emit the tap data
                        self.tap_received.emit({
                            'x': float(position['x']),
                            'y': float(position['y']),
                            'timestamp': doc_data.get('timestamp', time.time())
                        })
    
    def stop_watching(self):
        """Stop the Firestore listener."""
        if self.listener:
            self.listener.unsubscribe()
            self.listener = None
            self.running = False
            logger.info("Stopped Firestore watcher")

class TapOverlayManager(QObject):
    """Manages the overlay window for displaying tap dots."""
    
    def __init__(self):
        super().__init__()
        self.overlay = None
        
    def initialize_overlay(self):
        """Initialize the overlay window."""
        try:
            if platform.system() == "Windows":
                # Use Windows overlay (won't work in container but that's OK)
                from overlay import OverlayWindow
                self.overlay = OverlayWindow()
                logger.info("✅ Windows overlay initialized")
            else:
                # Use Linux overlay
                from overlay_linux import LinuxOverlayWindow
                self.overlay = LinuxOverlayWindow()
                logger.info("✅ Linux overlay initialized")
            
            if self.overlay:
                self.overlay.show()
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize overlay: {e}")
            self.overlay = None
    
    def handle_tap(self, tap_data):
        """Handle a new tap by adding it to the overlay."""
        if not self.overlay:
            logger.warning("No overlay available to display tap")
            return
        
        try:
            # Convert normalized coordinates to screen coordinates
            # For now, use a simple 1920x1080 assumption
            screen_width, screen_height = 1920, 1080
            
            x = int(tap_data['x'] * screen_width)
            y = int(tap_data['y'] * screen_height)
            
            logger.info(f"Converting tap: ({tap_data['x']:.3f}, {tap_data['y']:.3f}) → ({x}, {y})")
            
            # Add dot to overlay
            self.overlay.add_dot(x, y)
            
        except Exception as e:
            logger.error(f"❌ Error handling tap: {e}")

class StudentTapHelper:
    """Main application class."""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.firestore_watcher = FirestoreWatcher()
        self.overlay_manager = TapOverlayManager()
        
        # Connect signals
        self.firestore_watcher.tap_received.connect(self.overlay_manager.handle_tap)
        
        logger.info("Student Tap Helper initialized")
    
    def start(self):
        """Start the application."""
        try:
            # Initialize overlay
            self.overlay_manager.initialize_overlay()
            
            # Start Firestore watcher
            self.firestore_watcher.start_watching()
            
            # Create simple menu
            if QSystemTrayIcon.isSystemTrayAvailable():
                self._create_system_tray()
            else:
                logger.warning("System tray not available")
            
            logger.info("✅ Student Tap Helper started successfully")
            logger.info("Waiting for student taps...")
            
            # Start Qt event loop
            return self.app.exec()
            
        except Exception as e:
            logger.error(f"❌ Failed to start application: {e}")
            return 1
    
    def _create_system_tray(self):
        """Create system tray icon and menu."""
        try:
            self.tray_icon = QSystemTrayIcon()
            
            # Create a simple icon
            pixmap = QPixmap(16, 16)
            pixmap.fill()
            self.tray_icon.setIcon(QIcon(pixmap))
            
            # Create menu
            menu = QMenu()
            
            test_action = QAction("Test Overlay")
            test_action.triggered.connect(self._test_overlay)
            menu.addAction(test_action)
            
            quit_action = QAction("Quit")
            quit_action.triggered.connect(self.quit)
            menu.addAction(quit_action)
            
            self.tray_icon.setContextMenu(menu)
            self.tray_icon.show()
            
            logger.info("✅ System tray created")
            
        except Exception as e:
            logger.warning(f"Failed to create system tray: {e}")
    
    def _test_overlay(self):
        """Add test dots to the overlay."""
        if self.overlay_manager.overlay:
            self.overlay_manager.overlay.add_dot(100, 100)
            self.overlay_manager.overlay.add_dot(300, 200)
            self.overlay_manager.overlay.add_dot(500, 300)
            logger.info("✅ Added test dots to overlay")
        else:
            logger.warning("No overlay available for testing")
    
    def quit(self):
        """Quit the application."""
        self.firestore_watcher.stop_watching()
        self.app.quit()

if __name__ == '__main__':
    # Create and run the application
    helper = StudentTapHelper()
    sys.exit(helper.start())