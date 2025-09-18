"""
Linux-compatible overlay for testing in dev container

This is a simplified version of the overlay that works without Windows APIs
for testing purposes in the Linux dev container environment.
"""

import time
import logging
from typing import List, Tuple

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPainter, QBrush, QColor, QPen

logger = logging.getLogger(__name__)


class LinuxOverlayWindow(QWidget):
    """Linux-compatible overlay window for testing."""
    
    def __init__(self):
        super().__init__()
        self.dots = []
        self.DOT_SIZE = 20
        self.DOT_DURATION = 3.0
        
        # Basic window setup
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        
        # Set a reasonable size for testing
        self.setGeometry(0, 0, 1200, 800)
        self.setWindowTitle("Overlay Test")
        
        logger.info("Created Linux-compatible overlay window")
    
    def add_dot(self, x, y):
        """Add a dot and force repaint."""
        timestamp = time.time()
        self.dots.append((x, y, timestamp))
        logger.info(f"✅ Dot added to Linux overlay at ({x}, {y})")
        
        self.update()
        self.repaint()
        
        if not self.isVisible():
            self.show()
            self.raise_()
        
        # Start cleanup timer if not already running
        if not hasattr(self, 'cleanup_timer'):
            self.cleanup_timer = QTimer()
            self.cleanup_timer.timeout.connect(self._cleanup_dots)
            self.cleanup_timer.start(100)
    
    def _cleanup_dots(self):
        """Remove expired dots."""
        current_time = time.time()
        old_count = len(self.dots)
        self.dots = [(x, y, timestamp) for x, y, timestamp in self.dots 
                     if current_time - timestamp < self.DOT_DURATION]
        
        if len(self.dots) != old_count:
            self.update()
        
        # Stop timer if no dots left
        if not self.dots and hasattr(self, 'cleanup_timer'):
            self.cleanup_timer.stop()
    
    def paintEvent(self, event):
        """Simple paint event."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # Semi-transparent background for visibility in testing
        painter.fillRect(self.rect(), QColor(0, 0, 0, 50))
        
        current_time = time.time()
        
        for x, y, timestamp in self.dots:
            age = current_time - timestamp
            if age >= self.DOT_DURATION:
                continue
                
            fade_factor = 1.0 - (age / self.DOT_DURATION)
            alpha = int(255 * fade_factor)
            
            color = QColor(255, 0, 0, alpha)
            painter.setPen(QPen(color, 3))
            painter.setBrush(QBrush(color))
            
            painter.drawEllipse(int(x - self.DOT_SIZE//2), int(y - self.DOT_SIZE//2), 
                              self.DOT_SIZE, self.DOT_SIZE)
        
        painter.end()


# Simple compatibility wrapper
class OverlayWindow(LinuxOverlayWindow):
    """Compatibility wrapper for Linux testing."""
    
    def __init__(self, x=0, y=0, width=1200, height=800, dot_color='#FF0000', dot_radius=10, fade_ms=3000):
        super().__init__()
        self.DOT_SIZE = dot_radius * 2
        self.DOT_DURATION = fade_ms / 1000.0
        self.setGeometry(x, y, width, height)
        logger.info(f"Linux overlay created: {width}x{height} at ({x}, {y})")


class FallbackOverlayWindow(LinuxOverlayWindow):
    """Fallback is the same as main in Linux."""
    pass


if __name__ == '__main__':
    # Test the overlay
    import sys
    app = QApplication(sys.argv)
    
    overlay = LinuxOverlayWindow()
    overlay.show()
    
    # Add some test dots
    overlay.add_dot(100, 100)
    overlay.add_dot(300, 200)
    overlay.add_dot(500, 400)
    
    print("Linux overlay test started. Close window to exit.")
    
    sys.exit(app.exec())