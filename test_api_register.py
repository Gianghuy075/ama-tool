"""
Test script: Kiểm tra kết nối Phone Farm API và chạy thử đăng ký 1 tài khoản trên 1 thiết bị.

Cách chạy:
    python test_api_register.py

Script sẽ:
  1. Kiểm tra kết nối API (GET /api/devices)
  2. Test từng endpoint cơ bản (tap, text, keyevent, swipe, adb, screenshot)
  3. Chạy thử flow đăng ký 1 tài khoản trên thiết bị đầu tiên
"""

import asyncio
import sys
import os
import time
import logging
import json
from datetime import datetime

# Thêm RegisterBot_Package vào path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTER_PKG = os.path.join(SCRIPT_DIR, "RegisterBot_Package")
if REGISTER_PKG not in sys.path:
    sys.path.insert(0, REGISTER_PKG)

from src.xiaowei_client import XiaoWeiClient
from src.config import CONFIG

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-5s │ %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("test_api")

# ── Config ───────────────────────────────────────────────────────────────────
API_URL = CONFIG.get("xiaowei", {}).get("api_url", "http://127.0.0.1:5000")

# Tài khoản test – thay đổi trước khi chạy thật
TEST_ACCOUNT = {
    "name": "",                                  # Để trống → tự sinh tên Nhật
    "email": "pokemontt0008+test01@gmail.com",   # Email test (dùng Gmail + alias)
    "password": "TestPass@2026!",                # Mật khẩu mạnh
}

# URL sản phẩm Amazon JP – thay bằng link thật
PRODUCT_URL = CONFIG.get("product_url", "")


# ══════════════════════════════════════════════════════════════════════════════
#  PHASE 1: Kiểm tra kết nối API cơ bản
# ══════════════════════════════════════════════════════════════════════════════

async def test_connection(client: XiaoWeiClient) -> dict:
    """Test 1: Kiểm tra kết nối và lấy danh sách thiết bị."""
    log.info("=" * 60)
    log.info("TEST 1: Kiểm tra kết nối API Phone Farm")
    log.info(f"  API URL: {client.api_url}")
    log.info("=" * 60)

    result = await client.test_connection()
    if result["success"]:
        log.info(f"  ✅ Kết nối thành công!")
        log.info(f"  📱 Tìm thấy {len(result['devices'])} thiết bị:")
        for i, dev in enumerate(result["devices"], 1):
            serial = dev.get("Serial", "?")
            model = dev.get("Model", "?")
            status = dev.get("Status", "?")
            streaming = "🟢" if dev.get("is_streaming") else "⚫"
            selected = "☑️" if dev.get("is_selected") else "☐"
            log.info(f"    {i}. {serial} │ {model} │ {status} │ Stream: {streaming} │ Selected: {selected}")
    else:
        log.error(f"  ❌ Kết nối thất bại: {result['message']}")

    return result


