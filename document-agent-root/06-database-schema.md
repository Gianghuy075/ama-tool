# 06 — Database Schema

Dự án có 2 SQLite database hoàn toàn độc lập — mỗi component quản lý DB riêng.

---

## android_phone_farm/database.db

Quản lý proxy pool, data usage tracking, và cấu hình rotation.

```sql
-- Proxy pool: danh sách proxy sẵn sàng dùng
CREATE TABLE Proxy_Pool (
    id                INTEGER PRIMARY KEY,
    proxy_str         TEXT UNIQUE,     -- "IP:Port:User:Pass" (raw string nhập vào)
    ip                TEXT,
    port              INTEGER,
    username          TEXT,
    password          TEXT,
    status            TEXT DEFAULT 'live',   -- live | dead | checking
    assigned_phone_id TEXT UNIQUE            -- serial của device đang dùng proxy này
);

-- Theo dõi data usage từng device
CREATE TABLE Data_Usage (
    phone_id              TEXT PRIMARY KEY,  -- serial device
    total_bytes_used      INTEGER DEFAULT 0,
    last_read_raw_bytes   INTEGER DEFAULT 0, -- /proc/net/dev snapshot trước đó
    quota_limit_bytes     INTEGER DEFAULT 1073741824,  -- 1GB mặc định
    is_blocked            INTEGER DEFAULT 0  -- 1 nếu vượt quota
);

-- Config hệ thống (key-value store)
CREATE TABLE Proxy_Config (
    config_key   TEXT PRIMARY KEY,
    config_value TEXT
);
-- Các key có thể có:
-- rotation_enabled      '0' | '1'
-- rotation_interval_mins '10'
-- mode                  'static' | 'dynamic'
-- api_link              URL để gọi đổi IP
-- quota_limit_mb        '1024'
```

**CRUD helper:** `android_phone_farm/utils/db_manager.py`

---

## RegisterBot_Package/data/registered_accounts.db

Lưu kết quả đăng ký từng account theo batch.

```sql
CREATE TABLE registered_accounts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    group_name TEXT,          -- Tên batch (e.g. "Batch 2026-06-28")
    name       TEXT,          -- Tên đã đăng ký
    email      TEXT UNIQUE,   -- Email account (unique — không đăng ký trùng)
    password   TEXT,
    proxy      TEXT,          -- Proxy đã dùng
    status     TEXT,          -- "SUCCESS" | "FAILED"
    note       TEXT,          -- Lý do nếu FAILED
    timestamp  TEXT           -- "2026-06-28 14:30:45"
);
```

**CRUD helper:** `RegisterBot_Package/src/db_handler.py`

---

## Backup files

Hệ thống tự tạo backup trước khi overwrite:
- `data/registered_accounts_BACKUP_BEFORE_E2E_2026-06-21.db`
- `data/accounts_BACKUP_2026-06-21.xlsx`
- `data/results_BACKUP_BEFORE_E2E_2026-06-21.xlsx`

→ Chứng tỏ đã có batch chạy thực tế trước ngày 2026-06-21.
