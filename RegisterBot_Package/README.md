# RegisterBot - Hướng dẫn sử dụng

## Cấu trúc package
```
RegisterBot_Package/
├── src/                ← Thư mục chứa các code logic chính
│   ├── config.py       ← ⚙️ Cấu hình hệ thống (Gmail, IP rotation...)
│   ├── gmail_otp.py    ← Xử lý lấy OTP từ Gmail
│   ├── excel_handler.py← Đọc/ghi Excel
│   ├── captcha_helper.py
│   └── mock_captcha.py
├── data/               ← Thư mục chứa data Excel chạy tool
│   ├── accounts.xlsx   ← Danh sách accounts cần đăng ký
│   └── results.xlsx    ← Kết quả sau khi chạy xong
├── logs/               ← Log ghi chép khi chạy (sinh tự động)
│   └── bot.log
├── BUILD.bat           ← Script để build file chạy .exe
├── main.py             ← Điểm chạy duy nhất (chạy file này)
├── .env.example        ← Mẫu cấu hình biến môi trường
└── README.md
```

## Bước 1 – Cấu hình (QUAN TRỌNG)
Mở `src/config.py` và chỉnh:
```python
"base_url":           "http://localhost:8000"   # URL server của bạn
"gmail_address":      "your@gmail.com"
"gmail_app_password": "xxxx xxxx xxxx xxxx"     # Gmail App Password (16 ký tự)
```

## Bước 2 – Điền data/accounts.xlsx
| name | email | password | proxy (tùy chọn) |
|------|-------|----------|------------------|
| Nguyen Van A | test@gmail.com | Pass123! | http://127.0.0.1:1081 |
| Tran Thi B | testb@gmail.com | Pass456! | socks5://127.0.0.1:1082 |

*Mẹo: Điền cột `proxy` giúp từng luồng chạy song song sử dụng một proxy riêng biệt, tránh bị trùng lặp IP hoặc gây xung đột mạng khi chạy nhiều trình duyệt đồng thời.*

## Bước 3 – Build .exe (chỉ cần làm 1 lần)
```
Double-click: BUILD.bat
```
Sau khi build xong, toàn bộ nằm trong thư mục `dist\`

## Bước 4 – Chạy
```
dist\RegisterBot.exe
```

## Cấu trúc dist\ sau khi build
```
dist/
├── RegisterBot.exe     ← File chạy chính
├── src/
│   └── config.py       ← Vẫn có thể cấu hình tại đây sau khi build
├── data/
│   └── accounts.xlsx   ← Điền accounts vào đây ở máy chạy tool
└── .env.example
```

## Biến môi trường (tuỳ chọn)
```bash
# Windows CMD
set APP_ENV=test
set CAPTCHA_TEST_KEY=TEST_BYPASS_123
RegisterBot.exe
```

## Troubleshooting
| Lỗi | Giải pháp |
|-----|-----------|
| `Python not found` | Cài Python 3.10+ từ python.org, tick "Add to PATH" |
| `playwright not found` | Chạy: `python -m playwright install chromium` |
| `IMAP auth error` | Kiểm tra Gmail App Password (16 ký tự) |
| `CSRF not found` | Mở DevTools F12, inspect form lấy đúng selector |
| `.exe bị antivirus chặn` | Thêm exception cho thư mục `dist\` trong Windows Defender |
