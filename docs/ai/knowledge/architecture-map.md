# AI Knowledge — Architecture Map

## Architecture summary

Repo hiện có 2 khối vận hành chính:

- `android_phone_farm/`: desktop app quản lý thiết bị, stream màn hình, ADB wrapper và REST API
- `RegisterBot_Package/`: dashboard Flask, orchestration batch, Gmail OTP, Excel/SQLite output, phone/browser registration flows

Ngoài ra còn có:

- `docs/project/source/`: nơi lưu legacy project docs và raw notes đã archive
- `docs/ai/source/legacy-agent-context/`: nơi lưu legacy AI context và session history

## Module map

| Module | Vai trò | Folder/File |
|---|---|---|
| Phone Farm GUI | Điều khiển desktop, grid device, sidebar, proxy manager | `android_phone_farm/ui/` |
| Phone Farm API | Cấp REST API điều khiển thiết bị | `android_phone_farm/api_server.py` |
| ADB handler | Thực thi tap/swipe/text/keyevent/screenshot | `android_phone_farm/adb_handler.py` |
| Proxy database layer | Quản lý proxy pool, data usage, config | `android_phone_farm/utils/db_manager.py` |
| RegisterBot orchestrator | Điều phối batch theo device/mode | `RegisterBot_Package/src/phone_bot.py`, `main.py` |
| API client | Gọi Phone Farm API hoặc legacy xiaowei WS | `RegisterBot_Package/src/xiaowei_client.py` |
| OTP reader | Đọc OTP qua Gmail IMAP | `RegisterBot_Package/src/gmail_otp.py` |
| Dashboard | Start/stop/config/log/result UI | `RegisterBot_Package/src/web_server.py`, `src/web/` |
| Result persistence | Ghi SQLite và Excel output | `RegisterBot_Package/src/db_handler.py`, `src/excel_handler.py` |
| Screen reader | Đọc `uiautomator dump` để verify UI | `RegisterBot_Package/src/screen_reader.py` |
