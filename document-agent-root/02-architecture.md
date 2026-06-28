# 02 — Kiến Trúc Hệ Thống

## Sơ đồ tổng thể

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MÁY TÍNH WINDOWS                             │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  android_phone_farm/          (COMPONENT 1)                  │   │
│  │                                                              │   │
│  │  PyQt6 GUI ──► grid card hiển thị màn hình điện thoại        │   │
│  │  FastAPI  ──► REST server :5000 nhận lệnh điều khiển        │   │
│  │  ADBHandler ──► adb shell tap/swipe/text xuống device       │   │
│  │  ProxyManager ──► pool proxy, rotation, data quota          │   │
│  │  SQLite: database.db                                         │   │
│  └─────────────────────────┬────────────────────────────────────┘   │
│                            │ HTTP localhost:5000                    │
│                            │ POST /api/tap, /api/text, ...         │
│  ┌─────────────────────────▼────────────────────────────────────┐   │
│  │  RegisterBot_Package/         (COMPONENT 2)                  │   │
│  │                                                              │   │
│  │  Flask :8000 ──► web dashboard start/stop/monitor           │   │
│  │  PhoneBot ──► 8-step Amazon registration flow               │   │
│  │  GmailOTP ──► IMAP poll OTP mỗi 3s (timeout 90s)           │   │
│  │  ExcelHandler ──► đọc accounts.xlsx / ghi results.xlsx      │   │
│  │  SQLite: registered_accounts.db                              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
         │ USB (mỗi dây = 1 điện thoại, N máy song song)
         ↓
   [BoxPhone Android]  ──HTTPS──►  amazon.co.jp
```

## Luồng khởi động

```
1. python android_phone_farm/main.py
   → PyQt6 GUI hiện lên
   → FastAPI :5000 start (auto-scan port nếu bận)

2. User click "🔄 Quét Thiết Bị USB"
   → ADB quét device, cache 5 giây
   → scrcpy stream nhúng vào mỗi DeviceCard (Win32 HWND)

3. User click "🚀 Bắt đầu Tạo tài khoản"
   → Flask :8000 start
   → Browser mở localhost:8000
   → POST /api/start → PhoneBot chạy

4. PhoneBot gọi Phone Farm API :5000 → ADB → điện thoại → Amazon
```

## Cấu trúc thư mục

```
android_phone_farm/
├── main.py              Entry point PyQt6
├── api_server.py        FastAPI REST :5000
├── adb_handler.py       ADB wrapper (tap/swipe/text/keyevent/screenshot)
├── config.py            Auto-detect đường dẫn adb/scrcpy
├── config.json          User config (paths, bitrate, fps)
├── database.db          SQLite: proxy_pool, data_usage, proxy_config
├── ui/
│   ├── main_window.py   Layout + signals + background threads
│   ├── grid_view.py     DeviceCard grid (màn hình điện thoại)
│   ├── sidebar.py       Nút điều khiển + log + toggles
│   ├── proxy_manager.py Dialog proxy pool + data usage
│   └── overlay.py       Win32 window embedding
└── utils/
    ├── db_manager.py    SQLite CRUD
    └── helpers.py       Win32 API: embed/focus/resize scrcpy window

RegisterBot_Package/
├── main.py              Entry point (CLI/Web/Phone mode)
├── src/
│   ├── config.py        CONFIG dict (nguồn sự thật cấu hình)
│   ├── phone_bot.py     PhoneRegistrationBot — 8 bước đăng ký
│   ├── xiaowei_client.py HTTP client gọi Phone Farm API :5000
│   ├── gmail_otp.py     IMAP client đọc OTP
│   ├── excel_handler.py Đọc/ghi Excel
│   ├── db_handler.py    SQLite CRUD registered_accounts
│   ├── web_server.py    Flask :8000 + SSE log stream
│   ├── captcha_helper.py CAPTCHA bypass (production)
│   └── mock_captcha.py  Mock CAPTCHA (test mode)
├── data/
│   ├── accounts.xlsx         INPUT
│   ├── results.xlsx          OUTPUT
│   ├── registered_accounts.db SQLite
│   ├── config.json           Runtime override config
│   └── screenshots/          Ảnh chụp từng bước debug
└── logs/bot.log
```

## Giao tiếp giữa 2 component

```
RegisterBot (Flask :8000)
    └─► xiaowei_client.py
          └─► HTTP POST → Phone Farm API (:5000)
                    └─► adb_handler.py
                              └─► adb shell → Android device
```

**Điểm quan trọng:** Nếu port 5000 bị chiếm, `api_server.py` tự tìm port khác (5001, 5002...). Bot cần biết port thực tế — hiện lấy từ `CONFIG["xiaowei"]["api_url"]`.

## Hai chế độ hoạt động

| Chế độ | Kích hoạt | Mô tả |
|--------|-----------|-------|
| **Phone mode** | `xiaowei.enable = true` | Điều khiển điện thoại thật qua ADB — fingerprint thật, khó detect hơn |
| **Browser mode** | `xiaowei.enable = false` | Playwright chạy trên PC — nhanh hơn nhưng dễ bị detect |
