"""
Phone Farm API Client — Giao tiếp với tool quản lý boxphone tự tạo.
Tài liệu API: README-boxphone.md
API Server: api_server.py (FastAPI + Uvicorn, mặc định http://127.0.0.1:5000)
"""

import logging
import time
import json
import asyncio
from typing import Optional
import random
import string

import httpx

log = logging.getLogger(__name__)


class XiaoWeiClient:
    """
    HTTP client cho Phone Farm API (tool tự tạo).
    Tên class giữ nguyên XiaoWeiClient để tương thích ngược với phone_bot.py và web_server.py.
    """

    def __init__(self, api_url: str = "http://127.0.0.1:5000", api_type: str = "phone_farm", timeout: int = 30):
        self.api_url = api_url.rstrip("/")
        self.api_type = "phone_farm"  # Luôn là phone_farm, bỏ qua tham số api_type
        self.timeout = timeout
        log.info(f"[PhoneFarm] Initialized client: {self.api_url}")

    # ── Core HTTP helpers ─────────────────────────────────────────────

    async def _post(self, endpoint: str, payload: dict) -> dict:
        """Gửi POST request tới Phone Farm API."""
        url = f"{self.api_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload)
                result = resp.json()
                log.debug(f"[PhoneFarm] POST {endpoint} → {resp.status_code} {result}")
                return result
        except httpx.ConnectError as e:
            log.error(f"[PhoneFarm] Không thể kết nối tới {url}: {e}")
            return {"status": "error", "message": f"Connection error: {e}"}
        except Exception as e:
            log.error(f"[PhoneFarm] Lỗi API {endpoint}: {e}")
            return {"status": "error", "message": str(e)}

    async def _get(self, endpoint: str, params: dict = None) -> any:
        """Gửi GET request tới Phone Farm API."""
        url = f"{self.api_url}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, params=params)
                return resp.json()
        except httpx.ConnectError as e:
            log.error(f"[PhoneFarm] Không thể kết nối tới {url}: {e}")
            return None
        except Exception as e:
            log.error(f"[PhoneFarm] Lỗi API GET {endpoint}: {e}")
            return None

    def _is_success(self, result: dict) -> bool:
        """Kiểm tra response có thành công không."""
        if not result:
            return False
        return (result.get("status") == "success" or
                result.get("code") == 10000 or
                result.get("message") == "SUCCESS")

    # ── Device Management ─────────────────────────────────────────────

    async def get_devices(self) -> list[dict]:
        """
        Lấy danh sách thiết bị đang kết nối.
        GET /api/devices
        Returns: list of device dicts with serial, resolution, status, etc.
        """
        try:
            result = await self._get("/api/devices")
            if result and isinstance(result, list):
                devices = []
                for dev in result:
                    devices.append({
                        "Serial": dev.get("serial"),
                        "Model": dev.get("resolution", "Android Device"),
                        "Status": "Online",
                        "is_streaming": dev.get("is_streaming", False),
                        "is_selected": dev.get("is_selected", False),
                    })
                log.info(f"[PhoneFarm] Tìm thấy {len(devices)} thiết bị")
                return devices
            log.warning(f"[PhoneFarm] Không lấy được danh sách thiết bị: {result}")
            return []
        except Exception as e:
            log.error(f"[PhoneFarm] Lỗi lấy danh sách thiết bị từ {self.api_url}: {e}")
            return []

    async def test_connection(self) -> dict:
        """
        Kiểm tra kết nối tới API.
        Returns: {"success": bool, "message": str, "devices": list}
        """
        try:
            devices = await self.get_devices()
            if devices is not None:
                return {
                    "success": True,
                    "message": f"Kết nối thành công! Tìm thấy {len(devices)} thiết bị.",
                    "devices": devices
                }
            return {
                "success": False,
                "message": "Kết nối được nhưng không lấy được danh sách thiết bị.",
                "devices": []
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Không thể kết nối: {e}",
                "devices": []
            }

    # ── Screen Control ────────────────────────────────────────────────

    async def tap(self, device: str, x_pct: float, y_pct: float) -> bool:
        """
        Tap (click) vào vị trí trên màn hình.
        POST /api/tap
        x_pct, y_pct: tọa độ phần trăm (0-100), sẽ được chuyển đổi sang 0.0-1.0 cho API.
        """
        payload = {
            "serial": device,
            "x_pct": float(x_pct) / 100.0,
            "y_pct": float(y_pct) / 100.0
        }
        result = await self._post("/api/tap", payload)
        success = self._is_success(result)
        log.info(f"[PhoneFarm] Tap ({x_pct}%, {y_pct}%) on {device}: {'OK' if success else 'FAIL'}")
        return success

    async def long_press(self, device: str, x_pct: float, y_pct: float, duration_ms: int = 1500) -> bool:
        """
        Long press tại vị trí (swipe tại chỗ với duration dài).
        POST /api/swipe (cùng tọa độ bắt đầu/kết thúc)
        """
        payload = {
            "serial": device,
            "x1_pct": float(x_pct) / 100.0,
            "y1_pct": float(y_pct) / 100.0,
            "x2_pct": float(x_pct) / 100.0,
            "y2_pct": float(y_pct) / 100.0,
            "duration": duration_ms
        }
        result = await self._post("/api/swipe", payload)
        success = self._is_success(result)
        log.info(f"[PhoneFarm] LongPress ({x_pct}%, {y_pct}%) {duration_ms}ms on {device}: {'OK' if success else 'FAIL'}")
        return success

    async def swipe(self, device: str, direction: str) -> bool:
        """
        Vuốt theo hướng: 'up', 'down', 'left', 'right'.
        POST /api/swipe
        """
        coords = {
            "up": (0.5, 0.8, 0.5, 0.2),
            "down": (0.5, 0.2, 0.5, 0.8),
            "left": (0.8, 0.5, 0.2, 0.5),
            "right": (0.2, 0.5, 0.8, 0.5)
        }
        d = direction.lower()
        if d not in coords:
            d = "down"
        x1, y1, x2, y2 = coords[d]
        payload = {
            "serial": device,
            "x1_pct": x1,
            "y1_pct": y1,
            "x2_pct": x2,
            "y2_pct": y2,
            "duration": 400
        }
        result = await self._post("/api/swipe", payload)
        success = self._is_success(result)
        log.info(f"[PhoneFarm] Swipe {direction} on {device}: {'OK' if success else 'FAIL'}")
        return success

    async def swipe_custom(self, device: str, x1_pct: float, y1_pct: float,
                           x2_pct: float, y2_pct: float, duration: int = 400) -> bool:
        """
        Vuốt tùy chỉnh với tọa độ phần trăm (0.0-1.0).
        POST /api/swipe
        """
        payload = {
            "serial": device,
            "x1_pct": x1_pct,
            "y1_pct": y1_pct,
            "x2_pct": x2_pct,
            "y2_pct": y2_pct,
            "duration": duration
        }
        result = await self._post("/api/swipe", payload)
        return self._is_success(result)

    async def scroll_up(self, device: str) -> bool:
        """Scroll lên (swipe down = nội dung đi lên)."""
        return await self.swipe(device, "down")

    async def scroll_down(self, device: str) -> bool:
        """Scroll xuống (swipe up = nội dung đi xuống)."""
        return await self.swipe(device, "up")

    # ── System Keys ───────────────────────────────────────────────────

    async def _send_keyevent(self, device: str, keycode: int) -> bool:
        """
        Gửi phím cứng Android.
        POST /api/keyevent
        Keycodes: 3=HOME, 4=BACK, 26=POWER, 66=ENTER, 67=DEL, 82=MENU
        """
        payload = {
            "serial": device,
            "keycode": keycode
        }
        result = await self._post("/api/keyevent", payload)
        success = self._is_success(result)
        log.debug(f"[PhoneFarm] Keyevent {keycode} on {device}: {'OK' if success else 'FAIL'}")
        return success

    async def press_back(self, device: str) -> bool:
        """Nhấn nút Back (keycode 4)."""
        return await self._send_keyevent(device, 4)

    async def press_home(self, device: str) -> bool:
        """Nhấn nút Home (keycode 3)."""
        return await self._send_keyevent(device, 3)

    async def press_recents(self, device: str) -> bool:
        """Nhấn nút Recents/Task Manager (keycode 187)."""
        return await self._send_keyevent(device, 187)

    async def press_enter(self, device: str) -> bool:
        """Nhấn phím Enter (keycode 66)."""
        return await self._send_keyevent(device, 66)

    async def press_delete(self, device: str) -> bool:
        """Nhấn phím Delete/Backspace (keycode 67)."""
        return await self._send_keyevent(device, 67)

    # ── Text Input ────────────────────────────────────────────────────

    async def type_text(self, device: str, text: str, x_pct: float = 50, y_pct: float = 50) -> bool:
        """
        Nhập text vào ô input hiện tại (gõ toàn bộ chuỗi 1 lần).
        POST /api/text
        """
        payload = {
            "serial": device,
            "text": text
        }
        result = await self._post("/api/text", payload)
        success = self._is_success(result)
        log.info(f"[PhoneFarm] type_text '{text[:30]}...' on {device}: {'OK' if success else 'FAIL'}")
        return success

    async def type_single_char(self, device: str, char: str) -> bool:
        """Gõ 1 ký tự duy nhất qua API /api/text."""
        payload = {
            "serial": device,
            "text": char
        }
        result = await self._post("/api/text", payload)
        return self._is_success(result)

    # ── ADB Commands ──────────────────────────────────────────────────

    async def run_adb(self, device: str, command: str) -> bool:
        """
        Chạy lệnh ADB shell trên thiết bị.
        POST /api/adb
        """
        payload = {
            "serial": device,
            "command": command
        }
        result = await self._post("/api/adb", payload)
        success = result.get("code") == 10000 if result else False
        log.debug(f"[PhoneFarm] ADB '{command[:50]}' on {device}: {'OK' if success else 'FAIL'}")
        return success

    async def run_adb_with_output(self, device: str, command: str) -> Optional[str]:
        """
        Chạy lệnh ADB và trả về output.
        POST /api/adb → response.data chứa output
        """
        payload = {
            "serial": device,
            "command": command
        }
        result = await self._post("/api/adb", payload)
        if result and result.get("code") == 10000:
            return result.get("data")
        return None

    # ── App & URL Control ─────────────────────────────────────────────

    async def open_url(self, device: str, url: str) -> bool:
        """Mở URL trong Chrome trên thiết bị qua ADB."""
        cmd = f'am start -a android.intent.action.VIEW -d "{url}" com.android.chrome'
        return await self.run_adb(device, cmd)

    async def open_chrome(self, device: str) -> bool:
        """Mở Chrome browser."""
        return await self.run_adb(device, "am start -n com.android.chrome/com.google.android.apps.chrome.Main")

    async def clear_chrome_data(self, device: str) -> bool:
        """Xóa dữ liệu Chrome (cookies, cache) — dùng trước khi đăng ký."""
        return await self.run_adb(device, "pm clear com.android.chrome")

    async def kill_chrome(self, device: str) -> bool:
        """Tắt Chrome."""
        return await self.run_adb(device, "am force-stop com.android.chrome")

    # ── Screenshot ────────────────────────────────────────────────────

    async def screenshot(self, device: str, save_path: str = "") -> bool:
        """
        Chụp ảnh màn hình thiết bị.
        POST /api/screenshot
        """
        payload = {
            "serial": device,
            "save_path": save_path
        }
        result = await self._post("/api/screenshot", payload)
        success = result.get("code") == 10000 if result else False
        log.info(f"[PhoneFarm] Screenshot on {device}: {'OK' if success else 'FAIL'}")
        return success

    # ── Proxy Management ──────────────────────────────────────────────

    async def get_proxy(self, device: str) -> Optional[dict]:
        """
        Lấy thông tin proxy đang gán cho thiết bị.
        GET /api/proxy?serial=DEVICE_SERIAL
        """
        result = await self._get("/api/proxy", params={"serial": device})
        if result and result.get("has_proxy"):
            return result
        return None

    async def rotate_proxy(self, device: str) -> bool:
        """
        Xoay IP / đổi proxy mới cho thiết bị.
        POST /api/proxy/rotate
        """
        payload = {"serial": device}
        result = await self._post("/api/proxy/rotate", payload)
        success = self._is_success(result)
        log.info(f"[PhoneFarm] Rotate proxy on {device}: {'OK' if success else 'FAIL'}")
        return success

    # ── Stream Control ────────────────────────────────────────────────

    async def start_stream(self, device: str) -> bool:
        """Bật stream Scrcpy cho thiết bị."""
        result = await self._post("/api/stream", {"serial": device, "action": "start"})
        return self._is_success(result)

    async def stop_stream(self, device: str) -> bool:
        """Tắt stream Scrcpy cho thiết bị."""
        result = await self._post("/api/stream", {"serial": device, "action": "stop"})
        return self._is_success(result)

    # ── SMS Reading (via ADB) ─────────────────────────────────────────

    async def read_latest_sms(self, device: str, sender_filter: str = "", timeout_sec: int = 90) -> Optional[str]:
        """Đọc SMS mới nhất trên thiết bị qua ADB content query."""
        log.info(f"[PhoneFarm] Đang chờ SMS trên {device} (timeout={timeout_sec}s, filter='{sender_filter}')...")

        start_time = time.time()
        last_sms_body = None

        while time.time() - start_time < timeout_sec:
            cmd = 'content query --uri content://sms/inbox --projection body:address:date --sort "date DESC" --limit 5'
            output = await self.run_adb_with_output(device, command=cmd)

            if output and isinstance(output, str):
                for line in output.split("\n"):
                    if "body=" in line:
                        try:
                            body_part = line.split("body=")[1].split(",")[0].strip()
                            address_part = ""
                            if "address=" in line:
                                address_part = line.split("address=")[1].split(",")[0].strip()

                            if sender_filter and sender_filter.lower() not in address_part.lower():
                                continue

                            if body_part and body_part != last_sms_body:
                                import re
                                otp_match = re.search(r'\b(\d{6})\b', body_part)
                                if otp_match:
                                    otp = otp_match.group(1)
                                    log.info(f"[PhoneFarm] Tìm thấy OTP trong SMS: {otp}")
                                    return otp

                                last_sms_body = body_part
                        except Exception as e:
                            log.warning(f"[PhoneFarm] Lỗi parse SMS: {e}")

            await asyncio.sleep(5)

        log.warning(f"[PhoneFarm] Timeout chờ SMS trên {device}")
        return None

    # ══════════════════════════════════════════════════════════════════
    # ── Human-like Typing Simulation ─────────────────────────────────
    # ══════════════════════════════════════════════════════════════════

    # Bản đồ phím lân cận trên bàn phím QWERTY — dùng để tạo lỗi gõ nhầm "thật"
    _NEARBY_KEYS = {
        'a': 'sqwz', 'b': 'vghn', 'c': 'xdfv', 'd': 'serfcx', 'e': 'wsdfr',
        'f': 'dertgcv', 'g': 'frtyhvb', 'h': 'gtyjubn', 'i': 'ujklo',
        'j': 'hyuiknm', 'k': 'juilom', 'l': 'kiopm', 'm': 'njk',
        'n': 'bhjm', 'o': 'iklp', 'p': 'ol', 'q': 'wa', 'r': 'edft',
        's': 'awedxz', 't': 'rfgy', 'u': 'yhjik', 'v': 'cfgb',
        'w': 'qase', 'x': 'zsdc', 'y': 'tghu', 'z': 'asx',
        '0': '9', '1': '2', '2': '13', '3': '24', '4': '35',
        '5': '46', '6': '57', '7': '68', '8': '79', '9': '80',
    }

    def _get_typo_char(self, correct_char: str) -> str:
        """Trả về ký tự sai gần trên bàn phím (hoặc random nếu không có bản đồ)."""
        lower = correct_char.lower()
        nearby = self._NEARBY_KEYS.get(lower, '')
        nearby = nearby.replace(' ', '')
        if nearby:
            typo = random.choice(nearby)
            # Giữ nguyên case
            return typo.upper() if correct_char.isupper() else typo
        # Fallback: random ký tự chữ/số
        pool = string.ascii_lowercase + string.digits
        return random.choice(pool.replace(lower, ''))

    async def human_type(self, device: str, text: str, typo_config: dict = None) -> bool:
        """
        Gõ text từng ký tự một với delay ngẫu nhiên, giống người thật.

        Kịch bản:
        1. Duyệt từng ký tự trong text
        2. Với xác suất typo_probability (5%), gõ ký tự SAI (phím lân cận QWERTY)
           → Dừng 0.3s (nhận ra sai) → Backspace (keyevent 67) → Dừng 0.15s → Gõ lại đúng
        3. Gõ ký tự đúng qua POST /api/text
        4. Delay ngẫu nhiên 80-220ms giữa các ký tự

        Args:
            device: serial thiết bị
            text: chuỗi cần gõ
            typo_config: dict cấu hình (lấy từ CONFIG nếu None)

        Returns:
            True nếu gõ xong thành công
        """
        from src.config import CONFIG

        if typo_config is None:
            typo_config = CONFIG.get("xiaowei", {}).get("human_typing", {})

        char_delay_min = typo_config.get("char_delay_min", 0.08)
        char_delay_max = typo_config.get("char_delay_max", 0.22)
        typo_enabled = typo_config.get("typo_enabled", True)
        typo_prob = typo_config.get("typo_probability", 0.05)
        pause_before_bs = typo_config.get("typo_pause_before_backspace", 0.3)
        pause_after_bs = typo_config.get("typo_pause_after_backspace", 0.15)

        log.info(f"[PhoneFarm] human_type: '{text[:30]}...' trên {device} "
                 f"(delay={char_delay_min}-{char_delay_max}s, typo={'ON' if typo_enabled else 'OFF'} {typo_prob*100:.0f}%)")

        for i, char in enumerate(text):
            # ── Kiểm tra gõ nhầm ──
            if typo_enabled and char.isalnum() and random.random() < typo_prob:
                # Gõ ký tự SAI (gần trên bàn phím)
                wrong_char = self._get_typo_char(char)
                log.debug(f"[PhoneFarm] Typo! Gõ nhầm '{wrong_char}' thay vì '{char}' (vị trí {i})")

                # Gõ ký tự sai qua /api/text
                await self.type_single_char(device, wrong_char)

                # Dừng lại — "nhận ra sai"
                await asyncio.sleep(pause_before_bs)

                # Bấm Backspace (keyevent 67) để xóa ký tự sai
                await self._send_keyevent(device, 67)
                log.debug(f"[PhoneFarm] Backspace → xóa '{wrong_char}'")

                # Dừng lại trước khi gõ lại đúng
                await asyncio.sleep(pause_after_bs)

            # ── Gõ ký tự ĐÚNG qua /api/text ──
            success = await self.type_single_char(device, char)
            if not success:
                log.error(f"[PhoneFarm] Lỗi gõ ký tự '{char}' (vị trí {i})")
                return False

            # ── Delay ngẫu nhiên giữa các ký tự ──
            delay = random.uniform(char_delay_min, char_delay_max)
            await asyncio.sleep(delay)

        log.info(f"[PhoneFarm] human_type hoàn tất: '{text[:20]}...' ({len(text)} ký tự)")
        return True

    async def thinking_delay(self, description: str = ""):
        """
        Độ trễ suy nghĩ (Thinking Time) — giả lập người dùng nhìn lại
        trước khi bấm nút Tiếp tục/Xác nhận.
        Delay ngẫu nhiên từ thinking_time_min đến thinking_time_max giây.
        """
        from src.config import CONFIG
        ht_config = CONFIG.get("xiaowei", {}).get("human_typing", {})
        t_min = ht_config.get("thinking_time_min", 0.8)
        t_max = ht_config.get("thinking_time_max", 1.8)
        delay = random.uniform(t_min, t_max)
        if description:
            log.info(f"[PhoneFarm] Thinking delay {delay:.2f}s trước khi {description}")
        await asyncio.sleep(delay)

    async def tap_with_offset(self, device: str, x_pct: float, y_pct: float,
                               offset_range: float = 1.5) -> bool:
        """
        Tap vào vị trí với tọa độ lệch tâm ngẫu nhiên (giả lập ngón tay người thật).

        Args:
            device: serial thiết bị
            x_pct, y_pct: tọa độ phần trăm trung tâm nút (0-100)
            offset_range: phạm vi lệch tối đa (% màn hình), mặc định ±1.5%

        Returns:
            True nếu tap thành công
        """
        x_offset = random.uniform(-offset_range, offset_range)
        y_offset = random.uniform(-offset_range, offset_range)
        actual_x = max(0, min(100, x_pct + x_offset))
        actual_y = max(0, min(100, y_pct + y_offset))
        log.debug(f"[PhoneFarm] tap_with_offset: target=({x_pct}%, {y_pct}%) → "
                  f"actual=({actual_x:.1f}%, {actual_y:.1f}%) offset=({x_offset:+.1f}, {y_offset:+.1f})")
        return await self.tap(device, actual_x, actual_y)
