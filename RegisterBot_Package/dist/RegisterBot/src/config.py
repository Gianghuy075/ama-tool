"""
Configuration – chỉnh sửa các giá trị này theo hệ thống của bạn.
"""

CONFIG = {
    # ── Server ─────────────────────────────────────────────────────────────
    "base_url": "http://localhost:8000",  # đổi port nếu cần

    # ── Amazon Product URL ────────────────────────────────────────────────
    "product_url": "",  # Link sản phẩm Amazon JP (ví dụ: https://www.amazon.co.jp/dp/...)

    # ── Boxphone Proxy (Phương Án 1) ─────────────────────────────────────────
    "proxy": {
        "enable": False,                    # True = bật proxy, False = tắt proxy
        "server": "http://127.0.0.1:1080",  # Địa chỉ SOCKS5/HTTP Proxy server
        
        # API để ra lệnh đổi IP cho Boxphone (để trống nếu không sử dụng)
        # Hỗ trợ placeholder {index} hoặc {email} nếu cần truyền tham số phân biệt
        "change_ip_url": "",
        "change_ip_delay": 15,              # Thời gian chờ (giây) sau khi gọi đổi IP
        "verify_ip": False,                 # Kiểm tra IP thực tế trước/sau khi đổi
    },

    # ── Phone Farm (Tool Tự Tạo) ────────────────────────────────────────────
    # Key giữ tên "xiaowei" để tương thích ngược với code hiện tại
    "xiaowei": {
        "enable": True,                      # True = dùng điện thoại thật, False = dùng Playwright
        "api_type": "phone_farm",             # Luôn là "phone_farm" (tool tự tạo)
        "api_url": "http://127.0.0.1:5000",   # URL API Phone Farm (xem sidebar của tool)
        "devices": "all",                     # "all" hoặc danh sách serial: "serial1,serial2"
        "otp_source": "sms",                  # "sms" (từ SIM điện thoại) hoặc "gmail"
        "screenshot_dir": "data/screenshots", # Thư mục lưu ảnh chụp màn hình
        "tap_delay": [0.5, 1.5],              # Delay ngẫu nhiên giữa các thao tác (giây)

        # ── Human-like Typing Simulation ──────────────────────────────
        "human_typing": {
            # Delay giữa mỗi ký tự khi gõ (giây) — giả lập tốc độ gõ người thật
            "char_delay_min": 0.08,           # Tối thiểu 80ms giữa mỗi phím
            "char_delay_max": 0.22,           # Tối đa 220ms giữa mỗi phím

            # Thinking Time — độ trễ suy nghĩ trước khi bấm nút Tiếp tục/Xác nhận
            # Người thật cần 0.8-1.8s để nhìn lại rồi mới click
            "thinking_time_min": 0.8,         # Tối thiểu 0.8 giây
            "thinking_time_max": 1.8,         # Tối đa 1.8 giây

            # Typing Mistakes — giả lập gõ nhầm rồi xóa
            "typo_enabled": True,             # Bật/tắt tính năng gõ nhầm
            "typo_probability": 0.05,         # Xác suất gõ sai mỗi ký tự (5%)
            "typo_pause_before_backspace": 0.3,  # Dừng lại (giây) trước khi nhận ra sai và bấm Backspace
            "typo_pause_after_backspace": 0.15,  # Dừng lại (giây) sau khi bấm Backspace, trước khi gõ lại
        },
    },

    # ── Gmail IMAP ──────────────────────────────────────────────────────────
    # Dùng Gmail App Password (16 ký tự), KHÔNG phải password Gmail thật.
    # Tạo tại: https://myaccount.google.com/apppasswords
    "gmail_address": "gianghuy752003@gmail.com",
    "gmail_app_password": "sxkx pnpv rmum ymnc",  # App Password 16 ký tự
    "imap_server": "imap.gmail.com",

    # ── Browser ─────────────────────────────────────────────────────────────
    "headless": False,  # True = ẩn, False = hiện browser
    "max_concurrent_tasks": 3,      # Số lượng luồng trình duyệt chạy đồng thời tối đa

    # ── Timing ──────────────────────────────────────────────────────────────
    "otp_wait_seconds": 90,         # tối đa bao lâu chờ OTP
    "delay_between_accounts": 3,    # giây nghỉ giữa mỗi account

    # ── CSS Selectors (chỉnh theo HTML form thực tế của bạn) ────────────────
    "selectors": {
        "name":         'input[name="name"], input[name="full_name"], input#name',
        "email":        'input[name="email"], input[type="email"]',
        "password":     'input[name="password"], input[type="password"]',
        "submit":       'button[type="submit"], input[type="submit"]',
        "otp":          'input[name="otp"], input[name="code"], input.otp-input, input[maxlength="6"]',
        "otp_submit":   'button[type="submit"], input[type="submit"]',
    },

    # ── Nhận biết lỗi trên trang ────────────────────────────────────────────
    "error_selectors": [
        ".error", ".alert-danger", ".error-message",
        '[class*="error"]', '[class*="alert"]', ".flash-error",
    ],

    # ── Nhận biết thành công ─────────────────────────────────────────────────
    "success_url_patterns": [
        "/success", "/dashboard", "/home", "/welcome", "/complete",
    ],
    "success_selectors": [
        ".success", ".alert-success", '[class*="success"]',
    ],
}

import os
import json

def load_dynamic_config():
    config_path = os.path.join("data", "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                def update_recursive(d, u):
                    for k, v in u.items():
                        if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                            update_recursive(d[k], v)
                        else:
                            d[k] = v
                update_recursive(CONFIG, loaded)
        except Exception as e:
            print(f"[Config] Error loading data/config.json: {e}")

load_dynamic_config()

def save_dynamic_config(new_config_data):
    os.makedirs("data", exist_ok=True)
    config_path = os.path.join("data", "config.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(new_config_data, f, indent=4, ensure_ascii=False)
        def update_recursive(d, u):
            for k, v in u.items():
                if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                    update_recursive(d[k], v)
                else:
                    d[k] = v
        update_recursive(CONFIG, new_config_data)
        return True
    except Exception as e:
        print(f"[Config] Error saving config: {e}")
        return False

