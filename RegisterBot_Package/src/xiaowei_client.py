"""
Phone backend client.
Hỗ trợ:
- XiaoWei WebSocket API (mặc định hiện tại)
- Phone Farm HTTP API (legacy fallback)
"""

import logging
import time
import json
import asyncio
from typing import Optional, Any
import random
import string

import httpx

log = logging.getLogger(__name__)


class XiaoWeiClient:
    """
    Client cho backend phone mode.
    Tên class giữ nguyên để tương thích ngược với phone_bot.py và web_server.py.
    """

    def __init__(self, api_url: str = "http://127.0.0.1:22222", api_type: str = "xiaowei", timeout: int = 30):
        self.api_url = api_url.rstrip("/")
        # Detect if it's pointing to 22222 port or api_type is xiaowei
        if "22222" in self.api_url or api_type == "xiaowei":
            self.api_type = "xiaowei"
        else:
            self.api_type = "phone_farm"
        self.timeout = timeout
        self.resolutions_cache = {}
        log.info(f"[XiaoWeiClient] Initialized client: {self.api_url} (type: {self.api_type})")

    # ── Core WebSocket helpers ────────────────────────────────────────

    def _backend_label(self) -> str:
        return "XiaoWei WS" if self.api_type == "xiaowei" else "PhoneFarm HTTP"

    def _normalize_device(self, dev: Any, index: int = 0) -> dict:
        """
        Chuẩn hóa payload device từ nhiều backend/shape khác nhau về một format ổn định.
        """
        if isinstance(dev, dict):
            serial = (
                dev.get("serial")
                or dev.get("onlySerial")
                or dev.get("Serial")
                or dev.get("id")
                or dev.get("deviceId")
                or dev.get("name")
                or f"device-{index + 1}"
            )
            model = (
                dev.get("model")
                or dev.get("modelName")
                or dev.get("Model")
                or dev.get("deviceModel")
                or dev.get("resolution")
                or "Android Device"
            )
            status = (
                dev.get("status")
                or dev.get("Status")
                or dev.get("state")
                or dev.get("deviceStatus")
                or "Online"
            )
            is_streaming = bool(dev.get("is_streaming", self.api_type == "xiaowei"))
            is_selected = bool(dev.get("is_selected", self.api_type == "xiaowei"))
        else:
            serial = str(dev)
            model = "Android Device"
            status = "Online"
            is_streaming = self.api_type == "xiaowei"
            is_selected = self.api_type == "xiaowei"

        normalized = {
            "serial": str(serial),
            "Serial": str(serial),
            "model": str(model),
            "Model": str(model),
            "status": str(status),
            "Status": str(status),
            "is_streaming": is_streaming,
            "is_selected": is_selected,
        }
        return normalized

    async def _send_websocket(self, payload: dict) -> dict:
        """Gửi payload qua WebSocket tới XiaoWei API."""
        ws_url = self.api_url
        if ws_url.startswith("http://"):
            ws_url = "ws://" + ws_url[7:]
        elif ws_url.startswith("https://"):
            ws_url = "wss://" + ws_url[8:]
        if not ws_url.startswith("ws://") and not ws_url.startswith("wss://"):
            ws_url = f"ws://{ws_url}"
        if not ws_url.endswith("/"):
            ws_url += "/"

        delay_ms = [100, 300, 600]
        action = payload.get("action", "unknown")
        last_error = None

        for attempt in range(3):
            try:
                import websockets
                ws = await asyncio.wait_for(websockets.connect(ws_url), timeout=self.timeout)
                async with ws:
                    await ws.send(json.dumps(payload))
                    resp = await asyncio.wait_for(ws.recv(), timeout=self.timeout)
                    result = json.loads(resp)
                    log.debug(f"[XiaoWei WS] {action} -> {result}")
                    return result
            except Exception as e:
                last_error = e
                if attempt < 2:
                    wait = delay_ms[attempt] / 1000.0
                    log.warning(
                        f"[XiaoWei WS] {action} lần {attempt + 1} thất bại ({e}), retry sau {delay_ms[attempt]}ms"
                    )
                    await asyncio.sleep(wait)

        log.error(f"[XiaoWei WS] {action} thất bại sau 3 lần thử tới {ws_url}: {last_error}")
        return {"code": -1, "message": str(last_error), "data": None}


    async def _get_device_res(self, device: str) -> tuple[int, int]:
        """Lấy độ phân giải của thiết bị qua adb shell wm size."""
        if device in self.resolutions_cache:
            return self.resolutions_cache[device]
            
        out = await self.run_adb_with_output(device, "wm size")
        if out:
            import re
            override_match = re.search(r"Override size:\s*(\d+)x(\d+)", out)
            if override_match:
                w, h = int(override_match.group(1)), int(override_match.group(2))
                self.resolutions_cache[device] = (w, h)
                return w, h
            physical_match = re.search(r"Physical size:\s*(\d+)x(\d+)", out)
            if physical_match:
                w, h = int(physical_match.group(1)), int(physical_match.group(2))
                self.resolutions_cache[device] = (w, h)
                return w, h
        return 1080, 1920


    # ── Core HTTP helpers ─────────────────────────────────────────────

    async def _post(self, endpoint: str, payload: dict) -> dict:
        """
        Gửi POST request tới Phone Farm API với retry 3 lần (100/300/600ms backoff).
        Retry khi: network error, timeout, HTTP 5xx.
        Không retry khi: HTTP 4xx (lỗi client, retry vô ích).
        """
        url = f"{self.api_url}{endpoint}"
        delay_ms = [100, 300, 600]
        last_error = None

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code >= 500:
                        # Server error — đáng retry
                        raise httpx.HTTPStatusError(
                            f"HTTP {resp.status_code}",
                            request=resp.request,
                            response=resp,
                        )
                    result = resp.json()
                    if attempt > 0:
                        log.info(f"[PhoneFarm] POST {endpoint} thành công sau {attempt + 1} lần thử")
                    log.debug(f"[PhoneFarm] POST {endpoint} → {resp.status_code} {result}")
                    return result
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last_error = e
                if attempt < 2:
                    wait = delay_ms[attempt] / 1000.0
                    log.warning(f"[PhoneFarm] POST {endpoint} lần {attempt + 1} thất bại ({e}), retry sau {delay_ms[attempt]}ms")
                    await asyncio.sleep(wait)
            except Exception as e:
                log.error(f"[PhoneFarm] Lỗi API {endpoint}: {e}")
                return {"status": "error", "message": str(e)}

        log.error(f"[PhoneFarm] POST {endpoint} thất bại sau 3 lần thử: {last_error}")
        return {"status": "error", "message": f"Max retries exceeded: {last_error}"}

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
                result.get("success") is True or
                result.get("code") == 10000 or
                result.get("message") == "SUCCESS")

    # ── Device Management ─────────────────────────────────────────────

    async def get_devices(self) -> list[dict]:
        """
        Lấy danh sách thiết bị đang kết nối.
        GET /api/devices (hoặc action: list qua WebSocket cho XiaoWei)
        """
        if self.api_type == "xiaowei":
            res = await self._send_websocket({"action": "list"})
            if self._is_success(res) and isinstance(res.get("data"), list):
                devices = [self._normalize_device(dev, index=i) for i, dev in enumerate(res["data"])]
                log.info(f"[XiaoWei WS] Tìm thấy {len(devices)} thiết bị")
                return devices
            log.warning(f"[XiaoWei WS] Không lấy được danh sách thiết bị: {res}")
            return []

        try:
            result = await self._get("/api/devices")
            if result and isinstance(result, list):
                devices = []
                for i, dev in enumerate(result):
                    normalized = self._normalize_device(dev, index=i)
                    if isinstance(dev, dict) and dev.get("resolution"):
                        normalized["model"] = dev["resolution"]
                        normalized["Model"] = dev["resolution"]
                    devices.append(normalized)
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
                    "backend": self.api_type,
                    "backend_label": self._backend_label(),
                    "api_url": self.api_url,
                    "message": f"Kết nối thành công! Tìm thấy {len(devices)} thiết bị.",
                    "devices": devices
                }
            return {
                "success": False,
                "backend": self.api_type,
                "backend_label": self._backend_label(),
                "api_url": self.api_url,
                "message": "Kết nối được nhưng không lấy được danh sách thiết bị.",
                "devices": []
            }
        except Exception as e:
            return {
                "success": False,
                "backend": self.api_type,
                "backend_label": self._backend_label(),
                "api_url": self.api_url,
                "message": f"Không thể kết nối: {e}",
                "devices": []
            }

    # ── Screen Control ────────────────────────────────────────────────

    async def tap(self, device: str, x_pct: float, y_pct: float) -> bool:
        """
        Tap (click) vào vị trí trên màn hình.
        x_pct, y_pct: tọa độ phần trăm (0-100).
        """
        if self.api_type == "xiaowei":
            res = await self._send_websocket({
                "action": "pointerEvent",
                "devices": device,
                "data": {
                    "type": "10",
                    "x": str(x_pct),
                    "y": str(y_pct)
                }
            })
            return self._is_success(res)

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
        """
        if self.api_type == "xiaowei":
            # Gửi sự kiện nhấn xuống (type: "0") rồi chờ và gửi nhấc lên (type: "1") để giả lập long press
            res1 = await self._send_websocket({
                "action": "pointerEvent",
                "devices": device,
                "data": {
                    "type": "0",
                    "x": str(x_pct),
                    "y": str(y_pct)
                }
            })
            await asyncio.sleep(duration_ms / 1000.0)
            res2 = await self._send_websocket({
                "action": "pointerEvent",
                "devices": device,
                "data": {
                    "type": "1",
                    "x": str(x_pct),
                    "y": str(y_pct)
                }
            })
            return self._is_success(res1) and self._is_success(res2)

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
        """
        if self.api_type == "xiaowei":
            # Map hướng vuốt tới type tương ứng: up="6", down="7", left="8", right="9"
            dir_map = {"up": "6", "down": "7", "left": "8", "right": "9"}
            d_type = dir_map.get(direction.lower(), "7")
            res = await self._send_websocket({
                "action": "pointerEvent",
                "devices": device,
                "data": {
                    "type": d_type,
                    "x": "50",
                    "y": "50"
                }
            })
            return self._is_success(res)

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
        """
        if self.api_type == "xiaowei":
            # Dùng adb shell input swipe vì các API WebSocket pointerEvent custom swipe chưa được chuẩn hoá
            w, h = await self._get_device_res(device)
            x1 = int(float(x1_pct) * w)
            y1 = int(float(y1_pct) * h)
            x2 = int(float(x2_pct) * w)
            y2 = int(float(y2_pct) * h)
            return await self.run_adb(device, f"input swipe {x1} {y1} {x2} {y2} {duration}")

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
        """
        if self.api_type == "xiaowei":
            return await self.run_adb(device, f"input keyevent {keycode}")

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
        if self.api_type == "xiaowei":
            res = await self._send_websocket({
                "action": "pushEvent",
                "devices": device,
                "data": {"type": "3"}
            })
            return self._is_success(res)
        return await self._send_keyevent(device, 4)

    async def press_home(self, device: str) -> bool:
        """Nhấn nút Home (keycode 3)."""
        if self.api_type == "xiaowei":
            res = await self._send_websocket({
                "action": "pushEvent",
                "devices": device,
                "data": {"type": "2"}
            })
            return self._is_success(res)
        return await self._send_keyevent(device, 3)

    async def press_recents(self, device: str) -> bool:
        """Nhấn nút Recents/Task Manager (keycode 187)."""
        if self.api_type == "xiaowei":
            res = await self._send_websocket({
                "action": "pushEvent",
                "devices": device,
                "data": {"type": "1"}
            })
            return self._is_success(res)
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
        """
        if self.api_type == "xiaowei":
            res = await self._send_websocket({
                "action": "inputText",
                "devices": device,
                "data": {"content": text}
            })
            return self._is_success(res)

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
        if self.api_type == "xiaowei":
            res = await self._send_websocket({
                "action": "inputText",
                "devices": device,
                "data": {"content": char}
            })
            return self._is_success(res)

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
        """
        if self.api_type == "xiaowei":
            # Auto-prepend 'shell ' if not present and is a shell command
            clean_cmd = command
            if not any(clean_cmd.startswith(prefix) for prefix in ["shell ", "push ", "pull ", "install ", "uninstall ", "devices"]):
                clean_cmd = f"shell {command}"
                
            res = await self._send_websocket({
                "action": "adb",
                "devices": device,
                "data": {"command": clean_cmd}
            })
            success = self._is_success(res)
            log.debug(f"[XiaoWei WS] ADB '{command[:50]}' on {device}: {'OK' if success else 'FAIL'}")
            return success

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
        """
        if self.api_type == "xiaowei":
            # Auto-prepend 'shell ' if not present and is a shell command
            clean_cmd = command
            if not any(clean_cmd.startswith(prefix) for prefix in ["shell ", "push ", "pull ", "install ", "uninstall ", "devices"]):
                clean_cmd = f"shell {command}"
                
            res = await self._send_websocket({
                "action": "adb",
                "devices": device,
                "data": {"command": clean_cmd}
            })
            if self._is_success(res):
                data = res.get("data")
                if isinstance(data, dict):
                    # Trả về kết quả của thiết bị cụ thể
                    output = data.get(device)
                    if output is None and len(data) == 1:
                        # Fallback nếu key không khớp chính xác serial
                        output = list(data.values())[0]
                    return output
                return str(data) if data is not None else None
            return None

        payload = {
            "serial": device,
            "command": command
        }
        result = await self._post("/api/adb", payload)
        if result and result.get("code") == 10000:
            return result.get("data")
        return None

    # ── App & URL Control ─────────────────────────────────────────────
    
    async def is_package_installed(self, device: str, package: str) -> bool:
        """Kiểm tra xem một gói ứng dụng (package) có được cài đặt trên thiết bị không."""
        out = await self.run_adb_with_output(device, f"pm list packages {package}")
        if out and package in out:
            return True
        return False

    async def open_url(self, device: str, url: str, package: str = "com.android.chrome") -> bool:
        """Mở URL trong trình duyệt cụ thể trên thiết bị qua ADB."""
        if package == "com.android.chrome":
            cmd = (
                'am start -n com.android.chrome/com.google.android.apps.chrome.Main '
                f'-a android.intent.action.VIEW -d "{url}"'
            )
        else:
            cmd = f'am start -a android.intent.action.VIEW -d "{url}" {package}'
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

    async def clear_browser_data(self, device: str, package: str) -> bool:
        """Xóa dữ liệu trình duyệt cụ thể (cookies, cache)."""
        return await self.run_adb(device, f"pm clear {package}")

    async def kill_browser(self, device: str, package: str) -> bool:
        """Tắt trình duyệt cụ thể."""
        return await self.run_adb(device, f"am force-stop {package}")

    # ── Screenshot ────────────────────────────────────────────────────

    async def screenshot(self, device: str, save_path: str = "") -> bool:
        """
        Chụp ảnh màn hình thiết bị.
        """
        if self.api_type == "xiaowei":
            import os
            abs_path = os.path.abspath(save_path) if save_path else ""
            payload = {
                "action": "screen",
                "devices": device,
                "data": {
                    "savePath": abs_path
                }
            }
            res = await self._send_websocket(payload)
            success = self._is_success(res)
            log.info(f"[XiaoWei WS] Screenshot on {device}: {'OK' if success else 'FAIL'}")
            return success

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
        """
        if self.api_type == "xiaowei":
            return None

        result = await self._get("/api/proxy", params={"serial": device})
        if result and result.get("has_proxy"):
            return result
        return None

    async def rotate_proxy(self, device: str) -> bool:
        """
        Xoay IP / đổi proxy mới cho thiết bị.
        """
        if self.api_type == "xiaowei":
            return True

        payload = {"serial": device}
        result = await self._post("/api/proxy/rotate", payload)
        success = self._is_success(result)
        log.info(f"[PhoneFarm] Rotate proxy on {device}: {'OK' if success else 'FAIL'}")
        return success

    # ── Stream Control ────────────────────────────────────────────────

    async def start_stream(self, device: str) -> bool:
        """Bật stream Scrcpy cho thiết bị."""
        if self.api_type == "xiaowei":
            return True

        result = await self._post("/api/stream", {"serial": device, "action": "start"})
        return self._is_success(result)

    async def stop_stream(self, device: str) -> bool:
        """Tắt stream Scrcpy cho thiết bị."""
        if self.api_type == "xiaowei":
            return True

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

    async def clear_cache(self, device: str, package: str) -> bool:
        """Gọi POST /device/clear-cache để xóa dữ liệu app (hoặc adb shell pm clear cho XiaoWei)."""
        if self.api_type == "xiaowei":
            return await self.run_adb(device, f"pm clear {package}")

        payload = {"serial": device, "package": package}
        result = await self._post("/device/clear-cache", payload)
        success = self._is_success(result)
        log.info(f"[PhoneFarm] clear_cache for {package} on {device}: {'OK' if success else 'FAIL'}")
        return success

    async def open_app(self, device: str, package: str) -> bool:
        """Gọi POST /device/open-app để khởi chạy app (hoặc action: startApk cho XiaoWei)."""
        if self.api_type == "xiaowei":
            res = await self._send_websocket({
                "action": "startApk",
                "devices": device,
                "packageName": package
            })
            return self._is_success(res)

        payload = {"serial": device, "package": package}
        result = await self._post("/device/open-app", payload)
        success = self._is_success(result)
        log.info(f"[PhoneFarm] open_app {package} on {device}: {'OK' if success else 'FAIL'}")
        return success

    async def type_char(self, device: str, char: str) -> bool:
        """Gọi POST /device/type-char để nhập một ký tự (hoặc type_single_char cho XiaoWei)."""
        if self.api_type == "xiaowei":
            return await self.type_single_char(device, char)

        payload = {"serial": device, "char": char}
        result = await self._post("/device/type-char", payload)
        success = self._is_success(result)
        return success

    async def device_click(self, device: str, x: int, y: int) -> bool:
        """Gọi POST /device/click để click vào tọa độ pixel (hoặc pointerEvent cho XiaoWei)."""
        if self.api_type == "xiaowei":
            w, h = await self._get_device_res(device)
            x_pct = (x / w) * 100.0 if w > 0 else 50.0
            y_pct = (y / h) * 100.0 if h > 0 else 50.0
            res = await self._send_websocket({
                "action": "pointerEvent",
                "devices": device,
                "data": {
                    "type": "10",
                    "x": f"{x_pct:.1f}",
                    "y": f"{y_pct:.1f}"
                }
            })
            return self._is_success(res)

        payload = {"serial": device, "x": x, "y": y}
        result = await self._post("/device/click", payload)
        success = self._is_success(result)
        log.info(f"[PhoneFarm] device_click ({x}, {y}) on {device}: {'OK' if success else 'FAIL'}")
        return success
