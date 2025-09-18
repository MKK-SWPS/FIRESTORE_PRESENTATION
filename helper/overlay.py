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
from typing import List, Tuple
import logging

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QPainter, QBrush, QColor, QPen

# Windows API imports
import win32gui
import win32con
from ctypes import windll

logger = logging.getLogger(__name__)


class TapDot:
    """Represents a single tap dot with position, color, and fade timing."""
    
    def __init__(self, x: int, y: int, color: QColor, radius: int, fade_ms: int):
        self.x = x
        self.y = y
        self.color = color
        self.radius = radius
        self.fade_ms = fade_ms
        self.created_time = time.time() * 1000  # milliseconds
        
    def get_alpha(self) -> float:
        """Get current alpha value based on fade timing (0.0 to 1.0)."""
        if self.fade_ms <= 0:
            return 1.0  # No fade
        
        current_time = time.time() * 1000
        elapsed = current_time - self.created_time
        
        if elapsed >= self.fade_ms:
            return 0.0  # Fully faded
        
        # Smooth fade out using cosine
        fade_progress = elapsed / self.fade_ms
        alpha = (math.cos(fade_progress * math.pi) + 1) / 2
        return alpha
    
    def is_expired(self) -> bool:
        """Check if the dot should be removed."""
        return self.get_alpha() <= 0.0


class OverlayWindow(QWidget):
    """
    Transparent overlay window that displays tap dots.
    
    Uses Windows extended styles to be:
    - Always on top
    - Click-through (transparent to mouse/keyboard events)
    - Fully transparent background
    """
    
    def __init__(self, x: int, y: int, width: int, height: int, 
                 dot_color: str = '#8E4EC6', dot_radius: int = 8, fade_ms: int = 10000):
        super().__init__()
        
        # Configuration
        self.dot_color = QColor(dot_color)
        self.dot_radius = dot_radius
        self.fade_ms = fade_ms
        
        # State
        self.dots: List[TapDot] = []
        
        # Setup window
        self._setup_window(x, y, width, height)
        self._apply_transparency_and_click_through()
        
        # Timer for updating dots and repainting
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_dots)
        self.update_timer.start(50)  # Update every 50ms for smooth animation
        
        logger.info(f"Overlay window created: {width}x{height} at ({x}, {y})")
    
    def _setup_window(self, x: int, y: int, width: int, height: int):
        """Configure the basic window properties."""
        # Remove window frame and make it stay on top
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool |  # Don't show in taskbar
            Qt.BypassWindowManagerHint  # Bypass window manager
        )
        
        # Set geometry to cover the target monitor
        self.setGeometry(x, y, width, height)
        
        # Set transparent background
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        
        # Don't grab focus
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
    
    def _apply_transparency_and_click_through(self):
        """Apply Windows-specific extended styles for click-through behavior."""
        try:
            # Get the window handle
            hwnd = int(self.winId())
            
            # Get current extended style
            extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            # Add layered and transparent flags
            new_style = (extended_style | 
                        win32con.WS_EX_LAYERED | 
                        win32con.WS_EX_TRANSPARENT |
                        win32con.WS_EX_TOPMOST)
            
            # Apply the new style
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
            
            # Set layered window attributes for transparency
            # This makes the window fully transparent except for what we draw
            windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)
            
            logger.info("Applied click-through and transparency styles")
            
        except Exception as e:
            logger.error(f"Failed to apply window transparency: {e}")
    
    def add_dot(self, x: int, y: int):
        """Add a new tap dot at the specified screen coordinates."""
        # Convert screen coordinates to widget coordinates
        widget_pos = self.mapFromGlobal(self.mapToParent(self.rect().topLeft()))
        local_x = x - widget_pos.x()
        local_y = y - widget_pos.y()
        
        # Check if coordinates are within the widget bounds
        if (0 <= local_x <= self.width() and 0 <= local_y <= self.height()):
            dot = TapDot(local_x, local_y, self.dot_color, self.dot_radius, self.fade_ms)
            self.dots.append(dot)
            logger.debug(f"Added dot at ({local_x}, {local_y}) from screen ({x}, {y})")
            self.update()  # Trigger repaint
        else:
            logger.warning(f"Dot coordinates ({x}, {y}) outside widget bounds")
    
    def clear_dots(self):
        """Remove all dots from the overlay."""
        if self.dots:
            self.dots.clear()
            self.update()  # Trigger repaint
            logger.debug("Cleared all overlay dots")
    
    def _update_dots(self):
        """Update dots, removing expired ones and triggering repaints."""
        if not self.dots:
            return
        
        # Remove expired dots
        initial_count = len(self.dots)
        self.dots = [dot for dot in self.dots if not dot.is_expired()]
        
        if len(self.dots) != initial_count:
            logger.debug(f"Removed {initial_count - len(self.dots)} expired dots")
        
        # Trigger repaint if there are still dots
        if self.dots:
            self.update()
    
    def paintEvent(self, event):
        """Custom paint event to draw the tap dots."""
        if not self.dots:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        # Draw each dot
        for dot in self.dots:
            alpha = dot.get_alpha()
            if alpha <= 0:
                continue
            
            # Create color with current alpha
            color = QColor(dot.color)
            color.setAlphaF(alpha)
            
            # Set up painter
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(color, 1))
            
            # Draw the dot as a filled circle
            painter.drawEllipse(
                int(dot.x - dot.radius), 
                int(dot.y - dot.radius),
                dot.radius * 2, 
                dot.radius * 2
            )
        
        painter.end()
    
    def mousePressEvent(self, event):
        """Override mouse events to ensure they don't interfere."""
        # Don't handle mouse events - they should pass through
        event.ignore()
    
    def keyPressEvent(self, event):
        """Override keyboard events to ensure they don't interfere."""
        # Don't handle keyboard events - they should pass through
        event.ignore()
    
    def show(self):
        """Show the overlay window and ensure it's properly positioned."""
        super().show()
        
        # Force the window to be on top
        self.raise_()
        self.activateWindow()
        
        # Re-apply transparency after showing (sometimes needed)
        QTimer.singleShot(100, self._apply_transparency_and_click_through)
        
        logger.info("Overlay window shown")
    
    def closeEvent(self, event):
        """Clean up when the window is closed."""
        if self.update_timer:
            self.update_timer.stop()
        
        self.clear_dots()
        logger.info("Overlay window closed")
        super().closeEvent(event)


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
        overlay = OverlayWindow(
            primary.x, primary.y, primary.width, primary.height,
            dot_color='#FF00FF',  # Magenta for visibility
            dot_radius=12,
            fade_ms=5000
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