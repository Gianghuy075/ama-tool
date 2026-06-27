import sqlite3
import os
import random
import logging
from typing import List, Dict, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.db")

def get_connection():
    """Tạo kết nối tới SQLite Database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Khởi tạo cấu trúc các bảng dữ liệu nếu chưa tồn tại."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Bảng lưu Pool Proxy
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Proxy_Pool (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        proxy_str TEXT UNIQUE,
        ip TEXT,
        port INTEGER,
        username TEXT,
        password TEXT,
        status TEXT DEFAULT 'live',
        assigned_phone_id TEXT UNIQUE
    )
    """)
    
    # 2. Bảng lưu đo lường dung lượng Data tiêu thụ
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Data_Usage (
        phone_id TEXT PRIMARY KEY,
        total_bytes_used INTEGER DEFAULT 0,
        last_read_raw_bytes INTEGER DEFAULT 0,
        quota_limit_bytes INTEGER DEFAULT 1073741824, -- 1GB mặc định
        is_blocked INTEGER DEFAULT 0
    )
    """)
    
    # 3. Bảng lưu cấu hình Proxy toàn cục
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Proxy_Config (
        config_key TEXT PRIMARY KEY,
        config_value TEXT
    )
    """)
    
    # Thiết lập một số cấu hình mặc định nếu bảng trống
    cursor.execute("INSERT OR IGNORE INTO Proxy_Config (config_key, config_value) VALUES ('mode', 'static')")
    cursor.execute("INSERT OR IGNORE INTO Proxy_Config (config_key, config_value) VALUES ('rotation_enabled', '0')")
    cursor.execute("INSERT OR IGNORE INTO Proxy_Config (config_key, config_value) VALUES ('rotation_interval_mins', '10')")
    cursor.execute("INSERT OR IGNORE INTO Proxy_Config (config_key, config_value) VALUES ('api_link', '')")
    cursor.execute("INSERT OR IGNORE INTO Proxy_Config (config_key, config_value) VALUES ('quota_limit_mb', '1024')")
    
    conn.commit()
    conn.close()
    logging.info("Khởi tạo SQLite Database thành công.")

# ==========================================
# PHẦN QUẢN LÝ CẤU HÌNH (Proxy_Config)
# ==========================================

def get_config(key: str, default: str = "") -> str:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT config_value FROM Proxy_Config WHERE config_key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row["config_value"] if row else default

