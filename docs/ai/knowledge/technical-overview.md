# AI Knowledge — Technical Overview

## Tech stack

- Python 3.10+
- PyQt6 cho desktop GUI
- FastAPI/Uvicorn cho REST API phía phone farm
- Flask cho dashboard RegisterBot
- SQLite cho dữ liệu cục bộ
- ADB và scrcpy cho điều khiển điện thoại
- Pandas/OpenPyXL cho Excel
- Playwright cho browser mode

## How to run/build/test

- Phone Farm: chạy `android_phone_farm/main.py` trên Windows
- RegisterBot dashboard: chạy `RegisterBot_Package/main.py` hoặc `RegisterBot_Package/src/web_server.py` tùy flow
- Build artifact: có dấu vết PyInstaller trong `build/` và `dist/`
- Test runtime thật cần Windows + Android devices + ADB + scrcpy + Gmail IMAP

## Important files

- `android_phone_farm/api_server.py`
- `android_phone_farm/adb_handler.py`
- `android_phone_farm/utils/db_manager.py`
- `RegisterBot_Package/src/phone_bot.py`
- `RegisterBot_Package/src/xiaowei_client.py`
- `RegisterBot_Package/src/screen_reader.py`
- `RegisterBot_Package/src/gmail_otp.py`
- `RegisterBot_Package/src/web_server.py`
- `RegisterBot_Package/src/db_handler.py`

## Cần xác nhận

- Entry point chuẩn mà team đang dùng hằng ngày cho RegisterBot là file nào
- Bộ test nào được xem là chính thức ngoài manual test trên Windows
