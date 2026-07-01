# AI Knowledge — Data Model

| Model/Table | Fields chính | Vai trò | File |
|---|---|---|---|
| `registered_accounts` | `group_name`, `name`, `email`, `password`, `proxy`, `status`, `note`, `timestamp` | Lưu kết quả account theo batch | `RegisterBot_Package/src/db_handler.py` |
| `Proxy_Pool` | `proxy_str`, `ip`, `port`, `username`, `password`, `status`, `assigned_phone_id` | Pool proxy và trạng thái gán | `android_phone_farm/utils/db_manager.py` |
| `Data_Usage` | `phone_id`, `total_bytes_used`, `last_read_raw_bytes`, `quota_limit_bytes`, `is_blocked` | Theo dõi lưu lượng theo device | `android_phone_farm/utils/db_manager.py` |
| `Proxy_Config` | `config_key`, `config_value` | KV config cho chế độ proxy rotation | `android_phone_farm/utils/db_manager.py` |
| `accounts.xlsx` row | `name`, `email`, `password`, `proxy` | Input batch account | `RegisterBot_Package/src/excel_handler.py` |
| `results.xlsx` row | `name`, `email`, `password`, `proxy`, `status`, `note`, `timestamp` | Output kết quả chạy | `RegisterBot_Package/src/excel_handler.py` |
