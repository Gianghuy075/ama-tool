import asyncio
import sys
import os
import logging

# Add RegisterBot_Package to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGISTER_PKG = os.path.join(SCRIPT_DIR, "RegisterBot_Package")
if REGISTER_PKG not in sys.path:
    sys.path.insert(0, REGISTER_PKG)

from src.xiaowei_client import XiaoWeiClient

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s │ %(levelname)-5s │ %(message)s")
log = logging.getLogger("test_ws_integration")

async def test_integration():
    # Initialize Client with ws port
    client = XiaoWeiClient(api_url="ws://127.0.0.1:22222", api_type="xiaowei")
    
    log.info(f"Initialized client. api_type is: {client.api_type}")
    assert client.api_type == "xiaowei", "Failed to detect 'xiaowei' mode!"
    
    log.info("Testing get_devices()...")
    devices = await client.get_devices()
    log.info(f"Devices found: {devices}")
    
    if not devices:
        log.error("No devices found, cannot proceed with control tests.")
        return
        
    device = devices[0]["Serial"]
    log.info(f"Selected device for test: {device}")
    
    log.info("Testing run_adb_with_output (getprop ro.build.version.release)...")
    ver = await client.run_adb_with_output(device, "getprop ro.build.version.release")
    log.info(f"Android version: {ver.strip() if ver else 'N/A'}")
    
    log.info("Testing press_home()...")
    home_ok = await client.press_home(device)
    log.info(f"Press home success: {home_ok}")
    
    await asyncio.sleep(1)
    
    log.info("Testing tap (50%, 50%)...")
    tap_ok = await client.tap(device, 50.0, 50.0)
    log.info(f"Tap success: {tap_ok}")
    
    await asyncio.sleep(1)
    
    log.info("Testing screenshot...")
    screenshot_dir = os.path.join(SCRIPT_DIR, "logs")
    os.makedirs(screenshot_dir, exist_ok=True)
    ss_ok = await client.screenshot(device, screenshot_dir)
    log.info(f"Screenshot success: {ss_ok}")

if __name__ == "__main__":
    asyncio.run(test_integration())