def set_config(key: str, value: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO Proxy_Config (config_key, config_value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

# ==========================================
# PHẦN QUẢN LÝ PROXY POOL (Proxy_Pool)
# ==========================================

def import_proxies(raw_text: str) -> Tuple[int, int]:
    """
    Parse danh sách proxy thô từ Textarea và import vào DB.
    Định dạng: IP:Port:User:Pass hoặc IP:Port
    Trả về Tuple (số proxy được thêm mới, tổng số dòng hợp lệ).
    """
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    inserted = 0
    valid_count = 0
    
    conn = get_connection()
    cursor = conn.cursor()
    
    for line in lines:
        parts = line.split(":")
        if len(parts) >= 2:
            valid_count += 1
            ip = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                continue
            
            username = parts[2] if len(parts) >= 3 else None
            password = parts[3] if len(parts) >= 4 else None
            
            try:
                cursor.execute(
                    "INSERT INTO Proxy_Pool (proxy_str, ip, port, username, password) VALUES (?, ?, ?, ?, ?)",
                    (line, ip, port, username, password)
                )
                inserted += 1
            except sqlite3.IntegrityError:
                # Đã tồn tại proxy này, bỏ qua
                pass
                
    conn.commit()
    conn.close()
    return inserted, valid_count

def get_all_proxies() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Proxy_Pool")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def clear_proxy_pool():
    conn = get_connection()
    cursor = conn.cursor()
    # Reset liên kết trên các thiết bị trước
    cursor.execute("UPDATE Proxy_Pool SET assigned_phone_id = NULL")
    cursor.execute("DELETE FROM Proxy_Pool")
    conn.commit()
    conn.close()

def update_proxy_status(proxy_id: int, status: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Proxy_Pool SET status = ? WHERE id = ?", (status, proxy_id))
    conn.commit()
    conn.close()

# ==========================================
# PHẦN PHÂN PHỐI PROXY (Static / Dynamic)
# ==========================================

def allocate_proxy(serial: str, connected_serials: List[str]) -> Optional[Dict]:
    """
    Cấp phát proxy cho một thiết bị theo chế độ hiện tại.
    - Static: Phân bổ tuần tự dựa theo thứ tự của serial và proxy.
    - Dynamic Random: Bốc ngẫu nhiên proxy đang live và chưa bị chiếm.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Đọc chế độ phân phối từ Config
    cursor.execute("SELECT config_value FROM Proxy_Config WHERE config_key = 'mode'")
    mode = cursor.fetchone()["config_value"]
    
    assigned_proxy = None
    
    try:
        if mode == "static":
            # Chế độ Static Binding
            # Lấy tất cả proxy 'live'
            cursor.execute("SELECT * FROM Proxy_Pool WHERE status = 'live' ORDER BY id ASC")
            proxies = cursor.fetchall()
            
            if proxies:
                # Sắp xếp danh sách serial các máy đang cắm
                sorted_serials = sorted(list(set(connected_serials)))
                if serial in sorted_serials:
                    idx = sorted_serials.index(serial)
                    # Lấy proxy theo index tuần tự (vòng lặp chia dư nếu thiếu proxy)
                    proxy_to_assign = proxies[idx % len(proxies)]
                    
                    # Cập nhật liên kết trong DB
                    cursor.execute("UPDATE Proxy_Pool SET assigned_phone_id = NULL WHERE assigned_phone_id = ?", (serial,))
                    cursor.execute("UPDATE Proxy_Pool SET assigned_phone_id = ? WHERE id = ?", (serial, proxy_to_assign["id"]))
                    assigned_proxy = dict(proxy_to_assign)
                    assigned_proxy["assigned_phone_id"] = serial
                    
        else:
            # Chế độ Dynamic Random Pooling (Mutex Lock)
            # Kiểm tra xem máy này đã được gán proxy nào chưa
            cursor.execute("SELECT * FROM Proxy_Pool WHERE assigned_phone_id = ?", (serial,))
            existing = cursor.fetchone()
            
            if existing:
                assigned_proxy = dict(existing)
            else:
                # Bốc ngẫu nhiên một proxy rảnh
                cursor.execute("SELECT * FROM Proxy_Pool WHERE status = 'live' AND assigned_phone_id IS NULL")
                free_proxies = cursor.fetchall()
                
                if free_proxies:
                    chosen = random.choice(free_proxies)
                    cursor.execute("UPDATE Proxy_Pool SET assigned_phone_id = ? WHERE id = ?", (serial, chosen["id"]))
                    assigned_proxy = dict(chosen)
                    assigned_proxy["assigned_phone_id"] = serial
                    
        if assigned_proxy:
            conn.commit()
    except Exception as e:
        logging.error(f"Lỗi khi allocate_proxy cho {serial}: {e}")
    finally:
        conn.close()
        
    return assigned_proxy

def release_proxy(serial: str):
    """Giải phóng proxy đang được gán cho thiết bị serial này."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Proxy_Pool SET assigned_phone_id = NULL WHERE assigned_phone_id = ?", (serial,))
    conn.commit()
    conn.close()

def get_assigned_proxy(serial: str) -> Optional[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Proxy_Pool WHERE assigned_phone_id = ?", (serial,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

# ==========================================
# PHẦN ĐO LƯỜNG & HẠN MỨC DUNG LƯỢNG (Data_Usage)
# ==========================================

def update_data_usage(serial: str, current_raw_bytes: int) -> Tuple[int, bool]:
    """
    Cập nhật dung lượng mạng cộng dồn từ adb bytes.
    Sử dụng thuật toán sai lệch differential đối phó với reset điện thoại / cắm lại.
    Trả về Tuple (tổng dung lượng đã dùng bytes, cờ is_blocked).
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Đọc quota limit cấu hình toàn cục (đổi từ MB sang Bytes)
    cursor.execute("SELECT config_value FROM Proxy_Config WHERE config_key = 'quota_limit_mb'")
    quota_mb = int(cursor.fetchone()["config_value"])
    quota_bytes = quota_mb * 1024 * 1024
    
    cursor.execute("SELECT * FROM Data_Usage WHERE phone_id = ?", (serial,))
    row = cursor.fetchone()
    
    if not row:
        # Lần đầu tiên đọc dữ liệu thiết bị này
        cursor.execute(
            "INSERT INTO Data_Usage (phone_id, total_bytes_used, last_read_raw_bytes, quota_limit_bytes, is_blocked) VALUES (?, 0, ?, ?, 0)",
            (serial, current_raw_bytes, quota_bytes)
        )
        total_used = 0
        is_blocked = False
    else:
        total_used = row["total_bytes_used"]
        last_raw = row["last_read_raw_bytes"]
        
        # Tính sai lệch delta
        delta = current_raw_bytes - last_raw
        if delta < 0:
            # Máy đã reboot hoặc reset counters, tính delta bằng đúng raw hiện tại
            delta = current_raw_bytes
            
        total_used += delta
        is_blocked = total_used >= quota_bytes
        
        cursor.execute(
            "UPDATE Data_Usage SET total_bytes_used = ?, last_read_raw_bytes = ?, quota_limit_bytes = ?, is_blocked = ? WHERE phone_id = ?",
            (total_used, current_raw_bytes, quota_bytes, 1 if is_blocked else 0, serial)
        )
        
    conn.commit()
    conn.close()
    return total_used, is_blocked

def get_all_data_usages() -> List[Dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Data_Usage")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def reset_data_usage():
    conn = get_connection()
    cursor = conn.cursor()
    # Reset toàn bộ bytes về 0
    cursor.execute("UPDATE Data_Usage SET total_bytes_used = 0, last_read_raw_bytes = 0, is_blocked = 0")
    conn.commit()
    conn.close()
