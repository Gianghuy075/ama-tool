from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QMouseEvent, QKeyEvent
import math
import time
import logging

class TransparentOverlay(QWidget):
    def __init__(self, parent_widget: QWidget, on_tap_callback, on_swipe_callback, on_key_callback=None):
        """
        Creates a transparent overlay window positioned on top of the parent_widget
        to capture and intercept mouse and keyboard inputs for synchronization.
        - parent_widget: Widget containing the embedded scrcpy window.
        - on_tap_callback: Function called with (x_pct, y_pct) on click.
        - on_swipe_callback: Function called with (x1_pct, y1_pct, x2_pct, y2_pct, duration_ms) on swipe.
        - on_key_callback: Function called with QKeyEvent on keypress.
        """
        super().__init__(None)  # Parent is None to allow absolute screen positioning
        self.parent_widget = parent_widget
        self.on_tap_callback = on_tap_callback
        self.on_swipe_callback = on_swipe_callback
        self.on_key_callback = on_key_callback
        
        # Borderless, top-most, tool window to avoid creating separate taskbar icon
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        
        # Set opacity to 1% to capture mouse events while remaining practically invisible
        self.setWindowOpacity(0.01)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        self.start_time = 0.0
        self.start_x = 0.0
        self.start_y = 0.0
        
        self.hide()
        self.sync_position()

    def sync_position(self):
        """Position and resize overlay to match parent_widget screen coordinates."""
        try:
            if not self.parent_widget or not self.parent_widget.isVisible():
                self.hide()
                return

            # Map the local (0,0) position of the parent widget to screen coordinates
            global_pos = self.parent_widget.mapToGlobal(QPoint(0, 0))
            w = self.parent_widget.width()
            h = self.parent_widget.height()
            
            if w > 10 and h > 10:
                self.setGeometry(global_pos.x(), global_pos.y(), w, h)
                self.show()
                self.raise_()
            else:
                self.hide()
        except Exception as e:
            logging.debug(f"Không thể đồng bộ vị trí overlay: {e}")
            self.hide()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_time = time.time()
            pos = event.position()
            self.start_x = pos.x()
            self.start_y = pos.y()
            self.setFocus()

    def keyPressEvent(self, event: QKeyEvent):
        if self.on_key_callback:
            self.on_key_callback(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.start_time == 0.0:
                return
                
            end_time = time.time()
            duration_ms = int((end_time - self.start_time) * 1000)
            if duration_ms < 100:
                duration_ms = 100
                
            pos = event.position()
            end_x = pos.x()
            end_y = pos.y()
            
            w = self.width()
            h = self.height()
            if w <= 0 or h <= 0:
                return
                
            dx = end_x - self.start_x
            dy = end_y - self.start_y
            dist = math.sqrt(dx * dx + dy * dy)
            
            x1_pct = max(0.0, min(1.0, self.start_x / w))
            y1_pct = max(0.0, min(1.0, self.start_y / h))
            x2_pct = max(0.0, min(1.0, end_x / w))
            y2_pct = max(0.0, min(1.0, end_y / h))
            
            if dist < 8:
                logging.info(f"[Overlay] Click tại tỷ lệ: ({x1_pct:.3f}, {y1_pct:.3f})")
                self.on_tap_callback(x1_pct, y1_pct)
            else:
                logging.info(f"[Overlay] Vuốt từ ({x1_pct:.3f}, {y1_pct:.3f}) tới ({x2_pct:.3f}, {y2_pct:.3f}) trong {duration_ms}ms")
                self.on_swipe_callback(x1_pct, y1_pct, x2_pct, y2_pct, duration_ms)
                
            self.start_time = 0.0
