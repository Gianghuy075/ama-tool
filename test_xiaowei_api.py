"""
Test script: Kiểm tra kết nối tới API của XiaoWei (xiaowei.xin) Boxphone.

XiaoWei API sử dụng HTTP POST tới http://127.0.0.1:{PORT}
Port mặc định: 22222 (có thể kiểm tra trong cài đặt phần mềm XiaoWei)

Tất cả request đều là POST JSON với field "action" xác định loại lệnh.

Cách chạy:
    python test_xiaowei_api.py
    python test_xiaowei_api.py --port 22222
    python test_xiaowei_api.py --port 22222 --register
"""

import asyncio
import sys
import os
import time
import logging
import json
import argparse
from datetime import datetime

import httpx

# Thêm RegisterBot_Package vào path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTER_PKG = os.path.join(SCRIPT_DIR, "RegisterBot_Package")
if REGISTER_PKG not in sys.path:
    sys.path.insert(0, REGISTER_PKG)

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-5s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("test_xiaowei")

# ── Config ───────────────────────────────────────────────────────────────────
DEFAULT_PORTS = [22222, 20026, 5000, 5001]

# Tài khoản test – thay đổi trước khi chạy thật
TEST_ACCOUNT = {
    "name": "",                                  # Để trống → tự sinh tên Nhật
    "email": "pokemontt0008+test01@gmail.com",   # Email test (dùng Gmail + alias)
    "password": "TestPass@2026!",                # Mật khẩu mạnh
}


# ══════════════════════════════════════════════════════════════════════════════
#  XiaoWei API Client (giao thức gốc của xiaowei.xin)
# ══════════════════════════════════════════════════════════════════════════════

