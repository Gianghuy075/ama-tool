import sqlite3
import os
import logging
from datetime import datetime
import pandas as pd

log = logging.getLogger(__name__)

DB_PATH = "data/registered_accounts.db"

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        with get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS registered_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_name TEXT,
                    name TEXT,
                    email TEXT UNIQUE,
                    password TEXT,
                    proxy TEXT,
                    status TEXT,
                    note TEXT,
                    timestamp TEXT
                )
            """)
            conn.commit()
        log.info("SQLite database initialized successfully.")
    except Exception as e:
        log.error(f"Error initializing SQLite: {e}", exc_info=True)

def save_registered_accounts(new_records: list[dict], group_name: str = ""):
    """Saves new registration records to SQLite. De-duplicates by email, updating existing values."""
    if not new_records:
        return
    
    init_db()
    
    # Use current datetime if group_name is empty
    if not group_name or not group_name.strip():
        group_name = "Nhóm " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    else:
        group_name = group_name.strip()
        
    try:
        with get_db_connection() as conn:
            for r in new_records:
                email = r.get("email", "").strip()
                if not email:
                    continue
                
                name = r.get("name", "").strip()
                password = r.get("password", "").strip()
                proxy = r.get("proxy", "").strip()
                status = r.get("status", "").strip()
                note = r.get("note", "").strip()
                timestamp = r.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Check if email exists
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM registered_accounts WHERE email = ?", (email,))
                row = cursor.fetchone()
                
                if row:
                    # Update (keep the new information and new group name)
                    conn.execute("""
                        UPDATE registered_accounts
                        SET group_name = ?, name = ?, password = ?, proxy = ?, status = ?, note = ?, timestamp = ?
                        WHERE email = ?
                    """, (group_name, name, password, proxy, status, note, timestamp, email))
                else:
                    # Insert
                    conn.execute("""
                        INSERT INTO registered_accounts (group_name, name, email, password, proxy, status, note, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (group_name, name, email, password, proxy, status, note, timestamp))
            conn.commit()
        log.info(f"Successfully saved/updated {len(new_records)} accounts in SQLite with group name: {group_name}")
    except Exception as e:
        log.error(f"Error saving accounts to SQLite: {e}", exc_info=True)

def get_registered_accounts() -> list[dict]:
    init_db()
    try:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT group_name, name, email, password, proxy, status, note, timestamp FROM registered_accounts ORDER BY id DESC")
            rows = cursor.fetchall()
            # Convert to list of dicts with matching keys (renaming group_name to group for API symmetry)
            result = []
            for r in rows:
                d = dict(r)
                d["group"] = d.pop("group_name")
                result.append(d)
            return result
    except Exception as e:
        log.error(f"Error fetching accounts from SQLite: {e}", exc_info=True)
        return []

def clear_registered_accounts():
    init_db()
    try:
        with get_db_connection() as conn:
            conn.execute("DELETE FROM registered_accounts")
            conn.commit()
        log.info("Cleared all accounts from SQLite database.")
        return True
    except Exception as e:
        log.error(f"Error clearing accounts from SQLite: {e}", exc_info=True)
        return False

def export_registered_accounts_to_excel(excel_path: str):
    """Exports SQLite registered accounts to a styled Excel file."""
    accounts = get_registered_accounts()
    
    # We will reuse ExcelHandler style formatting or write using openpyxl/pandas
    df = pd.DataFrame(accounts)
    
    # Reorder columns
    cols = ["group", "name", "email", "password", "proxy", "status", "note", "timestamp"]
    for col in cols:
        if col not in df.columns:
            df[col] = ""
    df = df[cols]
    
    os.makedirs(os.path.dirname(excel_path), exist_ok=True)
    df.to_excel(excel_path, index=False)
    log.info(f"Exported SQLite registered accounts database to: {excel_path}")

def get_registered_groups() -> list[str]:
    init_db()
    try:
        with get_db_connection() as conn:
            cursor = conn.execute("SELECT DISTINCT group_name FROM registered_accounts ORDER BY group_name ASC")
            rows = cursor.fetchall()
            return [r["group_name"] for r in rows if r["group_name"]]
    except Exception as e:
        log.error(f"Error fetching group names from SQLite: {e}", exc_info=True)
        return []
