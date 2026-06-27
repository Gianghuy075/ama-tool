import sys
import os
import threading
import time
import logging
import requests
from typing import List, Optional, Dict

# Add parent directory of RegisterBot_Package to sys.path so we can import config/gmail_otp/excel_handler
curr_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(curr_dir, "..", "..", "RegisterBot_Package"))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QTimer
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QApplication
from PyQt6.QtGui import QKeyEvent

from adb_handler import ADBHandler
from ui.sidebar import Sidebar
from ui.grid_view import GridView
from ui.overlay import TransparentOverlay
from utils import db_manager as db
from ui.proxy_manager import ProxyManagerWindow


class MainWindow(QMainWindow):
    # Signals for thread-safe UI updates from worker threads
    log_signal = pyqtSignal(str)
    stream_action_signal = pyqtSignal(str, bool)
    device_list_signal = pyqtSignal(list)
    scan_finished_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("GDP-tool-phone")
        self.resize(1100, 700)
        self.setMinimumSize(800, 600)
        
        self.adb_handler = ADBHandler()
        db.init_db()
        
        self.is_sync_enabled = False
        self.overlays: Dict[str, TransparentOverlay] = {}
        
        # Proxy configurations
        self.is_proxy_rotation_enabled = db.get_config("rotation_enabled", "0") == "1"
        self.proxy_rotation_interval = int(db.get_config("rotation_interval_mins", "10")) * 60
        self.api_rotation_link = db.get_config("api_link", "")
        self.last_rotation_time = time.time()
        
        # Start background threads
        self.is_monitoring_active = True
        threading.Thread(target=self._data_polling_loop, daemon=True).start()
        threading.Thread(target=self._proxy_rotation_loop, daemon=True).start()
        
        self.auto_scan_active = True
        self.scan_thread: Optional[threading.Thread] = None
        self._last_device_set: set = set() # Theo dõi device set để chỉ allocate proxy khi có thay đổi
        
        # Setup Central Widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # GridView (Left)
        self.grid_view = GridView(
            self.central_widget,
            self.adb_handler,
            on_streams_updated=self._on_streams_updated,
            on_selection_changed=self._on_selection_changed
        )
        self.main_layout.addWidget(self.grid_view, 1)
        
        # Sidebar (Right)
        self.sidebar = Sidebar(
            self.central_widget,
            on_scan_click=self.scan_devices,
            on_sync_toggle=self.toggle_sync,
            on_size_changed=self.change_card_size,
            on_proxy_click=self.open_proxy_manager,
            on_proxy_rotation_toggle=self.toggle_proxy_rotation,
            initial_proxy_rotation=self.is_proxy_rotation_enabled,
            on_register_click=self.start_registration_experiment
        )
        self.main_layout.addWidget(self.sidebar, 0)
        
        self.grid_view.custom_card_width = self.sidebar.app_config.get("card_width", 200)
        
        # Connect Thread Signals to slots
        self.log_signal.connect(self.sidebar.update_log_info)
        self.stream_action_signal.connect(self._handle_remote_stream_action)
        self.device_list_signal.connect(self._update_ui_device_list)
        self.scan_finished_signal.connect(self._async_scan_finished)
        
        # Connect ADB on background thread
        self.sidebar.update_log_info("Đang khởi động ADB Server...")
        threading.Thread(target=self._async_adb_connect, daemon=True).start()

    def _async_adb_connect(self):
        success = self.adb_handler.connect()
        if success:
            # We can connect signals or trigger methods safely using signal
            self.log_signal.emit("Kết nối ADB Server thành công.")
            self._on_adb_connected()
        else:
            self.log_signal.emit(
                "LỖI: Không kết nối được tới ADB Server!\n\n"
                "Vui lòng kiểm tra:\n"
                "1. Tệp adb.exe có nằm đúng thư mục BoxPhone của bạn không.\n"
                "2. Đường dẫn trong file config.json.\n\n"
                "Nhấp nút 'Quét Thiết Bị' để thử lại."
            )

    def _on_adb_connected(self):
        import api_server
        # Run FastAPI API Server in background thread
        threading.Thread(
            target=lambda: api_server.run_api_server(self, default_port=5000), 
            daemon=True
        ).start()
        
        self.start_auto_scan()

    def start_auto_scan(self):
        def scan_loop():
            logging.info("Bắt đầu luồng tự động quét thiết bị.")
            while self.auto_scan_active:
                if self.adb_handler.client:
                    try:
                        devices = self.adb_handler.get_connected_devices(force=True)
                        self.device_list_signal.emit(devices)
                    except Exception as e:
                        logging.error(f"Lỗi trong luồng tự động quét thiết bị: {e}")
                time.sleep(20.0) # Chu kỳ 20s giảm tải USB/ADB bus (tăng từ 10s)
                
        self.scan_thread = threading.Thread(target=scan_loop, daemon=True)
        self.scan_thread.start()

    def scan_devices(self):
        if not self.adb_handler.client:
            self.sidebar.update_log_info("Thử kết nối lại tới ADB Server...")
            threading.Thread(target=self._async_adb_connect, daemon=True).start()
            return
            
        self.sidebar.update_log_info("Đang quét thiết bị...")
        
        def async_scan():
            try:
                devices = self.adb_handler.get_connected_devices()
                self.scan_finished_signal.emit(devices)
            except Exception as e:
                logging.error(f"Lỗi quét thiết bị thủ công: {e}")
                self.log_signal.emit("Lỗi quét thiết bị!")
                
        threading.Thread(target=async_scan, daemon=True).start()

    def _async_scan_finished(self, devices: List[str]):
        self._update_ui_device_list(devices)
        
        # Khởi chạy so le (staggered) các thiết bị chưa stream thay vì gọi đồng loạt gây đơ ứng dụng
        inactive_serials = []
        for serial, card in self.grid_view.cards.items():
            if not card.is_streaming and not card.is_starting:
                card.retry_count = 0
                card.is_retrying = False
                inactive_serials.append(serial)
                
        if inactive_serials:
            self.grid_view._queue_staggered_streams(inactive_serials)
                
        self.sidebar.update_log_info(f"Đã hoàn thành quét thủ công.\nPhát hiện {len(devices)} thiết bị.")

    def _update_ui_device_list(self, devices: List[str]):
        self.grid_view.update_devices(devices)
        active_streams = self.grid_view.get_active_streams()
        self.sidebar.update_device_list(devices, active_streams)
        
        # Chỉ chạy allocate_proxies khi danh sách devices thay đổi (để tránh ADB commands thừa mỗi chu kỳ scan)
        current_set = set(devices)
        if current_set != self._last_device_set:
            self._last_device_set = current_set
            self.allocate_proxies_to_devices(devices)
        
        if self.is_sync_enabled:
            self.update_sync_overlays()

    def _on_streams_updated(self, active_streams: List[str]):
        devices = list(self.grid_view.cards.keys())
        self.sidebar.update_device_list(devices, active_streams)
        
        if self.is_sync_enabled:
            self.update_sync_overlays()

    def _on_selection_changed(self, selected_devices: List[str]):
        devices = list(self.grid_view.cards.keys())
        active_streams = self.grid_view.get_active_streams()
        
        self.sidebar.update_log_info(
            f"Tổng thiết bị USB: {len(devices)}\n"
            f"Đang stream màn hình: {len(active_streams)}\n"
            f"Đang chọn điều khiển: {len(selected_devices)} máy"
        )
        
        if self.is_sync_enabled:
            self.update_sync_overlays()

    def toggle_sync(self, is_enabled: bool):
        self.is_sync_enabled = is_enabled
        self.update_sync_overlays()
        if not is_enabled:
            self.sidebar.sync_switch.setChecked(False)
            logging.info("Đã tắt chế độ đồng bộ.")

    def toggle_proxy_rotation(self, is_enabled: bool):
        self.is_proxy_rotation_enabled = is_enabled
        db.set_config("rotation_enabled", "1" if is_enabled else "0")
        logging.info(f"Đã {'bật' if is_enabled else 'tắt'} tự động xoay proxy.")
        if is_enabled:
            self.last_rotation_time = time.time()
            self.allocate_proxies_to_devices(list(self.grid_view.cards.keys()))
        else:
            # Clear proxy on all active devices once when disabled
            active_serials = list(self.grid_view.cards.keys())
            for serial in active_serials:
                self.adb_handler.clear_system_proxy(serial)

    def _handle_remote_stream_action(self, serial: str, start: bool):
        card = self.grid_view.cards.get(serial)
        if card:
            if start:
                card.start_stream()
            else:
                card.stop_stream()

    def _handle_sync_tap_from_device(self, source_serial: str, x_pct: float, y_pct: float):
        if not self.is_sync_enabled:
            return
            
        group = self.grid_view.get_selected_devices()
        if source_serial not in group:
            return
            
        res = self.adb_handler.get_device_resolution(source_serial)
        self.adb_handler.tap(source_serial, int(x_pct * res[0]), int(y_pct * res[1]))
        
        for serial in group:
            if serial != source_serial:
                res_target = self.adb_handler.get_device_resolution(serial)
                self.adb_handler.tap(serial, int(x_pct * res_target[0]), int(y_pct * res_target[1]))

    def _handle_sync_swipe_from_device(self, source_serial: str, x1_pct: float, y1_pct: float, x2_pct: float, y2_pct: float, duration_ms: int):
        if not self.is_sync_enabled:
            return
            
        group = self.grid_view.get_selected_devices()
        if source_serial not in group:
            return
            
        w_src, h_src = self.adb_handler.get_device_resolution(source_serial)
        self.adb_handler.swipe(source_serial, int(x1_pct * w_src), int(y1_pct * h_src), int(x2_pct * w_src), int(y2_pct * h_src), duration_ms)
        
        for serial in group:
            if serial != source_serial:
                w, h = self.adb_handler.get_device_resolution(serial)
                self.adb_handler.swipe(serial, int(x1_pct * w), int(y1_pct * h), int(x2_pct * w), int(y2_pct * h), duration_ms)

    def _handle_sync_key_from_device(self, source_serial: str, event: QKeyEvent):
        if not self.is_sync_enabled:
            return
            
        group = self.grid_view.get_selected_devices()
        if source_serial not in group:
            return
            
        key = event.key()
        char = event.text()
        
        # Ctrl+V Clipboard synchronization
        is_ctrl = (event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        if is_ctrl and key == Qt.Key.Key_V:
            clipboard = QApplication.clipboard()
            clipboard_text = clipboard.text()
            if clipboard_text:
                logging.info(f"[Sync Clipboard] Dán văn bản từ clipboard: {clipboard_text}")
                for serial in group:
                    self.adb_handler.input_text(serial, clipboard_text)
            return
            
        special_keys = {
            Qt.Key.Key_Backspace: 67,   # KEYCODE_DEL
            Qt.Key.Key_Return: 66,      # KEYCODE_ENTER
            Qt.Key.Key_Enter: 66,
            Qt.Key.Key_Tab: 61,         # KEYCODE_TAB
            Qt.Key.Key_Space: 62,       # KEYCODE_SPACE
            Qt.Key.Key_Escape: 111,     # KEYCODE_ESCAPE
            Qt.Key.Key_Left: 21,        # KEYCODE_DPAD_LEFT
            Qt.Key.Key_Right: 22,       # KEYCODE_DPAD_RIGHT
            Qt.Key.Key_Up: 19,          # KEYCODE_DPAD_UP
            Qt.Key.Key_Down: 20,        # KEYCODE_DPAD_DOWN
            Qt.Key.Key_Delete: 112,     # KEYCODE_FORWARD_DEL
            Qt.Key.Key_Home: 122,       # KEYCODE_MOVE_HOME
            Qt.Key.Key_End: 123,        # KEYCODE_MOVE_END
        }
        
        if key in special_keys:
            keycode = special_keys[key]
            for serial in group:
                self.adb_handler.press_key(serial, keycode)
        elif char and len(char) == 1 and char.isprintable():
            for serial in group:
                self.adb_handler.input_text(serial, char)

    def update_sync_overlays(self):
        if not self.is_sync_enabled:
            for serial, overlay in list(self.overlays.items()):
                try:
                    overlay.close()
                except Exception:
                    pass
            self.overlays.clear()
            return

        group = self.grid_view.get_selected_devices()
        active_streams = self.grid_view.get_active_streams()
        group = [s for s in group if s in active_streams]

        # Close overlays for devices no longer in group
        for serial in list(self.overlays.keys()):
            if serial not in group:
                try:
                    self.overlays[serial].close()
                except Exception:
                    pass
                del self.overlays[serial]

        # Position or create overlays for devices in group
        for serial in group:
            master_widget = self.grid_view.get_card_widget(serial)
            if master_widget:
                if serial not in self.overlays:
                    logging.info(f"Kích hoạt Overlay đồng bộ trên thiết bị: {serial}")
                    self.overlays[serial] = TransparentOverlay(
                        parent_widget=master_widget,
                        on_tap_callback=lambda x, y, s=serial: self._handle_sync_tap_from_device(s, x, y),
                        on_swipe_callback=lambda x1, y1, x2, y2, dur, s=serial: self._handle_sync_swipe_from_device(s, x1, y1, x2, y2, dur),
                        on_key_callback=lambda e, s=serial: self._handle_sync_key_from_device(s, e)
                    )
                else:
                    self.overlays[serial].sync_position()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.update_sync_overlays()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_sync_overlays()

    def change_card_size(self, size: int):
        self.grid_view.custom_card_width = size
        self.grid_view.rearrange_grid(force=True)
        if self.is_sync_enabled:
            # Sync positions with small delay to let layout settle
            QTimer.singleShot(50, self.update_sync_overlays)

    def open_proxy_manager(self):
        dialog = ProxyManagerWindow(self, self.adb_handler)
        dialog.exec()

    def allocate_proxies_to_devices(self, connected_serials: List[str]):
        if not self.is_proxy_rotation_enabled:
            return
        all_proxies = db.get_all_proxies()
        for p in all_proxies:
            assigned = p["assigned_phone_id"]
            if assigned and assigned not in connected_serials:
                db.release_proxy(assigned)
                
        usages = db.get_all_data_usages()
        blocked_serials = [u["phone_id"] for u in usages if u["is_blocked"] == 1]
        
        for serial in connected_serials:
            if serial in blocked_serials:
                self.adb_handler.set_system_proxy(serial, "127.0.0.1", 9999)
                continue
                
            proxy = db.allocate_proxy(serial, connected_serials)
            if proxy:
                self.adb_handler.set_system_proxy(serial, proxy["ip"], proxy["port"])
            else:
                self.adb_handler.clear_system_proxy(serial)

    def rotate_device_ip(self, serial: str, force_api_call: bool = False) -> bool:
        if self.api_rotation_link and (force_api_call or db.get_config("mode", "static") == "dynamic"):
            try:
                requests.get(self.api_rotation_link, timeout=5)
                logging.info(f"Đã gọi API xoay IP: {self.api_rotation_link}")
            except Exception as e:
                logging.warning(f"Lỗi gọi API xoay IP cho {serial}: {e}")
                
        mode = db.get_config("mode", "static")
        if mode == "dynamic":
            db.release_proxy(serial)
            
        active_serials = list(self.grid_view.cards.keys())
        proxy = db.allocate_proxy(serial, active_serials)
        
        if proxy:
            self.adb_handler.set_system_proxy(serial, proxy["ip"], proxy["port"])
            return True
        else:
            self.adb_handler.clear_system_proxy(serial)
            return False

    def _data_polling_loop(self):
        logging.info("Khởi chạy luồng Data Polling ngầm.")
        while self.is_monitoring_active:
            if self.is_proxy_rotation_enabled and self.adb_handler.client:
                try:
                    # Lấy danh sách thiết bị đang stream hoạt động từ GridView thay vì chạy adb devices mới
                    connected = self.grid_view.get_active_streams()
                    for serial in connected:
                        card = self.grid_view.cards.get(serial)
                        if card and not card.is_absent:
                            raw_bytes = self.adb_handler.read_network_bytes(serial)
                            if raw_bytes > 0:
                                total_used, is_blocked = db.update_data_usage(serial, raw_bytes)
                                
                                if is_blocked:
                                    self.adb_handler.set_system_proxy(serial, "127.0.0.1", 9999)
                                    # Ngắt stream an toàn qua Qt signal từ background thread
                                    self.stream_action_signal.emit(serial, False)
                except Exception as e:
                    logging.error(f"Lỗi trong luồng ngầm Data Polling: {e}")
            time.sleep(120.0) # Tăng từ 30s lên 120s (2 phút) để giảm tải ADB đáng kể

    def _proxy_rotation_loop(self):
        logging.info("Khởi chạy luồng Proxy Rotation ngầm.")
        while self.is_monitoring_active:
            if self.is_proxy_rotation_enabled:
                elapsed = time.time() - self.last_rotation_time
                if elapsed >= self.proxy_rotation_interval:
                    logging.info("Kích hoạt chu kỳ tự động xoay IP.")
                    if self.api_rotation_link:
                        try:
                            requests.get(self.api_rotation_link, timeout=5)
                            logging.info(f"Gọi API xoay IP thành công: {self.api_rotation_link}")
                        except Exception as e:
                            logging.warning(f"Lỗi gọi API xoay IP: {e}")
                            
                    active_serials = list(self.grid_view.cards.keys())
                    mode = db.get_config("mode", "static")
                    if mode == "dynamic":
                        for s in active_serials:
                            db.release_proxy(s)
                            
                    # We can execute allocate_proxies_to_devices by calling it.
                    # It reads from database and runs adb commands (which are submitted to a ThreadPoolExecutor inside adb_handler, so it is safe to call from background thread!)
                    self.allocate_proxies_to_devices(active_serials)
                    self.last_rotation_time = time.time()
            time.sleep(30.0) # Tăng từ 10s lên 30s để giảm tải

    def start_registration_experiment(self):
        """Khởi chạy đăng ký tự động trên các thiết bị đang online/được chọn."""
        # Lấy danh sách thiết bị được chọn hoặc online
        selected_devices = self.grid_view.get_selected_devices()
        if not selected_devices:
            # Fallback về toàn bộ thiết bị đang stream/online
            selected_devices = list(self.grid_view.cards.keys())

        if not selected_devices:
            self.log_signal.emit("Không tìm thấy thiết bị online nào! Hãy kết nối thiết bị và quét lại.")
            return

        self.log_signal.emit(f"Chuẩn bị chạy đăng ký trên {len(selected_devices)} thiết bị: {selected_devices}")
        threading.Thread(
            target=self._run_registration_experiment,
            args=(selected_devices,),
            daemon=True
        ).start()

    def _run_registration_experiment(self, online_devices: List[str]):
        import queue
        from src.config import CONFIG
        from src.excel_handler import ExcelHandler

        # Xác định đường dẫn file accounts.xlsx
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        pkg_accounts_path = os.path.abspath(os.path.join(curr_dir, "..", "..", "RegisterBot_Package", "data", "accounts.xlsx"))
        local_accounts_path = os.path.abspath(os.path.join(curr_dir, "data", "accounts.xlsx"))

        accounts_path = pkg_accounts_path
        if not os.path.exists(accounts_path):
            accounts_path = local_accounts_path

        if not os.path.exists(accounts_path):
            self.log_signal.emit(f"LỖI: Không tìm thấy file accounts.xlsx tại {accounts_path}")
            return

        try:
            excel = ExcelHandler(accounts_path)
            rows = excel.read_rows()
        except Exception as e:
            self.log_signal.emit(f"LỖI: Đọc file Excel thất bại: {e}")
            return

        if not rows:
            self.log_signal.emit("LỖI: accounts.xlsx không chứa tài khoản nào.")
            return

        self.log_signal.emit(f"Đã đọc {len(rows)} tài khoản từ Excel. Phân phối sang {len(online_devices)} máy.")

        # Đưa accounts vào hàng đợi thread-safe
        q = queue.Queue()
        for row in rows:
            q.put(row)

        results = []
        results_lock = threading.Lock()
        active_workers = len(online_devices)
        worker_threads = []

        def worker(serial: str):
            device = self.adb_handler.device_cache.get(serial)
            if not device:
                self.log_signal.emit(f"[{serial}] LỖI: Thiết bị không có trong cache.")
                return

            self.log_signal.emit(f"[{serial}] Worker đăng ký đã khởi động.")

            while not q.empty():
                try:
                    row = q.get_nowait()
                except queue.Empty:
                    break

                self.log_signal.emit(f"[{serial}] Bắt đầu đăng ký cho: {row['email']}")
                res = self._execute_registration_flow_direct(device, serial, row)
                
                with results_lock:
                    results.append(res)

                delay = CONFIG.get("delay_between_accounts", 3)
                if delay > 0:
                    time.sleep(delay)

            self.log_signal.emit(f"[{serial}] Worker hoàn thành.")

        for serial in online_devices:
            t = threading.Thread(target=worker, args=(serial,), daemon=True)
            t.start()
            worker_threads.append(t)

        # Chờ các thread hoàn thành
        for t in worker_threads:
            t.join()

        # Lưu kết quả
        try:
            output_path = accounts_path.replace("accounts.xlsx", "results.xlsx")
            excel.write_results(results, output_path)
            self.log_signal.emit(f"✅ Hoàn tất! Kết quả được lưu tại: {output_path}")
        except Exception as e:
            self.log_signal.emit(f"LỖI: Không thể ghi file kết quả: {e}")

    def _execute_registration_flow_direct(self, device, serial: str, row: dict) -> dict:
        import random
        from src.config import CONFIG
        from src.gmail_otp import GmailOTPReader
        from datetime import datetime
        import re

        if not row.get("name") or not str(row["name"]).strip():
            row["name"] = "User Test"

        result = {
            "name": row["name"],
            "email": row["email"],
            "password": row.get("password", ""),
            "proxy": "NO_PROXY",
            "device": serial,
            "status": "FAILED",
            "note": "",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Khởi tạo trước try để khối finally luôn có biến này (tránh NameError che lỗi gốc - ISSUE-004)
        chosen_browser = "com.android.chrome"

        try:
            # Luôn dùng Chrome để tránh Firefox/Brave tự xoay ngang trên Boxphone.
            self.log_signal.emit(f"[{serial}] Trình duyệt cố định: {chosen_browser}")
            device.shell("settings put system accelerometer_rotation 0")
            device.shell("settings put system user_rotation 0")
            device.shell("wm user-rotation lock 0")
            self.log_signal.emit(f"[{serial}] Đã khóa hướng màn hình dọc (portrait).")

            # ── Bước 1: Reset trình duyệt & Mở App ──────────────────
            self.log_signal.emit(f"[{serial}] Bước 1: Reset trình duyệt {chosen_browser}...")
            device.shell(f"pm clear {chosen_browser}")
            time.sleep(1.0)
            device.shell(f"am force-stop {chosen_browser}")
            time.sleep(1.0)

            self.log_signal.emit(f"[{serial}] Mở app {chosen_browser}...")
            device.shell(f"monkey -p {chosen_browser} -c android.intent.category.LAUNCHER 1")
            
            wait_app = random.uniform(3.0, 4.5)
            self.log_signal.emit(f"[{serial}] Chờ app tải xong: {wait_app:.2f}s")
            time.sleep(wait_app)
            # Chrome có thể yêu cầu xoay ngang khi vừa khởi động, nên khóa lại sau khi app đã mở.
            device.shell("wm user-rotation lock 0")
            self.log_signal.emit(f"[{serial}] Khóa lại portrait sau khi Chrome mở.")

            # ── Bước 2: Điều hướng đến Website ─────────────────────
            target_url = CONFIG.get("xiaowei", {}).get("default_experiment_url", "https://example.com/register")
            self.log_signal.emit(f"[{serial}] Bước 2: Điều hướng đến {target_url}...")
            
            url_to_type = f"{target_url}\n"
            for char in url_to_type:
                self.adb_handler.input_text(serial, char)
                time.sleep(random.uniform(0.07, 0.22))

            wait_load = random.uniform(4.0, 5.5)
            self.log_signal.emit(f"[{serial}] Chờ trang web tải xong: {wait_load:.2f}s")
            time.sleep(wait_load)

            # Helper for random offset tap
            def get_bbox_click(x_min, x_max, y_min, y_max):
                return random.randint(x_min, x_max), random.randint(y_min, y_max)

            # Helper for slow typing with delay
            def slow_type(text):
                for char in text:
                    self.adb_handler.input_text(serial, char)
                    time.sleep(random.uniform(0.07, 0.22))

            # ── Bước 3: Điền Form đăng ký (Tên, Email) ───────────────
            self.log_signal.emit(f"[{serial}] Bước 3: Click Create Account...")
            # Click vào tọa độ ngẫu nhiên trong vùng nút Create Account (Vùng X: 400 -> 600, Y: 1100 -> 1200)
            click_x, click_y = get_bbox_click(400, 600, 1100, 1200)
            self.adb_handler.tap(serial, click_x, click_y)
            time.sleep(2.0)

            # Nhập Email từng ký tự phím chậm
            self.log_signal.emit(f"[{serial}] Nhập email: {row['email']}...")
            slow_type(row["email"])
            time.sleep(1.0)

            # Click nút Verify Email bằng tọa độ lệch tâm (480-520, 1330-1370)
            verify_x, verify_y = get_bbox_click(480, 520, 1330, 1370)
            self.log_signal.emit(f"[{serial}] Click nút Verify Email tại ({verify_x}, {verify_y})...")
            
            # Ghi nhận thời điểm bấm "Gửi OTP" để Layer 2 Gmail filter hoạt động chính xác
            sent_otp_time = time.time()
            self.adb_handler.tap(serial, verify_x, verify_y)

            # ── Bước 4: Chờ và Quét OTP từ Mail Master ─────────────
            self.log_signal.emit(f"[{serial}] Bước 4: Quét OTP từ Gmail (3-layer filter)...")
            gmail = GmailOTPReader(
                email=CONFIG["gmail_address"],
                password=CONFIG["gmail_app_password"],
                imap_server=CONFIG["imap_server"],
            )

            # Quét Gmail qua IMAP với chu kỳ 3 giây
            otp = gmail.fetch_otp(
                row["email"],
                wait_seconds=CONFIG["otp_wait_seconds"],
                poll_interval=3,
                sent_otp_time=sent_otp_time
            )

            if not otp:
                result["note"] = "Không nhận được OTP từ Gmail"
                self.log_signal.emit(f"[{serial}] ❌ Không tìm thấy OTP cho {row['email']}")
                return result

            self.log_signal.emit(f"[{serial}] Bắt khớp OTP thành công: {otp}")

            # ── Bước 5: Độ trễ suy nghĩ & Nhập OTP hoàn tất ──────────
            thinking = random.uniform(1.5, 3.0)
            self.log_signal.emit(f"[{serial}] Bước 5: Độ trễ suy nghĩ {thinking:.2f}s...")
            time.sleep(thinking)

            # Nhập OTP từng ký tự
            self.log_signal.emit(f"[{serial}] Nhập mã OTP...")
            slow_type(otp)

            post_typing = random.uniform(1.0, 1.8)
            self.log_signal.emit(f"[{serial}] Chờ sau gõ: {post_typing:.2f}s")
            time.sleep(post_typing)

            # Click nút xác nhận cuối cùng (giả định tâm là 500, 1500)
            confirm_x, confirm_y = get_bbox_click(480, 520, 1480, 1520)
            self.log_signal.emit(f"[{serial}] Click xác nhận cuối tại ({confirm_x}, {confirm_y})...")
            self.adb_handler.tap(serial, confirm_x, confirm_y)

            # Đợi 5 giây và chụp ảnh màn hình
            time.sleep(5.0)
            screenshot_dir = CONFIG.get("xiaowei", {}).get("screenshot_dir", "data/screenshots")
            os.makedirs(screenshot_dir, exist_ok=True)
            save_path = os.path.join(screenshot_dir, f"{serial}_{row['email'].replace('@', '_')}.png")
            
            result_bytes = device.screencap()
            with open(save_path, "wb") as f:
                f.write(result_bytes)

            result["status"] = "SUCCESS"
            result["note"] = "Đăng ký thành công"
            self.log_signal.emit(f"[{serial}] ✅ ĐĂNG KÝ THÀNH CÔNG: {row['email']}")

        except Exception as e:
            result["note"] = f"Lỗi: {str(e)}"
            self.log_signal.emit(f"[{serial}] ❌ Lỗi: {e}")
            logging.error(f"Lỗi đăng ký {serial}: {e}", exc_info=True)

        finally:
            # Tắt app
            try:
                device.shell(f"am force-stop {chosen_browser}")
            except Exception:
                pass

        return result

    def closeEvent(self, event):

        logging.info("Đang tắt ứng dụng và dọn dẹp tài nguyên...")
        
        self.auto_scan_active = False
        self.is_monitoring_active = False
        
        self.is_sync_enabled = False
        self.update_sync_overlays()
            
        self.grid_view.cleanup_all()
        self.adb_handler.shutdown()
        
        super().closeEvent(event)
