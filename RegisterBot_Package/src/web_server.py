import os
import sys
import json
import logging
import threading
import asyncio
import webbrowser
from collections import deque
from datetime import datetime
from flask import Flask, jsonify, request, render_template, send_file
import pandas as pd

from src.config import CONFIG, save_dynamic_config
from src.excel_handler import ExcelHandler
from src.db_handler import init_db
init_db()

# Setup Flask paths dynamically (works for both dev run and PyInstaller bundle)
base_path = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(base_path, "web", "templates")
static_dir = os.path.join(base_path, "web", "static")

app = Flask(
    __name__,
    template_folder=template_dir,
    static_folder=static_dir,
    static_url_path="/static"
)

# Custom log handler to collect logs for real-time console streaming
class LogQueueHandler(logging.Handler):
    def __init__(self, maxlen=500):
        super().__init__()
        self.logs = deque(maxlen=maxlen)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.logs.append(msg)
        except Exception:
            pass

log_handler = LogQueueHandler()
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
log_handler.setFormatter(log_formatter)
logging.getLogger().addHandler(log_handler)

# Bot runner manager running Playwright in a background thread
class BotRunner:
    def __init__(self):
        self.status = "IDLE"  # IDLE, RUNNING, STOPPING
        self.total = 0
        self.success = 0
        self.failed = 0
        self.results = []
        self.bot_instance = None
        self._thread = None
        self._lock = threading.Lock()

    def start(self, group_name="", product_url=""):
        with self._lock:
            if self.status != "IDLE":
                return False, "Bot đang chạy hoặc đang trong quá trình dừng!"
            
            if not product_url or not product_url.strip():
                return False, "Vui lòng nhập link sản phẩm Amazon trước khi chạy!"

            try:
                # Ensure input file exists
                handler = ExcelHandler("data/accounts.xlsx")
                rows = handler.read_rows()
                self.total = len(rows)
            except Exception as e:
                return False, f"Không đọc được danh sách tài khoản: {e}"

            if self.total == 0:
                return False, "accounts.xlsx trống, vui lòng thêm tài khoản!"

            self.status = "RUNNING"
            self.success = 0
            self.failed = 0
            self.results = []
            self.group_name = group_name
            self.product_url = product_url.strip()
            
            self._thread = threading.Thread(target=self._run_thread, daemon=True)
            self._thread.start()
            return True, "Khởi chạy tool thành công!"

    def stop(self):
        with self._lock:
            if self.status != "RUNNING":
                return False, "Tool hiện tại không chạy!"
            self.status = "STOPPING"
            if self.bot_instance:
                self.bot_instance.should_stop = True
                request_stop = getattr(self.bot_instance, "request_stop", None)
                if callable(request_stop):
                    request_stop()
            return True, "Đang gửi yêu cầu dừng tool..."

    def on_progress(self, result):
        self.results.append(result)
        if result["status"] == "SUCCESS":
            self.success += 1
        else:
            self.failed += 1

    def _run_thread(self):
        logging.info("[Runner] Bắt đầu luồng chạy ngầm của Bot...")
        logging.info(f"[Runner] Product URL: {getattr(self, 'product_url', 'N/A')}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Kiểm tra chế độ: Phone (XiaoWei) hay Browser (Playwright)
            xiaowei_config = CONFIG.get("xiaowei", {})
            use_phone_mode = xiaowei_config.get("enable", False)

            if use_phone_mode:
                logging.info("[Runner] 📱 Chế độ PHONE (XiaoWei) đã bật!")
                from src.phone_bot import PhoneRegistrationManager
                self.bot_instance = PhoneRegistrationManager(product_url=getattr(self, "product_url", ""))
            else:
                logging.info("[Runner] 🖥️ Chế độ BROWSER (Playwright) đã bật!")
                from main import RegistrationBot
                self.bot_instance = RegistrationBot(product_url=getattr(self, "product_url", ""))

            loop.run_until_complete(
                self.bot_instance.run_all(
                    input_xlsx="data/accounts.xlsx",
                    output_xlsx="data/results.xlsx",
                    on_progress=self.on_progress,
                    group_name=getattr(self, "group_name", "")
                )
            )
        except Exception as e:
            logging.error(f"[Runner] Lỗi trong luồng chạy ngầm: {e}", exc_info=True)
        finally:
            self.status = "IDLE"
            self.bot_instance = None
            loop.close()
            logging.info("[Runner] Luồng chạy ngầm của Bot kết thúc.")

runner = BotRunner()


def _run_async(coro):
    """Chạy coroutine trong event loop tạm thời cho Flask route hoặc CLI helper."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _build_xiaowei_diagnostics_report(api_url: str, api_type: str, requested_device: str = "") -> dict:
    """Smoke diagnostics cho backend XiaoWei/Phone Farm trước khi chạy bot thật."""
    from src.xiaowei_client import XiaoWeiClient
    from src.screen_reader import ScreenReader

    xw_config = CONFIG.get("xiaowei", {})
    screenshot_dir = xw_config.get("screenshot_dir", "data/screenshots")
    diagnostics_dir = os.path.join("data", "diagnostics")
    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(diagnostics_dir, exist_ok=True)

    client = XiaoWeiClient(api_url=api_url, api_type=api_type)
    screen_reader = ScreenReader(client)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "timestamp": timestamp,
        "backend": client.api_type,
        "backend_label": client._backend_label(),
        "api_url": client.api_url,
        "requested_device": requested_device or "all",
        "selected_device": "",
        "overall_success": False,
        "steps": [],
    }

    def add_step(name: str, success: bool, detail: str, extra: dict = None):
        row = {"name": name, "success": bool(success), "detail": detail}
        if extra:
            row.update(extra)
        report["steps"].append(row)

    devices = await client.get_devices()
    if devices:
        add_step("get_devices", True, f"Tìm thấy {len(devices)} thiết bị", {"device_count": len(devices)})
    else:
        add_step("get_devices", False, "Không lấy được danh sách thiết bị")
        return report

    requested = (requested_device or "").strip()
    selected = None
    if requested and requested.lower() != "all":
        for dev in devices:
            serial = dev.get("serial") or dev.get("Serial")
            if serial == requested:
                selected = dev
                break
    if selected is None:
        selected = devices[0]

    serial = selected.get("serial") or selected.get("Serial") or ""
    report["selected_device"] = serial
    add_step("select_device", bool(serial), f"Dùng device '{serial}' để chẩn đoán")
    if not serial:
        return report

    wm_size = await client.run_adb_with_output(serial, "wm size")
    add_step(
        "adb_wm_size",
        bool(wm_size),
        "Đọc được độ phân giải thiết bị" if wm_size else "Không đọc được output của 'wm size'",
        {"output_preview": (wm_size or "")[:200]},
    )

    chrome_packages = await client.run_adb_with_output(serial, "pm list packages com.android.chrome")
    add_step(
        "adb_pm_list_packages",
        bool(chrome_packages),
        "Đọc được package list" if chrome_packages else "Không đọc được package list",
        {"output_preview": (chrome_packages or "")[:200]},
    )

    screenshot_path = os.path.join(screenshot_dir, f"{file_stamp}_{serial}_diagnostic.png")
    screenshot_ok = await client.screenshot(serial, screenshot_path)
    screenshot_exists = False
    if screenshot_ok:
        for _ in range(10):
            if os.path.exists(screenshot_path):
                screenshot_exists = True
                break
            await asyncio.sleep(0.2)
    add_step(
        "screenshot",
        screenshot_ok and screenshot_exists,
        f"Lưu screenshot tại {screenshot_path}" if screenshot_ok else "Chụp screenshot thất bại",
        {"path": screenshot_path},
    )

    xml = await screen_reader.dump_ui(serial)
    add_step(
        "uiautomator_dump",
        bool(xml),
        f"Dump UI thành công ({len(xml)} chars)" if xml else "Không dump được UI XML",
        {"xml_preview": (xml or "")[:300]},
    )

    if xml:
        text_found = screen_reader.has_any_text(xml, ["Amazon", "メール", "Email", "Chrome", "Firefox"])
        add_step(
            "ui_text_probe",
            bool(text_found),
            f"Tìm thấy text gợi ý: {text_found}" if text_found else "Không thấy text gợi ý trong XML",
        )

    report["overall_success"] = all(step["success"] for step in report["steps"])
    report_path = os.path.join(diagnostics_dir, f"xiaowei_diagnostics_{file_stamp}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    report["report_path"] = report_path
    return report


def run_xiaowei_diagnostics_sync(api_url: str = None, api_type: str = None, requested_device: str = "") -> dict:
    """Sync helper để web route/CLI gọi diagnostics dùng chung logic."""
    xw_config = CONFIG.get("xiaowei", {})
    final_api_url = (api_url or xw_config.get("api_url", "http://127.0.0.1:22222")).strip()
    final_api_type = (api_type or xw_config.get("api_type", "xiaowei")).strip()
    return _run_async(_build_xiaowei_diagnostics_report(final_api_url, final_api_type, requested_device=requested_device))

@app.after_request
def add_header(response):
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Flask API Web Routes
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def get_status():
    return jsonify({
        "status": runner.status,
        "total": runner.total,
        "success": runner.success,
        "failed": runner.failed,
        "results": runner.results
    })

@app.route("/api/bot/start", methods=["POST"])
def bot_start():
    data = request.json or {}
    group_name = data.get("group_name", "")
    product_url = data.get("product_url", "")
    ok, msg = runner.start(group_name=group_name, product_url=product_url)
    return jsonify({"success": ok, "message": msg})

@app.route("/api/bot/stop", methods=["POST"])
def bot_stop():
    ok, msg = runner.stop()
    return jsonify({"success": ok, "message": msg})

@app.route("/api/logs", methods=["GET"])
def get_logs():
    since = request.args.get("since", default=0, type=int)
    all_logs = list(log_handler.logs)
    new_logs = all_logs[since:]
    return jsonify({
        "logs": new_logs,
        "next_index": len(all_logs)
    })

@app.route("/api/accounts", methods=["GET", "POST"])
def manage_accounts():
    if request.method == "GET":
        try:
            if not os.path.exists("data/accounts.xlsx"):
                # Initial dummy excel creation
                handler = ExcelHandler("data/accounts.xlsx")
                handler.read_rows()
            handler = ExcelHandler("data/accounts.xlsx")
            rows = handler.read_rows()
            return jsonify({"success": True, "accounts": rows})
        except Exception as e:
            return jsonify({"success": False, "message": f"Không thể đọc file accounts.xlsx: {e}"})
    
    elif request.method == "POST":
        try:
            data = request.json  # expectation: list of account dicts
            if not isinstance(data, list):
                return jsonify({"success": False, "message": "Dữ liệu không đúng định dạng list"})
            
            # Map columns to lowercase
            cleaned_data = []
            for item in data:
                cleaned_item = {
                    "name": item.get("name", "").strip(),
                    "email": item.get("email", "").strip(),
                    "password": item.get("password", "").strip(),
                    "proxy": item.get("proxy", "").strip() if item.get("proxy") else ""
                }
                cleaned_data.append(cleaned_item)
                
            df = pd.DataFrame(cleaned_data, columns=["name", "email", "password", "proxy"])
            os.makedirs("data", exist_ok=True)
            df.to_excel("data/accounts.xlsx", index=False)
            return jsonify({"success": True, "message": "Đã lưu danh sách accounts thành công!"})
        except Exception as e:
            return jsonify({"success": False, "message": f"Lỗi khi lưu Excel: {e}"})

@app.route("/api/accounts/upload", methods=["POST"])
def upload_accounts():
    try:
        file = request.files.get("file")
        if not file:
            return jsonify({"success": False, "message": "Không tìm thấy file tải lên!"})
        
        os.makedirs("data", exist_ok=True)
        temp_path = "data/accounts_temp.xlsx"
        file.save(temp_path)
        
        # Parse Excel using smart mapping
        try:
            accounts = ExcelHandler.parse_excel(temp_path)
        except Exception as e:
            return jsonify({"success": False, "message": f"Không thể đọc hoặc phân tích file Excel: {e}"})
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            
        return jsonify({
            "success": True,
            "message": f"Đọc thành công {len(accounts)} tài khoản từ file Excel. Vui lòng kiểm tra và bấm 'Lưu Thay Đổi' để áp dụng.",
            "accounts": accounts
        })
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi hệ thống khi tải file: {e}"})


@app.route("/api/config", methods=["GET", "POST"])
def manage_config():
    if request.method == "GET":
        return jsonify(CONFIG)
    
    elif request.method == "POST":
        try:
            new_conf = request.json
            if not isinstance(new_conf, dict):
                return jsonify({"success": False, "message": "Dữ liệu cấu hình phải là một đối tượng JSON"})
            
            # Simple sanitizations
            if "max_concurrent_tasks" in new_conf:
                new_conf["max_concurrent_tasks"] = int(new_conf["max_concurrent_tasks"])
            if "otp_wait_seconds" in new_conf:
                new_conf["otp_wait_seconds"] = int(new_conf["otp_wait_seconds"])
            if "delay_between_accounts" in new_conf:
                new_conf["delay_between_accounts"] = int(new_conf["delay_between_accounts"])
            
            if save_dynamic_config(new_conf):
                return jsonify({"success": True, "message": "Đã lưu cấu hình mới thành công!"})
            else:
                return jsonify({"success": False, "message": "Ghi cấu hình thất bại."})
        except Exception as e:
            return jsonify({"success": False, "message": f"Lỗi lưu cấu hình: {e}"})

@app.route("/api/download/results", methods=["GET"])
def download_results():
    results_path = "data/results.xlsx"
    if os.path.exists(results_path):
        return send_file(results_path, as_attachment=True, download_name="results.xlsx")
    return jsonify({"success": False, "message": "Chưa có file kết quả kết xuất."}), 404

@app.route("/api/download/accounts", methods=["GET"])
def download_accounts():
    accounts_path = "data/accounts.xlsx"
    if os.path.exists(accounts_path):
        return send_file(accounts_path, as_attachment=True, download_name="accounts.xlsx")
    return jsonify({"success": False, "message": "Chưa có file danh sách tài khoản."}), 404

@app.route("/api/registered", methods=["GET"])
def get_registered_accounts():
    try:
        from src.db_handler import get_registered_accounts
        records = get_registered_accounts()
        return jsonify({"success": True, "accounts": records})
    except Exception as e:
        return jsonify({"success": False, "message": f"Không thể đọc danh sách tài khoản đã đăng ký: {e}"})

@app.route("/api/registered/clear", methods=["POST"])
def clear_registered_accounts():
    try:
        from src.db_handler import clear_registered_accounts
        ok = clear_registered_accounts()
        if ok:
            return jsonify({"success": True, "message": "Đã xóa toàn bộ dữ liệu quản trị tài khoản!"})
        return jsonify({"success": False, "message": "Không thể xóa dữ liệu từ cơ sở dữ liệu."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Không thể xóa dữ liệu: {e}"})

@app.route("/api/download/registered", methods=["GET"])
def download_registered_accounts():
    try:
        from src.db_handler import export_registered_accounts_to_excel
        excel_path = "data/registered_accounts.xlsx"
        export_registered_accounts_to_excel(excel_path)
        if os.path.exists(excel_path):
            return send_file(excel_path, as_attachment=True, download_name="registered_accounts.xlsx")
        return jsonify({"success": False, "message": "Chưa có danh sách tài khoản đã đăng ký."}), 404
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi xuất file Excel: {e}"})

@app.route("/api/registered/groups", methods=["GET"])
def get_registered_groups_api():
    try:
        from src.db_handler import get_registered_groups
        groups = get_registered_groups()
        return jsonify({"success": True, "groups": groups})
    except Exception as e:
        return jsonify({"success": False, "message": f"Không thể lấy danh sách nhóm: {e}"})

# ── XiaoWei Boxphone API endpoints ──────────────────────────────────────────

@app.route("/api/xiaowei/devices", methods=["GET"])
def get_xiaowei_devices():
    """Lấy danh sách thiết bị đang kết nối qua XiaoWei hoặc Phone Farm."""
    try:
        import asyncio
        from src.xiaowei_client import XiaoWeiClient
        xw_config = CONFIG.get("xiaowei", {})
        api_url = xw_config.get("api_url", "http://127.0.0.1:22222")
        api_type = xw_config.get("api_type", "xiaowei")
        client = XiaoWeiClient(api_url=api_url, api_type=api_type)

        devices = _run_async(client.get_devices())

        return jsonify({"success": True, "devices": devices})
    except Exception as e:
        return jsonify({"success": False, "message": f"Không thể kết nối: {e}", "devices": []})

@app.route("/api/xiaowei/test", methods=["POST"])
def test_xiaowei_connection():
    """Kiểm tra kết nối tới XiaoWei/Phone Farm API."""
    try:
        import asyncio
        from src.xiaowei_client import XiaoWeiClient
        data = request.json or {}
        xw_config = CONFIG.get("xiaowei", {})
        api_url = data.get("api_url", xw_config.get("api_url", "http://127.0.0.1:22222"))
        api_type = data.get("api_type", xw_config.get("api_type", "xiaowei"))
        client = XiaoWeiClient(api_url=api_url, api_type=api_type)

        result = _run_async(client.test_connection())

        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi kiểm tra kết nối: {e}", "devices": []})

@app.route("/api/xiaowei/screenshot", methods=["POST"])
def take_xiaowei_screenshot():
    """Chụp ảnh màn hình thiết bị qua XiaoWei hoặc Phone Farm."""
    try:
        import asyncio
        from src.xiaowei_client import XiaoWeiClient
        data = request.json or {}
        device = data.get("device", "all")
        xw_config = CONFIG.get("xiaowei", {})
        api_url = xw_config.get("api_url", "http://127.0.0.1:22222")
        api_type = xw_config.get("api_type", "xiaowei")
        screenshot_dir = xw_config.get("screenshot_dir", "data/screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)

        client = XiaoWeiClient(api_url=api_url, api_type=api_type)
        success = _run_async(client.screenshot(device, screenshot_dir))

        if success:
            return jsonify({"success": True, "message": f"Đã chụp ảnh thiết bị {device}"})
        return jsonify({"success": False, "message": "Chụp ảnh thất bại"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi: {e}"})


@app.route("/api/xiaowei/diagnostics", methods=["POST"])
def run_xiaowei_diagnostics_api():
    """Chạy smoke diagnostics cho backend XiaoWei/Phone Farm và lưu report JSON."""
    try:
        data = request.json or {}
        report = run_xiaowei_diagnostics_sync(
            api_url=data.get("api_url"),
            api_type=data.get("api_type"),
            requested_device=data.get("device", ""),
        )
        status_code = 200 if report.get("overall_success") else 207
        return jsonify(report), status_code
    except Exception as e:
        return jsonify({
            "overall_success": False,
            "message": f"Lỗi diagnostics: {e}",
            "steps": [],
        }), 500

@app.route("/api/registered/save", methods=["POST"])
def save_registered_accounts_api():
    try:
        data = request.json or {}
        results = data.get("results", [])
        group_name = data.get("group_name", "").strip()
        if not results:
            return jsonify({"success": False, "message": "Không tìm thấy dữ liệu tài khoản để lưu."})
        
        from src.db_handler import save_registered_accounts
        save_registered_accounts(results, group_name)
        return jsonify({"success": True, "message": f"Đã lưu thành công {len(results)} tài khoản vào nhóm '{group_name or 'Mặc định'}'."})
    except Exception as e:
        return jsonify({"success": False, "message": f"Lỗi khi lưu tài khoản vào cơ sở dữ liệu: {e}"})

def run_server():
    port = 8000
    logging.info(f"Đang chạy máy chủ Flask tại: http://127.0.0.1:{port}")
    
    url = f"http://127.0.0.1:{port}"
    
    # Mở trình duyệt mặc định sau 1 giây (đợi Flask khởi động)
    def open_browser():
        import time
        time.sleep(1.0)
        logging.info(f"Đang mở trình duyệt tại: {url}")
        webbrowser.open(url)
    
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()
    
    # Chạy Flask trực tiếp trên main thread (blocking)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
