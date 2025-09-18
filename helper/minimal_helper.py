"""
Minimal Windows Desktop Helper - Student Response Viewer Only

This version focuses on just showing student tap responses without screenshot capture.
Use this if you're having issues with the full version.

To capture screenshots manually:
1. Use any screenshot tool
2. Upload to your Firebase Storage manually
3. Update the Firestore session document with the image URL
"""

import json
import os
import sys
import time
import threading
from datetime import datetime
import logging

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore

# Qt for overlay window
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QThread, Signal

# Local imports
from overlay import OverlayWindow

# Monitor detection
import screeninfo

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


class MinimalDesktopHelper:
    """Minimal application class for viewing student responses only."""
    
    def __init__(self, config_path='config.json'):
        self.config = self._load_config(config_path)
        self.app = QApplication(sys.argv)
        
        # Firebase setup
        self.db = None
        self._init_firebase()
        
        # Components
        self.overlay = None
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
        required_fields = ['session_id', 'service_account_path', 'monitor_index']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")
        
        return config
    
    def _init_firebase(self):
        """Initialize Firebase Admin SDK."""
        try:
            # Initialize with service account
            cred = credentials.Certificate(self.config['service_account_path'])
            firebase_admin.initialize_app(cred)
            
            # Get Firestore client
            self.db = firestore.client()
            
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
    
    def _on_session_changed(self, session_data):
        """Handle session document changes from Firestore."""
        self.current_session = session_data
        
        slide_index = session_data.get('slideIndex', 0)
        slides = session_data.get('slides', [])
        
        logger.info(f"Session updated: slide {slide_index + 1}/{len(slides)}")
        
        # If slide index changed away from our current overlay, clear dots
        if slide_index != self.current_slide_index and self.overlay:
            self.overlay.clear_dots()
            self.current_slide_index = slide_index
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
        
        logger.info(f"Added dot at ({abs_x}, {abs_y}) from student tap")
    
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
        """Start the minimal desktop helper application."""
        try:
            logger.info("Starting Minimal Desktop Helper (Response Viewer Only)...")
            logger.info(f"Session ID: {self.config['session_id']}")
            logger.info(f"Monitor: {self.config['monitor_index']}")
            logger.info("This version only shows student responses - no screenshot capture")
            
            # Setup components
            self._setup_overlay()
            self._setup_firestore_watcher()
            
            logger.info("Watching for student tap responses...")
            logger.info("To add slides, manually upload images to Firebase Storage and update the session document")
            
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
    
    def _cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")
        
        if self.firestore_watcher:
            self.firestore_watcher.stop()
            self.firestore_watcher.wait(5000)  # Wait up to 5 seconds
        
        if self.overlay:
            self.overlay.close()


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Minimal Desktop Helper - Student Response Viewer Only"
    )
    
    parser.add_argument(
        'config', 
        nargs='?', 
        default='config.json',
        help='Path to configuration JSON file (default: config.json)'
    )
    
    # Parse arguments
    args = parser.parse_args()
    config_path = args.config
    
    try:
        helper = MinimalDesktopHelper(config_path)
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