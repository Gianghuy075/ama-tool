# 03 — Input / Output

## INPUT

### accounts.xlsx
**Vị trí:** `RegisterBot_Package/data/accounts.xlsx`

| Cột | Bắt buộc | Mô tả |
|-----|----------|-------|
| `name` | Không | Tên đăng ký. Để trống → bot sinh tên tiếng Nhật ngẫu nhiên |
| `email` | **Có** | Email dùng để đăng ký Amazon |
| `password` | **Có** | Mật khẩu mong muốn |
| `proxy` | Không | `http://ip:port` hoặc `socks5://ip:port` — proxy riêng cho account này |

**Mẹo:** Dùng Gmail alias (`mailgoc+may03@gmail.com`) để nhiều account cùng nhận về 1 Gmail.

### Config
**Vị trí chính:** `RegisterBot_Package/src/config.py`
**Runtime override:** `RegisterBot_Package/data/config.json` (ghi đè khi chạy)

Các giá trị quan trọng:
```python
"product_url": "https://www.amazon.co.jp/dp/B0GXCRBL5J"  # ASIN sản phẩm
"gmail_address": "pokemontt0008@gmail.com"                # Gmail nhận OTP
"gmail_app_password": "xbga ffyf gzwe lntb"              # App Password 16 ký tự
"otp_wait_seconds": 90                                    # Timeout chờ OTP
"delay_between_accounts": 3                               # Giây nghỉ giữa 2 account
"max_concurrent_tasks": 3                                 # Browser mode: số tab song song
"xiaowei.devices": "R58M30WAT1F"                         # Device đang dùng (hoặc "all")
```

### Phần cứng (Phone mode)
- Điện thoại Android, đã bật USB Debugging
- ADB path: `C:\Users\Admin\Downloads\BoxPhone\platform-tools\adb.exe`
- scrcpy path: `C:\Users\Admin\Downloads\BoxPhone\scrcpy-win64-v4.0\scrcpy.exe`

### Proxy Pool (tùy chọn)
Nhập qua GUI Proxy Manager → lưu vào `android_phone_farm/database.db`
Format: `IP:Port:Username:Password` (mỗi dòng 1 proxy)

---

## OUTPUT

### results.xlsx
**Vị trí:** `RegisterBot_Package/data/results.xlsx`

| Cột | Mô tả |
|-----|-------|
| `name` | Tên đã đăng ký |
| `email` | Email account |
| `password` | Mật khẩu |
| `proxy` | Proxy đã dùng |
| `status` | **SUCCESS** (xanh) / **FAILED** (đỏ) |
| `note` | Lý do thất bại nếu FAILED |
| `timestamp` | Thời điểm hoàn tất |

### registered_accounts.db
**Vị trí:** `RegisterBot_Package/data/registered_accounts.db`

```sql
CREATE TABLE registered_accounts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT,          -- Tên batch (e.g. "Batch 2026-06-28")
    name       TEXT,
    email      TEXT UNIQUE,
    password   TEXT,
    proxy      TEXT,
    status     TEXT,          -- "SUCCESS" | "FAILED"
    note       TEXT,          -- Lý do nếu FAILED
    timestamp  TEXT           -- "2026-06-28 14:30:45"
);
```

### Screenshots debug
**Vị trí:** `RegisterBot_Package/data/screenshots/{serial}.png`
Chụp màn hình điện thoại tại từng bước — dùng để debug khi bot bị kẹt.

### Tài khoản Amazon thực tế
Mỗi record SUCCESS = 1 account Amazon JP hợp lệ, đã xác minh OTP, sẵn sàng dùng.

---

## LUỒNG DỮ LIỆU ĐẦY ĐỦ

```
accounts.xlsx
    │
    │ ExcelHandler.read_rows()
    ▼
[List of account dicts]
    │
    │ PhoneRegistrationManager
    │ phân phối task cho mỗi device
    ▼
PhoneRegistrationBot (1 instance / 1 device)
    │
    │ 8-step flow (xem 04-registration-flow.md)
    │
    ├──► Phone Farm API :5000 (tap/type/screenshot)
    │         └──► Android device → amazon.co.jp
    │
    └──► GmailOTPReader (IMAP)
              └──► Gmail inbox → OTP 6 số
    │
    ▼
Result { status, note, timestamp }
    │
    ├──► db_handler.save() → registered_accounts.db
    └──► excel_handler.write() → results.xlsx
```
