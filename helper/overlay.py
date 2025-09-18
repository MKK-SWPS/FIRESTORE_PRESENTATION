"""
Transparent Overlay Window for Student Tap System

This module provides a transparent, click-through overlay window that:
- Covers the entire target monitor
- Shows purple dots at student tap locations
- Is always on top but doesn't intercept mouse/keyboard events
- Supports timed fade effects for dots
- Uses Windows extended styles for true transparency and click-through

Requirements:
- Windows only
- PySide6 for Qt GUI framework
- pywin32 for Windows API access
"""

import time
import math
import platform
from typing import List, Tuple
import logging

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPainter, QBrush, QColor, QPen

# Windows API imports (only on Windows)
if platform.system() == "Windows":
    try:
        import win32gui
        import win32con
        from ctypes import windll
        HAS_WIN32 = True
    except ImportError:
        HAS_WIN32 = False
        print("Warning: Windows API modules not available")
else:
    HAS_WIN32 = False

logger = logging.getLogger(__name__)


class SimpleOverlayWindow(QWidget):
    """Simple overlay window without layered transparency - more reliable."""
    
    def __init__(self, x: int, y: int, width: int, height: int, 
                 dot_color: str = '#FF0000', dot_radius: int = 15, fade_ms: int = 10000,
                 debug_bg: bool = False):
        super().__init__()
        
        # Configuration
        self.dot_color = QColor(dot_color)
        self.dot_radius = dot_radius
        self.fade_ms = fade_ms
        self.debug_bg = debug_bg
        
        # Simple dot storage: list of (x, y, timestamp) tuples
        self.dots = []
        self.DOT_DURATION = fade_ms / 1000.0  # Convert ms to seconds
        
        # Setup window
        self.setWindowTitle("Student Tap Overlay")
        self.setGeometry(x, y, width, height)
        
        # CRITICAL FIX: Proper window flags for transparency and click-through
        if debug_bg:
            # Debug mode: semi-transparent, closeable, stays on top
            flags = Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint
            self.setWindowOpacity(0.3)  # Semi-transparent for visibility
        else:
            # Production mode: fully transparent, click-through, no taskbar
            flags = (Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | 
                    Qt.WindowTransparentForInput | Qt.Tool)
            self.setWindowOpacity(1.0)
            
        self.setWindowFlags(flags)
        
        # Set transparency attributes
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        
        # CRITICAL: Set stylesheet for proper transparency
        if not debug_bg:
            self.setStyleSheet("background: transparent;")
            
        # Apply Windows-specific click-through if available
        if HAS_WIN32 and not debug_bg:
            self._apply_windows_transparency()
            
        # Timer for cleanup
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._cleanup_dots)
        self.update_timer.start(1000)  # Every second
        
        logger.info(f"Simple overlay window created: {width}x{height} at ({x}, {y}) debug={debug_bg}")
    
    def _apply_windows_transparency(self):
        """Apply Windows-specific transparency for click-through behavior."""
        try:
            import win32gui
            import win32con
            
            # Get window handle after it's created
            QTimer.singleShot(100, self._delayed_transparency)
        except Exception as e:
            logger.debug(f"Could not set up Windows transparency: {e}")
    
    def _delayed_transparency(self):
        """Apply transparency after window is fully created."""
        try:
            import win32gui
            import win32con
            
            hwnd = int(self.winId())
            if hwnd:
                # Get current extended style
                extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                # Add transparent and layered flags
                new_style = (extended_style | win32con.WS_EX_TRANSPARENT | 
                           win32con.WS_EX_LAYERED | win32con.WS_EX_TOPMOST)
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
                # Set layer attributes for transparency
                win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)
                logger.debug("Applied Windows click-through transparency")
        except Exception as e:
            logger.debug(f"Windows transparency failed: {e}")
    
    def add_dot(self, x, y):
        """Add a new dot at the specified coordinates."""
        timestamp = time.time()
        # Convert absolute coordinates to relative (since overlay covers monitor)
        monitor_x = self.geometry().x()
        monitor_y = self.geometry().y()
        relative_x = x - monitor_x
        relative_y = y - monitor_y
        
        self.dots.append((relative_x, relative_y, timestamp))
        logger.info(f"✅ Dot added to simple overlay at ({relative_x}, {relative_y}) (absolute: {x}, {y})")
        
        # Force immediate repaint
        self.update()
        self.repaint()
        
        # Ensure visibility - but don't force focus in production
        if not self.isVisible():
            self.show()
        if self.debug_bg:
            self.raise_()
            self.activateWindow()
    
    def clear_dots(self):
        """Remove all dots from the overlay."""
        if self.dots:
            self.dots.clear()
            self.update()
            logger.debug("Cleared all simple overlay dots")
    
    def _cleanup_dots(self):
        """Remove expired dots and trigger repaint if needed."""
        if not self.dots:
            return
        
        current_time = time.time()
        initial_count = len(self.dots)
        
        # Remove expired dots
        self.dots = [(x, y, timestamp) for x, y, timestamp in self.dots 
                     if current_time - timestamp < self.DOT_DURATION]
        
        if len(self.dots) != initial_count:
            logger.debug(f"Removed {initial_count - len(self.dots)} expired dots")
            self.update()
    
    def paintEvent(self, event):
        """Paint the overlay with dots."""
        painter = QPainter(self)
        
        try:
            # Enable anti-aliasing
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            
            # Clear background first
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            if self.debug_bg:
                # Debug: semi-transparent dark background with red border
                painter.fillRect(self.rect(), QColor(50, 50, 50, 100))
                painter.setPen(QPen(QColor(255, 0, 0), 3))
                painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
            else:
                # Transparent background
                painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
            
            # Switch to normal composition for dots
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            
            # Draw dots with fade effect
            current_time = time.time()
            for x, y, timestamp in self.dots:
                age = current_time - timestamp
                if age < self.DOT_DURATION:
                    # Calculate fade
                    fade_factor = 1.0 - (age / self.DOT_DURATION)
                    alpha = int(255 * fade_factor)
                    
                    # Set up color with alpha
                    color = QColor(self.dot_color)
                    color.setAlpha(alpha)
                    
                    # Draw dot
                    painter.setPen(QPen(color, 2))
                    painter.setBrush(QBrush(color))
                    painter.drawEllipse(int(x - self.dot_radius), int(y - self.dot_radius), 
                                      self.dot_radius * 2, self.dot_radius * 2)
        
        finally:
            painter.end()
    
    def show(self):
        """Show the overlay window and ensure it's properly positioned."""
        super().show()
        if self.debug_bg:
            self.raise_()
            self.activateWindow()
        logger.info("Simple overlay window shown")
    
    def closeEvent(self, event):
        """Clean up when the window is closed."""
        if self.update_timer:
            self.update_timer.stop()
        self.clear_dots()
        logger.info("Simple overlay window closed")
        super().closeEvent(event)


