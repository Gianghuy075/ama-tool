import re
import logging
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple, Optional
from ppadb.client import Client as AdbClient
from ppadb.device import Device

import config

# Cấu hình log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ADBHandler:
    def __init__(self):
        self.adb_path = config.get_executable_path("adb")
        self.client: Optional[AdbClient] = None
        self.executor = ThreadPoolExecutor(max_workers=5) # Giới hạn 5 workers để tránh quá tải USB/ADB bus
        self.device_cache: Dict[str, Device] = {} # Lưu cache đối tượng Device theo Serial
        self.resolutions: Dict[str, Tuple[int, int]] = {} # Lưu cache độ phân giải (width, height)
        self.last_reconnect_times: Dict[str, float] = {} # Lưu thời điểm reconnect gần nhất để tránh spam
        self._adb_lock = threading.Lock() # Lock để giãn cách lệnh ADB, tránh bão USB
        self._cached_serials: List[str] = [] # Cache kết quả scan devices
        self._cache_time: float = 0.0 # Thời điểm scan gần nhất
        self._cache_ttl: float = 5.0 # Chỉ scan lại sau 5 giây

    def start_server(self) -> bool:
        """Khởi chạy ADB Server cục bộ nếu chưa chạy."""
        try:
            logging.info(f"Đang khởi động ADB server từ: {self.adb_path}")
            # Chạy adb start-server ẩn cửa sổ console
            import os
            creationflags = 0x08000000 if os.name == 'nt' else 0
            result = subprocess.run(
                [self.adb_path, "start-server"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                logging.info("Khởi động ADB Server thành công.")
                return True
            else:
                logging.error(f"Khởi động ADB Server thất bại: {result.stderr}")
                return False
        except Exception as e:
            logging.error(f"Lỗi khi cố khởi động ADB server: {e}")
            return False

    def connect(self) -> bool:
        """Kết nối tới ADB Client."""
        self.start_server()
        try:
            self.client = AdbClient(host="127.0.0.1", port=5037)
            # Kiểm tra kết nối thử bằng cách gọi version
            version = self.client.version()
            logging.info(f"Đã kết nối tới ADB Server. Phiên bản: {version}")
            return True
        except Exception as e:
            logging.error(f"Không thể kết nối tới ADB Client: {e}")
            self.client = None
            return False

    def reconnect_device(self, serial: str):
        """Thử kết nối lại thiết bị ở trạng thái offline từ phía thiết bị (device-side)."""
        try:
            import os
            import time
            now = time.time()
            # Giới hạn thời gian giữa các lần reconnect tối thiểu 15 giây để tránh quá tải
            last_time = self.last_reconnect_times.get(serial, 0.0)
            if now - last_time < 15.0:
                return
            self.last_reconnect_times[serial] = now
            
            creationflags = 0x08000000 if os.name == 'nt' else 0
            logging.info(f"Phát hiện thiết bị offline. Đang gửi lệnh reconnect device: {serial}")
            subprocess.run(
                [self.adb_path, "-s", serial, "reconnect", "device"],
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
        except Exception as e:
            logging.warning(f"Lỗi khi tự động gửi lệnh reconnect device tới thiết bị {serial}: {e}")

    def reconnect_offline_devices(self):
        """Khôi phục nhanh tất cả các thiết bị offline bằng lệnh adb reconnect offline với giới hạn tần suất."""
        try:
            import os
            import time
            now = time.time()
            # Giới hạn gọi adb reconnect offline tối đa 1 lần mỗi 10 giây để tránh quá tải
            last_time = getattr(self, "_last_global_reconnect", 0.0)
            if now - last_time < 10.0:
                return
            self._last_global_reconnect = now
            
            creationflags = 0x08000000 if os.name == 'nt' else 0
            logging.info("Phát hiện thiết bị offline. Đang gửi lệnh khôi phục nhanh: adb reconnect offline")
            subprocess.run(
                [self.adb_path, "reconnect", "offline"],
                creationflags=creationflags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5
            )
        except Exception as e:
            logging.warning(f"Lỗi khi gửi lệnh adb reconnect offline: {e}")

    def get_connected_devices(self, force: bool = False) -> List[str]:
        """Quét và lấy danh sách Serial Number của các thiết bị đang kết nối ở trạng thái online (device) qua CLI.
        Sử dụng cache 5 giây để tránh gọi adb devices subprocess liên tục gây quá tải USB bus."""
        import os
        import time as _time
        
        # Trả về cache nếu chưa hết TTL (tránh gọi adb devices quá thường xuyên)
        now = _time.time()
        if not force and (now - self._cache_time) < self._cache_ttl and self._cached_serials:
            return list(self._cached_serials)
        
        creationflags = 0x08000000 if os.name == 'nt' else 0
        try:
            # Chạy lệnh adb devices nhanh để lấy trạng thái tất cả thiết bị chỉ trong 1 request
            result = subprocess.run(
                [self.adb_path, "devices"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
                text=True,
                timeout=5
            )
            
            current_serials = []
            new_cache = {}
            
            for line in result.stdout.splitlines():
                if not line.strip() or line.startswith("List of devices"):
                    continue
                parts = line.split()
                if len(parts) == 2:
                    serial, state = parts[0], parts[1]
                    if state == "device":
                        current_serials.append(serial)
                        # Đảm bảo client của ppadb được kết nối
                        if not self.client:
                            self.connect()
                        if self.client:
                            # Khởi tạo đối tượng Device của ppadb để giữ tính tương thích
                            new_cache[serial] = Device(self.client, serial)
                    elif state == "offline":
                        # Kích hoạt khôi phục nhanh toàn bộ thiết bị offline
                        self.executor.submit(self.reconnect_offline_devices)
                            
            self.device_cache = new_cache
            # Cập nhật cache
            self._cached_serials = list(current_serials)
            self._cache_time = now
            return current_serials
        except Exception as e:
            logging.error(f"Lỗi khi quét danh sách thiết bị ADB: {e}")
            return list(self._cached_serials) if self._cached_serials else []

    def get_device_resolution(self, serial: str) -> Tuple[int, int]:
        """
        Lấy độ phân giải thực tế (Width, Height) của thiết bị.
        Sử dụng cache nếu đã lấy trước đó.
        """
        if serial in self.resolutions:
            return self.resolutions[serial]
            
        device = self.device_cache.get(serial)
        if not device:
            return (1080, 1920) # Trả về mặc định nếu không tìm thấy thiết bị
            
        try:
            # Chạy lệnh wm size qua adb shell
            res_str = device.shell("wm size")
            # Kết quả mẫu: "Physical size: 1080x2400" hoặc "Physical size: 1080x1920\nOverride size: 720x1280"
            # Ta ưu tiên lấy "Override size" nếu có, nếu không lấy "Physical size"
            override_match = re.search(r"Override size:\s*(\d+)x(\d+)", res_str)
            if override_match:
                w, h = int(override_match.group(1)), int(override_match.group(2))
            else:
                physical_match = re.search(r"Physical size:\s*(\d+)x(\d+)", res_str)
                if physical_match:
                    w, h = int(physical_match.group(1)), int(physical_match.group(2))
                else:
                    w, h = 1080, 1920 # Mặc định
                    
            self.resolutions[serial] = (w, h)
            logging.info(f"Thiết bị {serial} có độ phân giải: {w}x{h}")
            return (w, h)
        except Exception as e:
            logging.error(f"Lỗi khi lấy độ phân giải của thiết bị {serial}: {e}")
            return (1080, 1920)

    def _execute_shell(self, device: Device, cmd: str):
        """Hàm nội bộ thực hiện lệnh shell ADB với rate limiting và timeout để tránh quá tải."""
        try:
            # Rate limiting: giãn cách tối thiểu 100ms giữa các lệnh ADB để tránh bão USB
            with self._adb_lock:
                import time as _time
                _time.sleep(0.1)
            device.shell(cmd, timeout=10) # Timeout 10 giây tránh thread treo vĩnh viễn khi device offline
        except Exception as e:
            logging.warning(f"Lỗi thực thi lệnh '{cmd}' trên thiết bị {device.serial} (có thể đã ngắt kết nối): {e}")

    def tap(self, serial: str, x: int, y: int):
        """Gửi sự kiện Tap (Click) đến một thiết bị chạy bất đồng bộ."""
        device = self.device_cache.get(serial)
        if device:
            cmd = f"input tap {x} {y}"
            self.executor.submit(self._execute_shell, device, cmd)

    def swipe(self, serial: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """Gửi sự kiện Swipe (Vuốt) đến một thiết bị chạy bất đồng bộ."""
        device = self.device_cache.get(serial)
        if device:
            cmd = f"input swipe {x1} {y1} {x2} {y2} {duration_ms}"
            self.executor.submit(self._execute_shell, device, cmd)

    def sync_tap(self, master_serial: str, slave_serials: List[str], x_percent: float, y_percent: float):
        """
        Đồng bộ thao tác click chuột.
        Nhận vào tỷ lệ phần trăm (x_percent, y_percent) từ màn hình Master,
        sau đó quy đổi và gửi lệnh tap tới Master và các Slave.
        """
        all_targets = [master_serial] + slave_serials
        for serial in all_targets:
            w, h = self.get_device_resolution(serial)
            x_target = int(x_percent * w)
            y_target = int(y_percent * h)
            self.tap(serial, x_target, y_target)

    def sync_swipe(self, master_serial: str, slave_serials: List[str], 
                   x1_percent: float, y1_percent: float, 
                   x2_percent: float, y2_percent: float, duration_ms: int):
        """
        Đồng bộ thao tác vuốt chuột.
        Quy đổi tỷ lệ phần trăm tọa độ bắt đầu và kết thúc rồi gửi swipe tới Master và các Slave.
        """
        all_targets = [master_serial] + slave_serials
        for serial in all_targets:
            w, h = self.get_device_resolution(serial)
            x1_target = int(x1_percent * w)
            y1_target = int(y1_percent * h)
            x2_target = int(x2_percent * w)
            y2_target = int(y2_percent * h)
            self.swipe(serial, x1_target, y1_target, x2_target, y2_target, duration_ms)
            
    def input_text(self, serial: str, text: str):
        """Giả lập nhập văn bản (text) trên thiết bị Android."""
        device = self.device_cache.get(serial)
        if device:
            # Thoát các ký tự đặc biệt của shell để tránh lỗi cú pháp
            # Chuyển khoảng trắng thành %s cho ADB nhận diện đúng
            escaped_text = ""
            for char in text:
                if char == " ":
                    escaped_text += "%s"
                elif char in ['\\', '$', '`', '"', "'", '<', '>', '|', ';', '&', '(', ')', '[', ']', '{', '}', '*', '?', '!']:
                    escaped_text += "\\" + char
                else:
                    escaped_text += char
            cmd = f"input text {escaped_text}"
            self.executor.submit(self._execute_shell, device, cmd)

    def press_key(self, serial: str, keycode: int):
        """Giả lập phím bấm vật lý (keyevent) trên thiết bị Android."""
        device = self.device_cache.get(serial)
        if device:
            cmd = f"input keyevent {keycode}"
            self.executor.submit(self._execute_shell, device, cmd)

    def shutdown(self):
        """Giải phóng thread pool."""
        self.executor.shutdown(wait=False)

    def read_network_bytes(self, serial: str) -> int:
        """Đọc tổng dung lượng bytes (Receive + Transmit) của tất cả interface trừ loopback (lo) qua file /proc/net/dev."""
        device = self.device_cache.get(serial)
        if not device:
            return 0
        try:
            # Rate limiting trước khi gọi shell để tránh quá tải ADB daemon
            with self._adb_lock:
                import time as _time
                _time.sleep(0.1)
            # Lấy nội dung file /proc/net/dev với timeout
            net_dev_content = device.shell("cat /proc/net/dev", timeout=10)
            total_bytes = 0
            for line in net_dev_content.splitlines():
                if ":" in line:
                    parts = line.split(":")
                    if len(parts) == 2:
                        iface = parts[0].strip()
                        if iface == "lo":
                            continue # Bỏ qua local loopback
                        stats = parts[1].split()
                        if len(stats) >= 9:
                            try:
                                rx_bytes = int(stats[0])
                                tx_bytes = int(stats[8])
                                total_bytes += (rx_bytes + tx_bytes)
                            except ValueError:
                                pass
            return total_bytes
        except Exception as e:
            logging.warning(f"Không thể đọc bytes mạng của thiết bị {serial} (thiết bị có thể đã offline): {e}")
            return 0

    def set_system_proxy(self, serial: str, ip: str, port: int):
        """Cấu hình proxy HTTP hệ thống Android qua lệnh Settings."""
        device = self.device_cache.get(serial)
        if device:
            cmd = f"settings put global http_proxy {ip}:{port}"
            self.executor.submit(self._execute_shell, device, cmd)
            logging.info(f"Đã đặt HTTP Proxy cho thiết bị {serial}: {ip}:{port}")

    def clear_system_proxy(self, serial: str):
        """Xóa cấu hình proxy HTTP hệ thống Android."""
        device = self.device_cache.get(serial)
        if device:
            # :0 đại diện cho tắt proxy trên một số phiên bản Android, hoặc dùng delete
            cmd = "settings put global http_proxy :0"
            self.executor.submit(self._execute_shell, device, cmd)
            logging.info(f"Đã xóa HTTP Proxy cho thiết bị {serial}")


