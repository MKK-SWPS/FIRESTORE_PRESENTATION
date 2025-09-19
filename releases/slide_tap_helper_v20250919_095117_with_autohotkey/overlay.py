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
from PySide6.QtGui import QPainter, QBrush, QColor, QPen, QGuiApplication

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
    """Simple overlay window without layered transparency - more reliable.

    Improvements:
    - Optional skip of Windows layered/click-through style (overlay_force_basic)
    - Fully transparent background (removed residual 1 alpha fill) to eliminate black screen
    - Paint diagnostics (counts, devicePixelRatio, geometry) for troubleshooting
    - Heuristic coordinate scaling if incoming dots appear outside widget bounds due to DPI scaling
    """
    
    def __init__(self, x: int, y: int, width: int, height: int, 
                 dot_color: str = '#FFFF00', dot_radius: int = 20, fade_ms: int = 10000,
                 debug_bg: bool = False, force_basic: bool = True):
        super().__init__()
        
        # Store monitor geometry for reference
        self.screen_x = x
        self.screen_y = y
        self.screen_width = width
        self.screen_height = height
        
        # Configuration
        self.dot_color = QColor(dot_color)
        self.dot_radius = dot_radius
        self.fade_ms = fade_ms
        self.debug_bg = debug_bg
        self.force_basic = force_basic
        
        # Simple dot storage: list of (x, y, timestamp) tuples
        self.dots = []
        self.DOT_DURATION = fade_ms / 1000.0  # Convert ms to seconds
        
        # Setup window
        self.setWindowTitle("Student Tap Overlay")
        self.setGeometry(x, y, width, height)
        
        # Set proper window flags for transparency and click-through
        flags = (Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | 
                Qt.WindowTransparentForInput | Qt.Tool)
        self.setWindowFlags(flags)

        # Transparency attributes
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        # Avoid forcing WA_NoSystemBackground (can cause black on some GPUs) and instead clear in paint
        self.setAutoFillBackground(False)
        # Remove any background fill. Using stylesheet with full transparency can still trigger paint on some GPUs.
        # Avoid stylesheet entirely unless debug background requested.
        if self.debug_bg:
            # Show faint border / tint for diagnostics only
            self.setStyleSheet("background: rgba(30,30,30,120);")
        else:
            self.setStyleSheet("")
        
        # Apply Windows-specific transparency and click-through
        if HAS_WIN32 and not self.force_basic:
            # Allow time for window to fully create before applying extended styles
            QTimer.singleShot(120, self._apply_windows_transparency)
            
        # Timer for cleanup
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._cleanup_dots)
        self.update_timer.start(1000)  # Every second
        
        # Diagnostics
        self._paint_count = 0
        logger.info(f"Simple overlay window created: {width}x{height} at ({x}, {y}) debug={debug_bg} force_basic={self.force_basic}")
        try:
            hwnd_dbg = int(self.winId())
            logger.info(f"Overlay HWND={hwnd_dbg} flags={hex(int(self.windowFlags()))} attrs: translucent={self.testAttribute(Qt.WA_TranslucentBackground)} autoFill={self.autoFillBackground()}")
        except Exception:
            pass
    
    def _apply_windows_transparency(self):
        """Apply Windows-specific transparency for click-through behavior."""
        try:
            import win32gui
            import win32con
            
            hwnd = int(self.winId())
            if hwnd:
                # Get current extended style
                extended_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                # Add transparent, layered, and no-activate flags
                new_style = (extended_style | win32con.WS_EX_TRANSPARENT | 
                           win32con.WS_EX_LAYERED | win32con.WS_EX_TOPMOST | 
                           win32con.WS_EX_NOACTIVATE)
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
                # Set layer attributes for transparency
                win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)
                logger.debug(f"Applied Windows click-through styles to HWND {hwnd}")
        except Exception as e:
            logger.debug(f"Windows transparency failed: {e}")
    
    def add_dot(self, x, y):
        """Add a tap dot at window-relative coordinates.
        
        Coordinates should already be properly scaled for the overlay widget.
        This method no longer applies DPI heuristics since proper scaling 
        is handled in the calling code.
        """
        timestamp = time.time()
        w = self.width()
        h = self.height()
        dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 1.0

        # Log the coordinates we received for debugging
        logger.debug(f"Overlay add_dot called: ({x:.1f}, {y:.1f}) widget_size={w}x{h} dpr={dpr:.2f}")
        
        # Simple bounds check - allow small margin for edge cases
        if x < -20 or y < -20 or x > w + 20 or y > h + 20:
            logger.warning(f"Dot out of bounds: ({x:.1f},{y:.1f}) widget={w}x{h} - adding anyway")
            # Note: We still add the dot even if out of bounds for debugging
        
        self.dots.append((x, y, timestamp))
        logger.debug(f"Added dot to overlay: ({x:.1f}, {y:.1f}) total_dots={len(self.dots)}")
        
        # Force immediate repaint
        self.update()
        self.repaint()
        
        # Also force Windows repaint if available
        if HAS_WIN32:
            try:
                import win32gui
                hwnd = int(self.winId())
                win32gui.InvalidateRect(hwnd, None, True)
                win32gui.UpdateWindow(hwnd)
            except Exception:
                pass
        
        # Ensure visibility
        if not self.isVisible():
            self.show()
    
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
        """Paint the overlay with dots ensuring full transparency clearing first."""
        painter = QPainter(self)
        try:
            # Explicitly clear background for true transparency
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(self.rect(), Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

            painter.setRenderHint(QPainter.Antialiasing, True)

            if self.debug_bg:
                painter.setPen(QPen(QColor(255, 255, 0, 120), 1))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(0, 0, self.width()-1, self.height()-1)

            current_time = time.time()
            self._paint_count += 1
            if self._paint_count <= 5 or self._paint_count % 100 == 0:
                # Log initial few paints and then every 100th for diagnostics
                try:
                    dpr = self.devicePixelRatioF() if hasattr(self, 'devicePixelRatioF') else 1.0
                    logger.debug(f"paintEvent #{self._paint_count} dots={len(self.dots)} size={self.width()}x{self.height()} dpr={dpr:.2f}")
                except Exception:
                    pass
            for x, y, timestamp in self.dots:
                if x < 0 or y < 0 or x > self.screen_width + 5 or y > self.screen_height + 5:
                    logger.debug(f"Dot out of bounds skipped ({x},{y}) screen {self.screen_width}x{self.screen_height}")
                    continue
                age = current_time - timestamp
                if age < self.DOT_DURATION:
                    fade_factor = 1.0 - (age / self.DOT_DURATION)
                    alpha = int(255 * fade_factor)
                    color = QColor(self.dot_color)
                    color.setAlpha(alpha)
                    painter.setBrush(QBrush(color))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(int(x - self.dot_radius), int(y - self.dot_radius), self.dot_radius*2, self.dot_radius*2)
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