from PyQt6.QtCore import Qt, QProcess, QTimer, QPoint, QRect, QSize, QEvent
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QGridLayout, QRubberBand, QSizePolicy
)
from PyQt6.QtGui import QFont, QMouseEvent, QWindow
import subprocess
import time
import logging
from typing import Dict, List, Callable, Optional

import config
from utils import helpers
from adb_handler import ADBHandler

class StreamContainer(QFrame):
    def __init__(self, parent: QWidget, card: 'DeviceCard'):
        super().__init__(parent)
        self.card = card
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setStyleSheet("background-color: #0a0a0d; border-bottom-left-radius: 9px; border-bottom-right-radius: 9px;")
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.card.is_streaming and self.card.scrcpy_hwnd:
            helpers.resize_embed_window(self.card.scrcpy_hwnd, self.width(), self.height())

class DeviceCard(QFrame):
    stream_state_changed = pyqtSignal = None # Will bind via parent callback

    def __init__(
        self, 
        parent: QWidget, 
        serial: str, 
        adb_handler: ADBHandler, 
        on_stream_state_changed: Callable[[str, bool], None]
    ):
        super().__init__(parent)
        self.serial = serial
        self.adb_handler = adb_handler
        self.on_stream_state_changed = on_stream_state_changed
        
        self.scrcpy_process: Optional[QProcess] = None
        self.scrcpy_hwnd: Optional[int] = None
        self.is_streaming = False
        self.is_starting = False
        
        self.is_selected = False
        self.is_master = False
        self.is_absent = False
        self.is_retrying = False
        self.retry_count = 0
        self.max_retries = 3
        
        # UI Styling (Gray-dark border frame)
        self.setObjectName("DeviceCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._update_card_style()
        
        # Main layout
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)
        
        # 1. Header Bar
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(40)
        self.header_frame.setStyleSheet("background-color: #18181c; border-top-left-radius: 9px; border-top-right-radius: 9px;")
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(12, 5, 12, 5)
        
        self.title_label = QLabel(f"📱 {self.serial}")
        self.title_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #e0e0e0; background: transparent;")
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        
        card_layout.addWidget(self.header_frame)
        
        # 2. Stream Container Area
        self.stream_container = StreamContainer(self, self)
        self.container_layout = QVBoxLayout(self.stream_container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        
        # Placeholder label
        self.placeholder_label = QLabel("Đang kết nối màn hình...")
        self.placeholder_label.setFont(QFont("Segoe UI", 9, -1, True))
        self.placeholder_label.setStyleSheet("color: #6c7a89;")
        self.placeholder_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.container_layout.addWidget(self.placeholder_label)
        
        card_layout.addWidget(self.stream_container, 1)
        
        # Window embed widget reference
        self.embed_widget: Optional[QWidget] = None
        
        # QTimer to wait for window handle
        self.find_timer = QTimer(self)
        self.find_timer.setInterval(200)
        self.find_timer.timeout.connect(self._check_scrcpy_window)
        self.find_start_time = 0.0

    def focus_device(self):
        """Focus keyboard control onto scrcpy window."""
        if self.is_streaming and self.scrcpy_hwnd:
            logging.info(f"Chuyển focus bàn phím sang thiết bị: {self.serial}")
            helpers.focus_window_cross_process(self.scrcpy_hwnd)

    def set_selected(self, state: bool):
        self.is_selected = state
        self._update_card_style()

    def set_master(self, state: bool):
        self.is_master = state
        self._update_card_style()

    def set_absent(self, is_absent: bool):
        if self.is_absent == is_absent:
            return
        self.is_absent = is_absent
        if is_absent:
            self.stop_stream()
        self._update_card_style()

    def _update_card_style(self):
        border_color = "#1e1e24"
        text_color = "#e0e0e0"
        title_text = f"📱 {self.serial}"
        
        if self.is_absent:
            border_color = "#ff4757"
            text_color = "#ff4757"
            title_text = f"❌ {self.serial} (Mất kết nối)"
        elif self.is_selected:
            border_color = "#2ecc71"
            text_color = "#2ecc71"
            title_text = f"✅ {self.serial} [SELECTED]"
            
        self.setStyleSheet(f"""
            QFrame#DeviceCard {{
                background-color: #1e1e24;
                border: 3px solid {border_color};
                border-radius: 12px;
            }}
        """)
        if hasattr(self, "title_label"):
            self.title_label.setText(title_text)
            self.title_label.setStyleSheet(f"color: {text_color}; background: transparent;")

    def toggle_stream(self):
        if self.is_streaming:
            self.stop_stream()
        else:
            self.start_stream()

    def start_stream(self):
        if self.is_streaming or self.is_starting:
            return
            
        self.is_starting = True
        self.placeholder_label.setText("Đang kết nối màn hình...")
        self.placeholder_label.setStyleSheet("color: #6c7a89;")
        
        # Build scrcpy launch command
        app_config = config.load_config()
        scrcpy_path = config.get_executable_path("scrcpy")
        window_title = f"scrcpy_farm_{self.serial}"
        
        max_fps = str(app_config.get("max_fps", 10))
        bitrate = str(app_config.get("bitrate", "800K"))
        max_size = str(app_config.get("max_size", 480))
        
        args = [
            "-s", self.serial,
            "--window-title", window_title,
            "--window-borderless",
            "--max-fps", max_fps,
            "--video-bit-rate", bitrate,
            "--max-size", max_size,
            "--no-audio"
        ]
        
        if app_config.get("force_adb_forward", True):
            args.append("--force-adb-forward")
            
        if app_config.get("turn_screen_off", True):
            args.append("--turn-screen-off")
            
        if app_config.get("show_touches", False):
            args.append("--show-touches")
        if app_config.get("stay_awake", False):
            args.append("--stay-awake")
            
        logging.info(f"Khởi chạy scrcpy cho {self.serial}: {scrcpy_path} {' '.join(args)}")
        
        # Start scrcpy process
        self.scrcpy_process = QProcess(self)
        self.scrcpy_process.setProgram(scrcpy_path)
        self.scrcpy_process.setArguments(args)
        self.scrcpy_process.finished.connect(self._on_scrcpy_finished)
        
        self.scrcpy_process.start()
        
        self.find_start_time = time.time()
        self.find_timer.start()

    def _check_scrcpy_window(self):
        pid = 0
        if self.scrcpy_process:
            pid = self.scrcpy_process.processId()
            
        # 1. Tìm theo PID của tiến trình con
        hwnd = helpers.find_window_by_pid(pid, timeout=0.0) if pid > 0 else None
        
        # 2. Dự phòng: Tìm theo tiêu đề cửa sổ nếu PID chưa sẵn sàng hoặc bị lệch
        if not hwnd:
            window_title = f"scrcpy_farm_{self.serial}"
            hwnd = helpers.find_window_by_title(window_title, timeout=0.0)
        
        if hwnd:
            self.find_timer.stop()
            self.scrcpy_hwnd = hwnd
            
            # Tạo QWindow từ handle của scrcpy
            self.scrcpy_window = QWindow.fromWinId(self.scrcpy_hwnd)
            
            # Sử dụng QWidget.createWindowContainer nhúng cửa sổ an toàn chéo tiến trình
            self.embed_widget = QWidget.createWindowContainer(self.scrcpy_window, self.stream_container)
            self.embed_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.embed_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.embed_widget.installEventFilter(self)
            
            # Thêm container vào layout để Qt tự động quản lý kích thước và co giãn
            self.container_layout.addWidget(self.embed_widget)
            
            self.placeholder_label.hide()
            
            self.is_streaming = True
            self.is_starting = False
            self.retry_count = 0
            self.is_retrying = False
            
            self.on_stream_state_changed(self.serial, True)
            
            # Auto focus if sync mode is disabled
            main_win = self.window()
            if hasattr(main_win, "is_sync_enabled") and not main_win.is_sync_enabled:
                QTimer.singleShot(100, self.focus_device)
        else:
            # Check for timeout (20 seconds)
            if time.time() - self.find_start_time > 20.0:
                self.find_timer.stop()
                logging.error(f"Timeout tìm kiếm cửa sổ scrcpy cho {self.serial}")
                self._handle_launch_failure()

    def _on_scrcpy_finished(self, exit_code, exit_status):
        logging.warning(f"Tiến trình scrcpy của {self.serial} kết thúc (exit code: {exit_code})")
        if self.is_streaming:
            self._handle_unexpected_disconnect()
        elif self.is_starting:
            # scrcpy bi crash khi dang khoi chay
            self._handle_launch_failure()

    def trigger_queue_start(self):
        """Khởi chạy lại stream theo cách xếp hàng (staggered) thông qua GridView để tránh nghẽn USB/ADB."""
        grid = self._get_grid_view()
        if grid and hasattr(grid, "queue_stream_start"):
            grid.queue_stream_start(self.serial)
        else:
            self.start_stream()

    def _handle_launch_failure(self):
        self.is_starting = False
        self.stop_stream()
        
        if not self.is_absent and self.retry_count < self.max_retries:
            self.retry_count += 1
            self.is_retrying = True
            delay_ms = 3000
            logging.info(f"Thử lại kết nối {self.serial} sau {delay_ms/1000}s (Lần {self.retry_count}/{self.max_retries})")
            self.placeholder_label.setText(f"Lỗi kết nối! Đang thử lại...\n(Lần {self.retry_count}/{self.max_retries})")
            self.placeholder_label.setStyleSheet("color: #ff9f43;")
            self.placeholder_label.show()
            QTimer.singleShot(delay_ms, self.trigger_queue_start)
        else:
            self.placeholder_label.show()
            if self.is_absent:
                self.placeholder_label.setText("Mất kết nối - cần kiểm tra lại")
                self.placeholder_label.setStyleSheet("color: #ff4757;")
            else:
                self.placeholder_label.setText("Kết nối lỗi!\nNhấp để kết nối lại.")
                self.placeholder_label.setStyleSheet("color: #6c7a89;")
 
    def _handle_unexpected_disconnect(self):
        self.stop_stream()
        if not self.is_absent and self.retry_count < self.max_retries:
            self.retry_count += 1
            self.is_retrying = True
            delay_ms = 3000
            self.placeholder_label.setText(f"Mất kết nối! Đang thử lại...\n(Lần {self.retry_count}/{self.max_retries})")
            self.placeholder_label.setStyleSheet("color: #ff9f43;")
            self.placeholder_label.show()
            QTimer.singleShot(delay_ms, self.trigger_queue_start)
        else:
            self.placeholder_label.show()
            if self.is_absent:
                self.placeholder_label.setText("Mất kết nối - cần kiểm tra lại")
                self.placeholder_label.setStyleSheet("color: #ff4757;")
            else:
                self.placeholder_label.setText("Kết nối lỗi!\nNhấp để kết nối lại.")
                self.placeholder_label.setStyleSheet("color: #6c7a89;")

    def stop_stream(self):
        self.is_streaming = False
        self.is_starting = False
        self.find_timer.stop()
        
        # Terminate QProcess safely
        if self.scrcpy_process:
            self.scrcpy_process.finished.disconnect(self._on_scrcpy_finished)
            self.scrcpy_process.terminate()
            if not self.scrcpy_process.waitForFinished(1000):
                self.scrcpy_process.kill()
            self.scrcpy_process = None
            
        # Giải phóng widget container nhúng cũ
        if self.embed_widget:
            try:
                self.container_layout.removeWidget(self.embed_widget)
                self.embed_widget.deleteLater()
            except Exception:
                pass
            self.embed_widget = None
            
        self.scrcpy_hwnd = None
        
        # Restore placeholder
        self.placeholder_label.show()
        if self.is_absent:
            self.placeholder_label.setText("Mất kết nối - cần kiểm tra lại")
            self.placeholder_label.setStyleSheet("color: #ff4757;")
        else:
            self.placeholder_label.setText("Kết nối đã ngắt\nNhấp để kết nối lại")
            self.placeholder_label.setStyleSheet("color: #6c7a89;")
            
        self.on_stream_state_changed(self.serial, False)

    def _get_grid_view(self):
        p = self.parent()
        while p:
            if hasattr(p, "handle_card_click"):
                return p
            p = p.parent()
        return None

    def mousePressEvent(self, event: QMouseEvent):
        # Notify GridView this card is clicked (single selection)
        if event.button() == Qt.MouseButton.LeftButton:
            # Call parent grid selection logic
            grid = self._get_grid_view()
            if grid:
                grid.handle_card_click(self)
        super().mousePressEvent(event)

    def eventFilter(self, obj, event):
        embed_widget = getattr(self, "embed_widget", None)
        if embed_widget and obj == embed_widget:
            if event.type() in (QEvent.Type.FocusIn, QEvent.Type.MouseButtonPress):
                # Force Windows keyboard focus to scrcpy native window handle
                self.focus_device()
                
                # Also, notify GridView to handle card click selection
                grid = self._get_grid_view()
                if grid:
                    grid.handle_card_click(self)
        return super().eventFilter(obj, event)

    def cleanup(self):
        self.stop_stream()
        self.deleteLater()


class GridView(QScrollArea):
    def __init__(
        self, 
        parent: QWidget, 
        adb_handler: ADBHandler, 
        on_streams_updated: Callable[[List[str]], None],
        on_selection_changed: Optional[Callable[[List[str]], None]] = None
    ):
        super().__init__(parent)
        self.adb_handler = adb_handler
        self.on_streams_updated = on_streams_updated
        self.on_selection_changed = on_selection_changed
        
        self.cards: Dict[str, DeviceCard] = {}
        self._pending_streams: List[str] = []
        self._launching_streams = False
        
        self.custom_card_width = 200
        
        # Configure Scroll Area
        self.setWidgetResizable(True)
        self.setStyleSheet("background-color: #0c0d12; border: none;")
        
        # Grid container widget
        self.container = QWidget()
        self.container.setStyleSheet("background-color: #0c0d12;")
        self.grid_layout = QGridLayout(self.container)
        self.grid_layout.setContentsMargins(15, 15, 15, 15)
        self.grid_layout.setSpacing(16)
        
        self.setWidget(self.container)
        self.container.installEventFilter(self)
        
        # QRubberBand for selection marquee
        self.rubber_band = None
        self.drag_start_pos = QPoint()
        
        # Track last width/height to optimize resizing calls
        self.last_width = 0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() != self.last_width:
            self.last_width = self.width()
            self.rearrange_grid()

    def handle_card_click(self, clicked_card: DeviceCard):
        # Toggle selection on click (only for Slave cards)
        if not clicked_card.is_master:
            clicked_card.set_selected(not clicked_card.is_selected)
            self._dispatch_selection_change()
            
        # Focus on click if sync mode is disabled
        main_win = self.window()
        if hasattr(main_win, "is_sync_enabled") and not main_win.is_sync_enabled:
            clicked_card.focus_device()

    def eventFilter(self, obj, event):
        container = getattr(self, "container", None)
        if container and obj == container:
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.drag_start_pos = self.mapFrom(self.container, event.pos())
                    if not self.rubber_band:
                        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
                    self.rubber_band.setGeometry(QRect(self.drag_start_pos, QSize()))
                    self.rubber_band.show()
                    return True
            elif event.type() == QEvent.Type.MouseMove:
                if self.rubber_band and (event.buttons() & Qt.MouseButton.LeftButton):
                    curr_pos = self.mapFrom(self.container, event.pos())
                    self.rubber_band.setGeometry(QRect(self.drag_start_pos, curr_pos).normalized())
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease:
                if self.rubber_band:
                    self.rubber_band.hide()
                    sel_rect = self.rubber_band.geometry()
                    
                    for card in self.cards.values():
                        card_pos = card.mapTo(self, QPoint(0, 0))
                        card_rect = QRect(card_pos, card.size())
                        is_intersect = sel_rect.intersects(card_rect)
                        card.set_selected(is_intersect)
                        
                    self._dispatch_selection_change()
                    self.rubber_band = None
                    return True
        return super().eventFilter(obj, event)

    def get_selected_devices(self) -> List[str]:
        return [serial for serial, card in self.cards.items() if card.is_selected]

    def get_active_streams(self) -> List[str]:
        return [serial for serial, card in self.cards.items() if card.is_streaming]

    def get_card_widget(self, serial: str) -> Optional[QWidget]:
        card = self.cards.get(serial)
        if card:
            return card.stream_container
        return None

    def _dispatch_selection_change(self):
        if self.on_selection_changed:
            self.on_selection_changed(self.get_selected_devices())

    def update_devices(self, current_serials: List[str]):
        # 1. Mark offline devices absent
        for serial in list(self.cards.keys()):
            if serial not in current_serials:
                self.cards[serial].set_absent(True)
                
        # 2. Add new devices to grid
        new_serials = []
        for serial in current_serials:
            if serial not in self.cards:
                logging.info(f"Thêm thiết bị mới vào GridView: {serial}")
                card = DeviceCard(
                    self.container, 
                    serial, 
                    self.adb_handler, 
                    self._on_card_stream_state_changed
                )
                self.cards[serial] = card
                new_serials.append(serial)
            else:
                card = self.cards[serial]
                was_absent = card.is_absent
                card.set_absent(False)
                
                if not card.is_streaming and not card.is_starting and not card.is_retrying:
                    if was_absent:
                        card.retry_count = 0
                        new_serials.append(serial)
                    elif card.retry_count < card.max_retries:
                        new_serials.append(serial)
                        
        # 3. Rearrange grid
        self.rearrange_grid()
        
        # 4. Sequential launch of streams
        if new_serials:
            self._queue_staggered_streams(new_serials)

    def _queue_staggered_streams(self, serials: List[str]):
        for s in serials:
            if s not in self._pending_streams:
                self._pending_streams.append(s)
                
        if not self._launching_streams:
            self._launch_next_stream()

    def _launch_next_stream(self):
        self._launching_streams = True
        
        while self._pending_streams:
            serial = self._pending_streams.pop(0)
            card = self.cards.get(serial)
            if card and not card.is_streaming and not card.is_starting:
                card.start_stream()
                
                if self._pending_streams:
                    # Delay 1.5 seconds before launching next device stream
                    QTimer.singleShot(3000, self._launch_next_stream)
                    return
                else:
                    break
                    
        self._launching_streams = False

    def queue_stream_start(self, serial: str):
        """Thêm thiết bị vào hàng đợi khởi chạy so le (staggered)."""
        self._queue_staggered_streams([serial])

    def _on_card_stream_state_changed(self, serial: str, is_streaming: bool):
        active = self.get_active_streams()
        self.on_streams_updated(active)
        self._dispatch_selection_change()

    def rearrange_grid(self, force=False):
        width = self.viewport().width()
        if width < 100:
            return
            
        num_cards = len(self.cards)
        if num_cards == 0:
            # Dọn dẹp layout nếu không còn card nào
            for i in reversed(range(self.grid_layout.count())):
                item = self.grid_layout.itemAt(i)
                if item and item.widget():
                    self.grid_layout.removeWidget(item.widget())
            self.last_serials_sorted = []
            self.last_cols = 0
            return
            
        card_width = self.custom_card_width
        ratio = 2.1
        card_height = int(card_width * ratio) + 40
        
        spacing = 16
        cols = max(1, (width - spacing) // (card_width + spacing))
        cols = min(cols, num_cards)
        
        current_serials_sorted = sorted(self.cards.keys())
        
        # Tối ưu hóa: Nếu số cột và danh sách thiết bị không đổi, bỏ qua tính toán lại
        if not force and cols == getattr(self, "last_cols", 0) and current_serials_sorted == getattr(self, "last_serials_sorted", []):
            return
            
        self.last_cols = cols
        self.last_serials_sorted = current_serials_sorted
        
        # Chỉ xóa khỏi layout, KHÔNG gọi setParent(None) để tránh phá hủy cửa sổ nhúng chéo process
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                self.grid_layout.removeWidget(item.widget())
            
        for idx, serial in enumerate(current_serials_sorted):
            card = self.cards[serial]
            row = idx // cols
            col = idx % cols
            
            card.setFixedSize(card_width, card_height)
            self.grid_layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignCenter)

    def cleanup_all(self):
        for card in list(self.cards.values()):
            card.cleanup()
        self.cards.clear()