class XiaoWeiAPITester:
    """
    Client test trực tiếp API gốc của phần mềm XiaoWei Boxphone (xiaowei.xin).

    Giao thức:
    - Nếu port là 22222: Sử dụng WebSocket để kết nối và gửi/nhận dữ liệu.
    - Ngược lại: Sử dụng HTTP POST tới http://127.0.0.1:{port}
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 22222, timeout: int = 15):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self.is_ws = (port == 22222)
        if self.is_ws:
            log.info(f"XiaoWeiAPITester: Sử dụng WebSocket cho port {port}")

    async def _send_websocket(self, payload: dict) -> dict:
        """Gửi payload qua WebSocket tới XiaoWei API."""
        ws_url = f"ws://{self.host}:{self.port}/"
        try:
            import websockets
            ws = await asyncio.wait_for(websockets.connect(ws_url), timeout=self.timeout)
            async with ws:
                await ws.send(json.dumps(payload))
                resp = await ws.recv()
                result = json.loads(resp)
                log.debug(f"WS {payload.get('action', '?')} → {json.dumps(result, ensure_ascii=False)[:200]}")
                return result
        except Exception as e:
            log.error(f"WS Error: {e}")
            return {"code": -99, "message": f"WebSocket Error: {e}", "data": None}

    async def _post(self, payload: dict) -> dict:
        """Gửi POST request tới XiaoWei API."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.base_url, json=payload)
                result = resp.json()
                log.debug(f"POST {payload.get('action', '?')} → {resp.status_code} {json.dumps(result, ensure_ascii=False)[:200]}")
                return result
        except httpx.ConnectError as e:
            return {"code": -1, "message": f"Connection error: {e}", "data": None}
        except httpx.ReadTimeout as e:
            return {"code": -2, "message": f"Timeout: {e}", "data": None}
        except Exception as e:
            return {"code": -99, "message": f"Error: {e}", "data": None}

    async def _send_payload(self, payload: dict) -> dict:
        if self.is_ws:
            return await self._send_websocket(payload)
        else:
            return await self._post(payload)

    def _is_success(self, result: dict) -> bool:
        return result.get("code") == 10000

    async def _get_device_res(self, device: str) -> tuple[int, int]:
        """Lấy độ phân giải của thiết bị qua adb shell wm size."""
        resp = await self.run_adb(device, "wm size")
        if resp and resp.get("code") == 10000:
            data = resp.get("data")
            out = None
            if isinstance(data, dict):
                out = data.get(device)
                if out is None and len(data) == 1:
                    out = list(data.values())[0]
            elif isinstance(data, str):
                out = data
            if out:
                import re
                override_match = re.search(r"Override size:\s*(\d+)x(\d+)", out)
                if override_match:
                    return int(override_match.group(1)), int(override_match.group(2))
                physical_match = re.search(r"Physical size:\s*(\d+)x(\d+)", out)
                if physical_match:
                    return int(physical_match.group(1)), int(physical_match.group(2))
        return 1080, 1920

    # ── API Methods ──────────────────────────────────────────────────────────

    async def get_devices(self) -> dict:
        """8.2.1 list - Lấy danh sách thiết bị đang kết nối."""
        return await self._send_payload({"action": "list"})

    async def run_adb(self, devices: str, command: str) -> dict:
        """8.2.3 adb - Chạy lệnh ADB shell."""
        if self.is_ws:
            clean_cmd = command
            if not any(clean_cmd.startswith(prefix) for prefix in ["shell ", "push ", "pull ", "install ", "uninstall ", "devices"]):
                clean_cmd = f"shell {command}"
            payload = {
                "action": "adb",
                "devices": devices,
                "data": {"command": clean_cmd}
            }
        else:
            payload = {
                "action": "adb",
                "devices": devices,
                "command": command,
            }
        return await self._send_payload(payload)

    async def screenshot(self, devices: str) -> dict:
        """8.2.4 screen - Chụp ảnh màn hình."""
        if self.is_ws:
            payload = {
                "action": "screen",
                "devices": devices,
                "data": {"savePath": ""}
            }
        else:
            payload = {
                "action": "screen",
                "devices": devices,
            }
        return await self._send_payload(payload)

    async def pointer_event(self, devices: str, x: int, y: int, action_type: str = "click") -> dict:
        """
        8.2.5 pointerEvent - Điều khiển con trỏ (tap/click/swipe).
        action_type: "click", "swipe", "longPress"
        """
        if self.is_ws:
            w, h = await self._get_device_res(devices)
            x_pct = (x / w) * 100.0 if w > 0 else 50.0
            y_pct = (y / h) * 100.0 if h > 0 else 50.0
            type_val = "10"
            payload = {
                "action": "pointerEvent",
                "devices": devices,
                "data": {
                    "type": type_val,
                    "x": f"{x_pct:.1f}",
                    "y": f"{y_pct:.1f}"
                }
            }
        else:
            payload = {
                "action": "pointerEvent",
                "devices": devices,
                "data": {
                    "action": action_type,
                    "x": x,
                    "y": y,
                }
            }
        return await self._send_payload(payload)

    async def swipe(self, devices: str, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> dict:
        """Vuốt từ (x1,y1) đến (x2,y2)."""
        if self.is_ws:
            return await self.run_adb(devices, f"input swipe {x1} {y1} {x2} {y2} {duration}")
        else:
            payload = {
                "action": "pointerEvent",
                "devices": devices,
                "data": {
                    "action": "swipe",
                    "x": x1,
                    "y": y1,
                    "toX": x2,
                    "toY": y2,
                    "duration": duration,
                }
            }
            return await self._send_payload(payload)

    async def push_event(self, devices: str, event_type: str) -> dict:
        """
        8.2.6 pushEvent - Phím cứng nhanh.
        event_type: "home", "back", "recent", "volumeUp", "volumeDown", "power",
                    "lockScreen", "unlockScreen", "rotateScreen"
        """
        if self.is_ws:
            type_map = {"home": "2", "back": "3", "recent": "1"}
            type_val = type_map.get(event_type.lower())
            if type_val:
                payload = {
                    "action": "pushEvent",
                    "devices": devices,
                    "data": {"type": type_val}
                }
            else:
                payload = {
                    "action": "pushEvent",
                    "devices": devices,
                    "data": {"action": event_type}
                }
        else:
            payload = {
                "action": "pushEvent",
                "devices": devices,
                "data": {"action": event_type},
            }
        return await self._send_payload(payload)

    async def input_text(self, devices: str, text: str) -> dict:
        """8.2.19 inputText - Nhập text."""
        if self.is_ws:
            payload = {
                "action": "inputText",
                "devices": devices,
                "data": {"content": text}
            }
        else:
            payload = {
                "action": "inputText",
                "devices": devices,
                "text": text,
            }
        return await self._send_payload(payload)

    async def start_app(self, devices: str, package: str) -> dict:
        """8.2.14 startApk - Khởi chạy ứng dụng."""
        return await self._send_payload({
            "action": "startApk",
            "devices": devices,
            "packageName": package,
        })

    async def stop_app(self, devices: str, package: str) -> dict:
        """8.2.15 stopApk - Dừng ứng dụng."""
        return await self._send_payload({
            "action": "stopApk",
            "devices": devices,
            "packageName": package,
        })

    async def keyevent(self, devices: str, keycode: int) -> dict:
        """Gửi keyevent qua ADB shell."""
        return await self.run_adb(devices, f"input keyevent {keycode}")


# ══════════════════════════════════════════════════════════════════════════════
#  Test Functions
# ══════════════════════════════════════════════════════════════════════════════

async def find_xiaowei_port(host: str = "127.0.0.1", ports: list = None) -> int:
    """Tìm port XiaoWei đang chạy bằng cách thử kết nối lần lượt."""
    ports = ports or DEFAULT_PORTS
    log.info(f"🔍 Tìm XiaoWei API trên {host}...")

    for port in ports:
        if port == 22222:
            try:
                import websockets
                ws_url = f"ws://{host}:{port}/"
                ws = await asyncio.wait_for(websockets.connect(ws_url), timeout=2)
                async with ws:
                    await ws.send(json.dumps({"action": "list"}))
                    resp = await ws.recv()
                    data = json.loads(resp)
                    if data.get("code") == 10000 or isinstance(data.get("data"), list):
                        log.info(f"  ✅ Tìm thấy XiaoWei WebSocket API ở port {port}!")
                        return port
            except Exception:
                pass
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.post(f"http://{host}:{port}", json={"action": "list"})
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == 10000 or isinstance(data.get("data"), list):
                        log.info(f"  ✅ Tìm thấy XiaoWei API ở port {port}!")
                        return port
        except Exception:
            log.debug(f"  ⚫ Port {port}: không phản hồi")
            continue

    return 0


async def test_connection(tester: XiaoWeiAPITester) -> dict:
    """Test 1: Kiểm tra kết nối và lấy danh sách thiết bị."""
    log.info("=" * 60)
    log.info("TEST 1: Kiểm tra kết nối XiaoWei API")
    log.info(f"  URL: {tester.base_url}")
    log.info("=" * 60)

    result = await tester.get_devices()
    success = tester._is_success(result)

    if success:
        devices = result.get("data", [])
        log.info(f"  ✅ Kết nối thành công! code={result.get('code')}")
        log.info(f"  📱 Tìm thấy {len(devices)} thiết bị:")

        if isinstance(devices, list):
            for i, dev in enumerate(devices, 1):
                if isinstance(dev, dict):
                    serial = dev.get("serial", dev.get("id", dev.get("Serial", "?")))
                    model = dev.get("model", dev.get("Model", dev.get("name", "?")))
                    status = dev.get("status", dev.get("Status", "online"))
                    resolution = dev.get("resolution", "?")
                    log.info(f"    {i}. Serial: {serial} │ Model: {model} │ Resolution: {resolution} │ Status: {status}")
                else:
                    log.info(f"    {i}. {dev}")
        else:
            log.info(f"    Raw data: {json.dumps(result.get('data'), ensure_ascii=False)[:500]}")
    else:
        log.error(f"  ❌ Kết nối thất bại!")
        log.error(f"     Code: {result.get('code')}")
        log.error(f"     Message: {result.get('message')}")

    return {"success": success, "result": result}


async def test_api_endpoints(tester: XiaoWeiAPITester, device_serial: str) -> dict:
    """Test 2: Kiểm tra từng API endpoint trên 1 thiết bị."""
    log.info("")
    log.info("=" * 60)
    log.info(f"TEST 2: Kiểm tra API endpoints trên thiết bị: {device_serial}")
    log.info("=" * 60)

    results = {}

    # ── 2.1 ADB shell ────────────────────────────────────────────────────────
    log.info("\n  📋 2.1 Test ADB shell (lấy Android version)...")
    resp = await tester.run_adb(device_serial, "getprop ro.build.version.release")
    if tester._is_success(resp):
        output = resp.get("data", "?")
        log.info(f"    ✅ Android version: {str(output).strip()[:100]}")
        results["adb_shell"] = "PASS"
    else:
        log.error(f"    ❌ ADB shell thất bại: {resp.get('message')}")
        results["adb_shell"] = "FAIL"

    # ── 2.2 Lấy resolution ───────────────────────────────────────────────────
    log.info("\n  📋 2.2 Test ADB lấy resolution...")
    resp = await tester.run_adb(device_serial, "wm size")
    if tester._is_success(resp):
        log.info(f"    ✅ Resolution: {str(resp.get('data', '?')).strip()[:100]}")
        results["resolution"] = "PASS"
    else:
        log.warning(f"    ⚠️ Không lấy được: {resp.get('message')}")
        results["resolution"] = "WARN"

    # ── 2.3 Screenshot ───────────────────────────────────────────────────────
    log.info("\n  📋 2.3 Test Screenshot...")
    resp = await tester.screenshot(device_serial)
    if tester._is_success(resp):
        log.info(f"    ✅ Screenshot OK")
        results["screenshot"] = "PASS"
    else:
        log.warning(f"    ⚠️ Screenshot: {resp.get('message')}")
        results["screenshot"] = "WARN"

    # ── 2.4 pushEvent: Home ──────────────────────────────────────────────────
    log.info("\n  📋 2.4 Test pushEvent (Home)...")
    resp = await tester.push_event(device_serial, "home")
    if tester._is_success(resp):
        log.info(f"    ✅ Push Home thành công")
        results["push_home"] = "PASS"
    else:
        log.error(f"    ❌ Push Home thất bại: {resp.get('message')}")
        results["push_home"] = "FAIL"
    await asyncio.sleep(1)

    # ── 2.5 pushEvent: Back ──────────────────────────────────────────────────
    log.info("\n  📋 2.5 Test pushEvent (Back)...")
    resp = await tester.push_event(device_serial, "back")
    if tester._is_success(resp):
        log.info(f"    ✅ Push Back thành công")
        results["push_back"] = "PASS"
    else:
        log.error(f"    ❌ Push Back thất bại: {resp.get('message')}")
        results["push_back"] = "FAIL"
    await asyncio.sleep(0.5)

    # ── 2.6 pointerEvent: Click giữa màn hình ───────────────────────────────
    log.info("\n  📋 2.6 Test pointerEvent (Click giữa màn hình)...")
    resp = await tester.pointer_event(device_serial, 540, 960, "click")
    if tester._is_success(resp):
        log.info(f"    ✅ Click (540, 960) thành công")
        results["pointer_click"] = "PASS"
    else:
        log.error(f"    ❌ Click thất bại: {resp.get('message')}")
        results["pointer_click"] = "FAIL"
    await asyncio.sleep(0.5)

    # ── 2.7 Swipe ────────────────────────────────────────────────────────────
    log.info("\n  📋 2.7 Test Swipe (vuốt lên)...")
    resp = await tester.swipe(device_serial, 540, 1500, 540, 500, 400)
    if tester._is_success(resp):
        log.info(f"    ✅ Swipe UP thành công")
        results["swipe"] = "PASS"
    else:
        log.error(f"    ❌ Swipe thất bại: {resp.get('message')}")
        results["swipe"] = "FAIL"
    await asyncio.sleep(0.5)

    # ── 2.8 inputText ────────────────────────────────────────────────────────
    log.info("\n  📋 2.8 Test inputText...")
    resp = await tester.input_text(device_serial, "hello xiaowei test")
    if tester._is_success(resp):
        log.info(f"    ✅ inputText thành công")
        results["input_text"] = "PASS"
    else:
        log.warning(f"    ⚠️ inputText: {resp.get('message')} (có thể không có ô text focus)")
        results["input_text"] = "WARN"

    # ── 2.9 pushEvent: Home (về home sau khi test) ───────────────────────────
    log.info("\n  📋 2.9 Quay về Home screen...")
    await tester.push_event(device_serial, "home")
    await asyncio.sleep(0.5)

    # ── Tổng kết ─────────────────────────────────────────────────────────────
    log.info("\n  ─── Tổng kết API Endpoints ───")
    pass_count = sum(1 for v in results.values() if v == "PASS")
    warn_count = sum(1 for v in results.values() if v == "WARN")
    fail_count = sum(1 for v in results.values() if v == "FAIL")
    total = len(results)
    for name, status in results.items():
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(status, "?")
        log.info(f"    {icon} {name}: {status}")
    log.info(f"  Kết quả: {pass_count}/{total} PASS, {warn_count} WARN, {fail_count} FAIL")

    return results


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 2: Chạy thử đăng ký tài khoản (tùy chọn --register)
# ══════════════════════════════════════════════════════════════════════════════

async def test_registration_flow(tester: XiaoWeiAPITester, device_serial: str) -> dict:
    """
    Test 3: Chạy thử flow đăng ký tài khoản trên 1 thiết bị.
    Sử dụng XiaoWeiClient wrapper (tương thích với phone_bot.py).
    """
    log.info("")
    log.info("=" * 60)
    log.info(f"TEST 3: Đăng ký thử 1 tài khoản trên: {device_serial}")
    log.info("=" * 60)

    from src.config import CONFIG

    product_url = CONFIG.get("product_url", "")
    if not product_url:
        log.error("  ❌ Chưa cung cấp product_url trong config!")
        return {"status": "SKIPPED", "note": "Thiếu product_url"}

    # Cập nhật config để trỏ vào đúng XiaoWei API
    CONFIG["xiaowei"]["api_url"] = tester.base_url
    CONFIG["xiaowei"]["api_type"] = "xiaowei"
    CONFIG["xiaowei"]["enable"] = True

    from src.xiaowei_client import XiaoWeiClient
    from src.phone_bot import PhoneRegistrationBot

    client = XiaoWeiClient(
        api_url=tester.base_url,
        api_type="xiaowei",
        timeout=30,
    )

    bot = PhoneRegistrationBot(
        xiaowei=client,
        device_serial=device_serial,
        product_url=product_url,
    )

    log.info(f"  📧 Email: {TEST_ACCOUNT['email']}")
    log.info(f"  🔑 Password: {'*' * len(TEST_ACCOUNT['password'])}")
    log.info(f"  🔗 Product URL: {product_url[:80]}...")
    log.info("  🚀 Bắt đầu flow đăng ký...")

    start_time = time.time()
    result = await bot.register_one(TEST_ACCOUNT)
    elapsed = time.time() - start_time

    log.info("")
    status_icon = "✅" if result["status"] == "SUCCESS" else "❌"
    log.info(f"  {status_icon} Status: {result['status']}")
    log.info(f"  📝 Note: {result.get('note', 'N/A')}")
    log.info(f"  ⏱️ Thời gian: {elapsed:.1f}s")

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(description="Test XiaoWei Boxphone API (xiaowei.xin)")
    parser.add_argument("--host", default="127.0.0.1", help="API host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=0, help="API port (default: auto-detect)")
    parser.add_argument("--register", action="store_true", help="Chạy thử flow đăng ký sau khi test API")
    parser.add_argument("--device", default="", help="Serial thiết bị cụ thể (mặc định: chọn thiết bị đầu tiên)")
    args = parser.parse_args()

    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║   TEST XIAOWEI BOXPHONE API (xiaowei.xin)                  ║")
    log.info(f"║   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<52}║")
    log.info("╚══════════════════════════════════════════════════════════════╝")
    log.info("")

    # ── Tìm port ─────────────────────────────────────────────────────────────
    port = args.port
    if port == 0:
        port = await find_xiaowei_port(args.host)
        if port == 0:
            log.error("\n🛑 Không tìm thấy XiaoWei API trên các port phổ biến!")
            log.error(f"   Đã thử: {DEFAULT_PORTS}")
            log.error("   Kiểm tra:")
            log.error("   1. Phần mềm XiaoWei Boxphone đã mở chưa?")
            log.error("   2. Port API đúng chưa? (xem trong Cài đặt → HTTP API)")
            log.error("   3. Thử: python test_xiaowei_api.py --port <PORT_NUMBER>")

            # Thử scan thêm các port phổ biến
            log.info("\n   Đang quét thêm các port...")
            extra_ports = list(range(20000, 20030)) + list(range(22220, 22230))
            for p in extra_ports:
                try:
                    async with httpx.AsyncClient(timeout=1) as client:
                        resp = await client.post(f"http://{args.host}:{p}", json={"action": "list"})
                        if resp.status_code == 200:
                            log.info(f"   🔍 Phát hiện dịch vụ HTTP ở port {p}: {resp.text[:100]}")
                except Exception:
                    pass
            return

    tester = XiaoWeiAPITester(host=args.host, port=port)

    # ── Phase 1: Kiểm tra kết nối ────────────────────────────────────────────
    conn_result = await test_connection(tester)
    if not conn_result["success"]:
        log.error("\n🛑 Không kết nối được XiaoWei API!")
        return

    # Chọn thiết bị
    raw_data = conn_result["result"].get("data", [])
    if not raw_data:
        log.error("\n🛑 Không có thiết bị nào kết nối!")
        return

    # Parse serial từ response
    device_serial = args.device
    if not device_serial:
        if isinstance(raw_data, list) and len(raw_data) > 0:
            first_dev = raw_data[0]
            if isinstance(first_dev, dict):
                device_serial = first_dev.get("serial", first_dev.get("id", first_dev.get("Serial", "")))
            else:
                device_serial = str(first_dev)

    if not device_serial:
        log.error("\n🛑 Không xác định được serial thiết bị!")
        log.info(f"   Raw data: {json.dumps(raw_data, ensure_ascii=False)[:500]}")
        log.info("   Thử: python test_xiaowei_api.py --device <SERIAL>")
        return

    log.info(f"\n🎯 Chọn thiết bị test: {device_serial}")

    # ── Phase 1b: Test API endpoints ─────────────────────────────────────────
    api_results = await test_api_endpoints(tester, device_serial)

    # ── Phase 2: Đăng ký thử (nếu có --register) ────────────────────────────
    reg_result = {"status": "SKIPPED"}
    if args.register:
        reg_result = await test_registration_flow(tester, device_serial)
    else:
        log.info("\n📋 Bỏ qua test đăng ký. Thêm --register để chạy thử đăng ký.")

    # ── Tổng kết ─────────────────────────────────────────────────────────────
    log.info("")
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║                     TỔNG KẾT TEST                          ║")
    log.info("╠══════════════════════════════════════════════════════════════╣")
    api_ok = conn_result["success"]
    log.info(f"║  API Connection:     {'✅ PASS' if api_ok else '❌ FAIL':<38}║")
    all_pass = all(v != "FAIL" for v in api_results.values())
    log.info(f"║  API Endpoints:      {'✅ PASS' if all_pass else '⚠️ PARTIAL':<38}║")
    if args.register:
        log.info(f"║  Registration:       {reg_result.get('status', '?'):<38}║")
    log.info("╚══════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    asyncio.run(main())
