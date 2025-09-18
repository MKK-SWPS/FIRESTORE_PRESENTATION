#!/usr/bin/env python3
"""
Simple overlay test - verifies dot display without Firebase
"""

import sys
import time
from PySide6.QtWidgets import QApplication
from overlay_linux import LinuxOverlayWindow

def test_overlay():
    """Test the overlay with simulated tap data."""
    print("Starting overlay test...")
    
    app = QApplication(sys.argv)
    
    # Create overlay
    overlay = LinuxOverlayWindow()
    overlay.show()
    
    print("Overlay created and shown")
    print("Adding test dots...")
    
    # Add some test dots
    overlay.add_dot(100, 100)
    print("Added dot 1 at (100, 100)")
    
    time.sleep(1)
    overlay.add_dot(300, 200)
    print("Added dot 2 at (300, 200)")
    
    time.sleep(1)
    overlay.add_dot(500, 300)
    print("Added dot 3 at (500, 300)")
    
    print("Test complete! Check if you can see 3 red dots on the overlay window.")
    print("The window should be visible with dots that fade over time.")
    print("Close the window to exit.")
    
    return app.exec()

if __name__ == '__main__':
    exit(test_overlay())