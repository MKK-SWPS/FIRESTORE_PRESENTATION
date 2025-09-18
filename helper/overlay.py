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
        if not HAS_WIN32:
            logger.warning("Windows API not available, skipping transparency setup")
            return
            
        try:
            # Get the window handle
            hwnd = int(self.winId())
            
            if not hwnd:
                logger.error("Could not get window handle")
                return
            
            # Get current extended style
            extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            
            # Add layered and transparent flags
            new_style = (extended_style | 
                        win32con.WS_EX_LAYERED | 
                        win32con.WS_EX_TRANSPARENT |
                        win32con.WS_EX_TOPMOST)
            
            # Apply the new style
            result = win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
            
            if result == 0:
                logger.warning("SetWindowLong may have failed, but continuing...")
            
            # Try different approaches for layered window attributes
            try:
                # Method 1: Standard SetLayeredWindowAttributes
                result = windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)
                if result:
                    logger.info("Applied transparency using SetLayeredWindowAttributes")
                else:
                    logger.warning("SetLayeredWindowAttributes returned 0, trying alternative...")
                    
                    # Method 2: Try with different parameters
                    result2 = windll.user32.SetLayeredWindowAttributes(hwnd, 0, 200, win32con.LWA_ALPHA)
                    if result2:
                        logger.info("Applied transparency with reduced alpha")
                    else:
                        logger.warning("All SetLayeredWindowAttributes methods failed")
                        
            except Exception as e:
                logger.error(f"SetLayeredWindowAttributes failed: {e}")
            
            logger.info("Applied click-through and transparency styles")
            
        except Exception as e:
            logger.error(f"Failed to apply window transparency: {e}")
            # Continue anyway - overlay might still work partially
    
    def add_dot(self, x, y):
        """Add a new dot at the specified coordinates."""
        timestamp = time.time()
        self.dots.append((x, y, timestamp))
        logger.info(f"✅ Dot added to overlay at ({x}, {y})")
        
        # Force immediate repaint using multiple methods
        try:
            self.update()
            self.repaint()
            
            # Also try to force a Windows redraw if on Windows
            if HAS_WIN32:
                hwnd = int(self.winId())
                windll.user32.InvalidateRect(hwnd, None, True)
                windll.user32.UpdateWindow(hwnd)
            
            # Force show if hidden
            if not self.isVisible():
                self.show()
                self.raise_()
                self.activateWindow()
                
        except Exception as e:
            logger.error(f"Error forcing repaint: {e}")
        
        # Start timer to remove old dots
        if not hasattr(self, 'cleanup_timer'):
            self.cleanup_timer = QTimer()
            self.cleanup_timer.timeout.connect(self._cleanup_dots)
            self.cleanup_timer.start(100)  # Check every 100ms
    
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
        """Handle paint events to draw tap dots."""
        painter = QPainter(self)
        
        # Enable anti-aliasing
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        # Clear the background
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        
        current_time = time.time()
        
        # Draw dots and remove expired ones
        self.dots = [(x, y, timestamp) for x, y, timestamp in self.dots 
                     if current_time - timestamp < self.DOT_DURATION]
        
        for x, y, timestamp in self.dots:
            # Calculate fade based on age
            age = current_time - timestamp
            fade_factor = 1.0 - (age / self.DOT_DURATION)
            alpha = int(255 * fade_factor)
            
            # Set up the pen and brush for the dot
            color = QColor(255, 0, 0, alpha)  # Red with alpha
            painter.setPen(QPen(color, 2))
            painter.setBrush(QBrush(color))
            
            # Draw a circle
            painter.drawEllipse(int(x - self.DOT_SIZE//2), int(y - self.DOT_SIZE//2), 
                              self.DOT_SIZE, self.DOT_SIZE)
            
            logger.debug(f"Drew dot at ({x}, {y}) with alpha {alpha}")
        
        painter.end()
        
        # Update the display
        self.update() if self.dots else None
    
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


class FallbackOverlayWindow(QWidget):
    """Simpler fallback overlay window with basic transparency."""
    
    def __init__(self):
        super().__init__()
        self.dots = []
        self.DOT_SIZE = 20
        self.DOT_DURATION = 3.0
        
        # Simpler window setup
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet("background-color: transparent;")
        
        # Full screen
        from PySide6.QtWidgets import QApplication
        desktop = QApplication.desktop()
        combined_geometry = QRect()
        for i in range(desktop.screenCount()):
            screen_geometry = desktop.screenGeometry(i)
            combined_geometry = combined_geometry.united(screen_geometry)
        
        self.setGeometry(combined_geometry)
        
        # Set window opacity
        self.setWindowOpacity(0.8)
        
        logger.info("Created fallback overlay window")
    
    def add_dot(self, x, y):
        """Add a dot and force repaint."""
        timestamp = time.time()
        self.dots.append((x, y, timestamp))
        logger.info(f"✅ Dot added to fallback overlay at ({x}, {y})")
        
        self.update()
        self.repaint()
        
        if not self.isVisible():
            self.show()
            self.raise_()
    
    def paintEvent(self, event):
        """Simple paint event."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        
        current_time = time.time()
        self.dots = [(x, y, timestamp) for x, y, timestamp in self.dots 
                     if current_time - timestamp < self.DOT_DURATION]
        
        for x, y, timestamp in self.dots:
            age = current_time - timestamp
            fade_factor = 1.0 - (age / self.DOT_DURATION)
            alpha = int(255 * fade_factor)
            
            color = QColor(255, 0, 0, alpha)
            painter.setPen(QPen(color, 3))
            painter.setBrush(QBrush(color))
            
            painter.drawEllipse(int(x - self.DOT_SIZE//2), int(y - self.DOT_SIZE//2), 
                              self.DOT_SIZE, self.DOT_SIZE)
        
        painter.end()


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