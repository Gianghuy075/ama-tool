"""
Configuration – chỉnh sửa các giá trị này theo hệ thống của bạn.
"""

CONFIG = {
    # ── Server ─────────────────────────────────────────────────────────────
    "base_url": "http://localhost:8000",  # đổi port nếu cần

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

