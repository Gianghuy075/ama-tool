import os
import sys
import json
import logging
import threading
import asyncio
import webbrowser
from collections import deque
from flask import Flask, jsonify, request, render_template, send_file
import pandas as pd

from src.config import CONFIG, save_dynamic_config
from src.excel_handler import ExcelHandler
from main import RegistrationBot

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

    def start(self):
        with self._lock:
            if self.status != "IDLE":
                return False, "Bot đang chạy hoặc đang trong quá trình dừng!"
            
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
            return True, "Đang gửi yêu cầu dừng tool..."

    def on_progress(self, result):
        self.results.append(result)
        if result["status"] == "SUCCESS":
            self.success += 1
        else:
            self.failed += 1

    def _run_thread(self):
        logging.info("[Runner] Bắt đầu luồng chạy ngầm của Bot...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            self.bot_instance = RegistrationBot()
            loop.run_until_complete(
                self.bot_instance.run_all(
                    input_xlsx="data/accounts.xlsx",
                    output_xlsx="data/results.xlsx",
                    on_progress=self.on_progress
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
    ok, msg = runner.start()
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
                
            df = pd.DataFrame(cleaned_data)
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

def run_server():
    port = 8000
    logging.info(f"Đang chạy máy chủ Flask ngầm tại: http://127.0.0.1:{port}")
    
    def start_flask():
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
        
    t = threading.Thread(target=start_flask, daemon=True)
    t.start()
    
    # Đợi Flask khởi động xong
    import time
    time.sleep(0.5)
    
    # Mở cửa sổ ứng dụng desktop bằng PyQt5 QWebEngineView (Chromium engine)
    import sys
    from PyQt5.QtCore import QUrl
    from PyQt5.QtWidgets import QApplication, QMainWindow
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    
    logging.info("Đang khởi chạy cửa sổ ứng dụng desktop...")
    
    # Khởi tạo Qt Application
    qt_app = QApplication(sys.argv)
    
    # Tạo cửa sổ chính
    window = QMainWindow()
    window.setWindowTitle("GDP RegisterBot - Control Panel")
    window.resize(1280, 800)
    
    # Tạo WebView và trỏ tới Flask URL
    webview = QWebEngineView()
    webview.setUrl(QUrl(f"http://127.0.0.1:{port}"))
    
    window.setCentralWidget(webview)
    window.show()
    
    # Chạy vòng lặp sự kiện Qt. Khi tắt cửa sổ, vòng lặp kết thúc và dừng toàn bộ app.
    sys.exit(qt_app.exec_())