async def test_api_endpoints(client: XiaoWeiClient, device_serial: str) -> dict:
    """Test 2: Kiểm tra từng API endpoint riêng lẻ trên 1 thiết bị."""
    log.info("")
    log.info("=" * 60)
    log.info(f"TEST 2: Kiểm tra các API endpoint trên thiết bị: {device_serial}")
    log.info("=" * 60)

    results = {}

    # ── 2.1 ADB shell ────────────────────────────────────────────────────────
    log.info("\n  📋 2.1 Test ADB shell (lấy Android version)...")
    output = await client.run_adb_with_output(device_serial, "getprop ro.build.version.release")
    if output:
        log.info(f"    ✅ Android version: {output.strip()}")
        results["adb_shell"] = "PASS"
    else:
        log.error(f"    ❌ Không chạy được ADB shell")
        results["adb_shell"] = "FAIL"

    # ── 2.2 Lấy độ phân giải ─────────────────────────────────────────────────
    log.info("\n  📋 2.2 Test lấy độ phân giải màn hình...")
    res_output = await client.run_adb_with_output(device_serial, "wm size")
    if res_output:
        log.info(f"    ✅ Resolution: {res_output.strip()}")
        results["resolution"] = "PASS"
    else:
        log.error(f"    ❌ Không lấy được resolution")
        results["resolution"] = "FAIL"

    # ── 2.3 Screenshot ───────────────────────────────────────────────────────
    log.info("\n  📋 2.3 Test chụp ảnh màn hình...")
    screenshot_dir = os.path.join(SCRIPT_DIR, "test_screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)
    ss_result = await client.screenshot(device_serial, screenshot_dir)
    if ss_result:
        log.info(f"    ✅ Screenshot OK → {screenshot_dir}")
        results["screenshot"] = "PASS"
    else:
        log.warning(f"    ⚠️ Screenshot có thể thất bại (kiểm tra thư mục: {screenshot_dir})")
        results["screenshot"] = "WARN"

    # ── 2.4 Test Tap (click giữa màn hình) ───────────────────────────────────
    log.info("\n  📋 2.4 Test Tap (click giữa màn hình)...")
    tap_ok = await client.tap(device_serial, 50.0, 50.0)
    if tap_ok:
        log.info(f"    ✅ Tap (50%, 50%) thành công")
        results["tap"] = "PASS"
    else:
        log.error(f"    ❌ Tap thất bại")
        results["tap"] = "FAIL"

    await asyncio.sleep(0.5)

    # ── 2.5 Test Keyevent (nhấn Back) ────────────────────────────────────────
    log.info("\n  📋 2.5 Test Keyevent (nhấn nút Back)...")
    back_ok = await client.press_back(device_serial)
    if back_ok:
        log.info(f"    ✅ Press Back thành công")
        results["keyevent"] = "PASS"
    else:
        log.error(f"    ❌ Press Back thất bại")
        results["keyevent"] = "FAIL"

    await asyncio.sleep(0.5)

    # ── 2.6 Test Swipe (vuốt xuống) ──────────────────────────────────────────
    log.info("\n  📋 2.6 Test Swipe (vuốt xuống 1 lần)...")
    swipe_ok = await client.swipe(device_serial, "up")
    if swipe_ok:
        log.info(f"    ✅ Swipe UP (scroll down) thành công")
        results["swipe"] = "PASS"
    else:
        log.error(f"    ❌ Swipe thất bại")
        results["swipe"] = "FAIL"

    await asyncio.sleep(0.5)

    # ── 2.7 Test Text Input ──────────────────────────────────────────────────
    log.info("\n  📋 2.7 Test nhập text (gõ 'hello test')...")
    text_ok = await client.type_text(device_serial, "hello test")
    if text_ok:
        log.info(f"    ✅ Type text thành công")
        results["text_input"] = "PASS"
    else:
        log.warning(f"    ⚠️ Type text có thể thất bại (kiểm tra xem có ô nhập liệu đang focus không)")
        results["text_input"] = "WARN"

    # ── 2.8 Test Press Home ──────────────────────────────────────────────────
    log.info("\n  📋 2.8 Test nhấn Home...")
    home_ok = await client.press_home(device_serial)
    if home_ok:
        log.info(f"    ✅ Press Home thành công")
        results["home"] = "PASS"
    else:
        log.error(f"    ❌ Press Home thất bại")
        results["home"] = "FAIL"

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
#  PHASE 2: Chạy thử đăng ký 1 tài khoản
# ══════════════════════════════════════════════════════════════════════════════

async def test_registration(client: XiaoWeiClient, device_serial: str) -> dict:
    """Test 3: Chạy thử flow đăng ký 1 tài khoản Amazon JP trên 1 thiết bị."""
    log.info("")
    log.info("=" * 60)
    log.info(f"TEST 3: Đăng ký thử 1 tài khoản trên thiết bị: {device_serial}")
    log.info("=" * 60)

    if not PRODUCT_URL:
        log.error("  ❌ Chưa cung cấp PRODUCT_URL! Hãy cấu hình product_url trong config.")
        log.error("     Vào data/config.json hoặc sửa trực tiếp src/config.py")
        return {"status": "SKIPPED", "note": "Thiếu product_url"}

    log.info(f"  📧 Email: {TEST_ACCOUNT['email']}")
    log.info(f"  🔑 Password: {'*' * len(TEST_ACCOUNT['password'])}")
    log.info(f"  🔗 Product URL: {PRODUCT_URL[:80]}...")
    log.info("")

    from src.phone_bot import PhoneRegistrationBot

    bot = PhoneRegistrationBot(
        xiaowei=client,
        device_serial=device_serial,
        product_url=PRODUCT_URL,
    )

    log.info("  🚀 Bắt đầu chạy flow đăng ký...")
    start_time = time.time()

    result = await bot.register_one(TEST_ACCOUNT)

    elapsed = time.time() - start_time
    log.info("")
    log.info(f"  ─── Kết quả đăng ký ───")
    status_icon = "✅" if result["status"] == "SUCCESS" else "❌"
    log.info(f"    {status_icon} Status: {result['status']}")
    log.info(f"    📝 Note: {result.get('note', 'N/A')}")
    log.info(f"    📧 Email: {result.get('email', 'N/A')}")
    log.info(f"    📱 Device: {result.get('device', 'N/A')}")
    log.info(f"    ⏱️ Thời gian: {elapsed:.1f}s")
    log.info(f"    🕒 Timestamp: {result.get('timestamp', 'N/A')}")

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║   TEST PHONE FARM API & REGISTRATION FLOW                  ║")
    log.info(f"║   API: {API_URL:<53}║")
    log.info(f"║   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<52}║")
    log.info("╚══════════════════════════════════════════════════════════════╝")
    log.info("")

    client = XiaoWeiClient(api_url=API_URL, api_type="phone_farm", timeout=30)

    # ── Phase 1: Kiểm tra kết nối ────────────────────────────────────────────
    conn_result = await test_connection(client)
    if not conn_result["success"]:
        log.error("\n🛑 Không thể kết nối API. Kiểm tra:")
        log.error("   1. Phone Farm GUI đã chạy chưa?")
        log.error(f"   2. API Server đang chạy ở {API_URL}?")
        log.error("   3. Có thiết bị Android nào đang kết nối qua USB/WiFi?")
        return

    devices = conn_result["devices"]
    if not devices:
        log.error("\n🛑 Không có thiết bị nào kết nối. Cắm USB hoặc kết nối WiFi ADB.")
        return

    # Chọn thiết bị đầu tiên
    chosen_device = devices[0]["Serial"]
    log.info(f"\n🎯 Chọn thiết bị đầu tiên để test: {chosen_device}")

    # ── Phase 1b: Test từng API endpoint ─────────────────────────────────────
    api_results = await test_api_endpoints(client, chosen_device)

    # Kiểm tra xem có FAIL nào không
    critical_fails = [k for k, v in api_results.items() if v == "FAIL"]
    if critical_fails:
        log.warning(f"\n⚠️ Có {len(critical_fails)} endpoint FAIL: {critical_fails}")
        log.warning("   Bạn có muốn tiếp tục test đăng ký không? (Ctrl+C để dừng)")
        await asyncio.sleep(3)

    # ── Phase 2: Đăng ký thử ─────────────────────────────────────────────────
    log.info("\n" + "─" * 60)
    log.info("CHUẨN BỊ CHẠY THỬ ĐĂNG KÝ TÀI KHOẢN")
    log.info("─" * 60)

    if not PRODUCT_URL:
        log.warning("⚠️ product_url chưa được cấu hình.")
        log.warning("   Để test đăng ký, hãy cấu hình product_url trong:")
        log.warning("   - RegisterBot_Package/src/config.py")
        log.warning("   - Hoặc RegisterBot_Package/data/config.json")
        log.info("\n✅ Test API endpoints hoàn tất. Bỏ qua phần đăng ký do thiếu product_url.")
        return

    reg_result = await test_registration(client, chosen_device)

    # ── Tổng kết cuối ────────────────────────────────────────────────────────
    log.info("")
    log.info("╔══════════════════════════════════════════════════════════════╗")
    log.info("║                     TỔNG KẾT TEST                          ║")
    log.info("╠══════════════════════════════════════════════════════════════╣")
    log.info(f"║  API Connection:     {'✅ PASS' if conn_result['success'] else '❌ FAIL':<38}║")
    api_all_pass = all(v != "FAIL" for v in api_results.values())
    log.info(f"║  API Endpoints:      {'✅ PASS' if api_all_pass else '⚠️ PARTIAL':<38}║")
    log.info(f"║  Registration:       {reg_result['status']:<38}║")
    log.info("╚══════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    asyncio.run(main())