# Legacy alias for compatibility
OverlayWindow = SimpleOverlayWindow


class TestOverlay:
    """Simple test class for the overlay window."""
    
    @staticmethod
    def run_test():
        """Run a basic test of the overlay functionality."""
        import sys
        from PySide6.QtWidgets import QApplication
        import screeninfo
        
        app = QApplication(sys.argv)
        
        # Get primary monitor
        monitors = screeninfo.get_monitors()
        primary = monitors[0]
        
        # Create overlay
        overlay = SimpleOverlayWindow(
            primary.x, primary.y, primary.width, primary.height,
            dot_color='#FF0000',  # Red for visibility
            dot_radius=15,
            fade_ms=5000,
            debug_bg=True
        )
        
        overlay.show()
        
        # Add some test dots
        overlay.add_dot(primary.x + 100, primary.y + 100)
        overlay.add_dot(primary.x + primary.width // 2, primary.y + primary.height // 2)
        overlay.add_dot(primary.x + primary.width - 100, primary.y + primary.height - 100)
        
        print("Test overlay created with 3 dots. Press Ctrl+C to exit.")
        print(f"Overlay covers: {primary.width}x{primary.height} at ({primary.x}, {primary.y})")
        
        try:
            return app.exec()
        except KeyboardInterrupt:
            print("Test interrupted")
            return 0


if __name__ == '__main__':
    # Run test if executed directly
    logging.basicConfig(level=logging.DEBUG)
    test = TestOverlay()
    exit(test.run_test())