import pyodbc
from datetime import datetime
from typing import Optional, List
from config import BOT_DB_CONFIG

# def get_connection():
#     conn_str = (
#         f"DRIVER={BOT_DB_CONFIG['driver']};"
#         f"SERVER={BOT_DB_CONFIG['server']};"
#         f"DATABASE={BOT_DB_CONFIG['database']};"
#         f"Trusted_Connection={BOT_DB_CONFIG.get('trusted_connection','no')};"
#     )
#     return pyodbc.connect(conn_str, timeout=30)
def get_connection():
    conn_str = (
        f"DRIVER={BOT_DB_CONFIG['driver']};"
        f"SERVER={BOT_DB_CONFIG['server']};"
        f"DATABASE={BOT_DB_CONFIG['database']};"
        f"UID={BOT_DB_CONFIG['user']};"
        f"PWD={BOT_DB_CONFIG['password']};"
    )
    return pyodbc.connect(conn_str, timeout=30)
def log_message(user_id, chat_id, direction, text):
    try:
        uid = int(user_id)
        cid = int(chat_id)
        d = str(direction)
        t = str(text)
    except:
        return
    query = """
        INSERT INTO message_log (user_id, chat_id, direction, text, timestamp)
        VALUES (?, ?, ?, ?, GETDATE())
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, uid, cid, d, t)
            conn.commit()
    except Exception as e:
        print("❌ خطا در log_message:", e)

def get_setting(key) -> Optional[str]:
    k = str(key)
    query = "SELECT [value] FROM bot_settings WHERE [key]=?"
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            row = cur.execute(query, k).fetchone()
            return row[0] if row else None
    except Exception as e:
        print("❌ خطا در get_setting:", e)
        return None

def set_setting(key, value):
    k, v = str(key), str(value)
    query = """
      MERGE bot_settings AS target
      USING (SELECT ? AS [key], ? AS [value]) AS src
        ON target.[key]=src.[key]
      WHEN MATCHED THEN UPDATE SET [value]=src.[value]
      WHEN NOT MATCHED THEN INSERT ([key],[value]) VALUES (src.[key],src.[value]);
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, k, v)
            conn.commit()
    except Exception as e:
        print("❌ خطا در set_setting:", e)


def add_to_blacklist(user_id):
    try:
        uid = int(user_id)
    except:
        return
    query = "IF NOT EXISTS (SELECT 1 FROM blacklist WHERE user_id=?) INSERT INTO blacklist(user_id) VALUES(?)"
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, uid, uid)
            conn.commit()
    except Exception as e:
        print("❌ خطا در add_to_blacklist:", e)

def remove_from_blacklist(user_id):
    try:
        uid = int(user_id)
    except:
        return
    query = "DELETE FROM blacklist WHERE user_id=?"
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, uid)
            conn.commit()
    except Exception as e:
        print("❌ خطا در remove_from_blacklist:", e)

def is_blacklisted(user_id) -> bool:
    try:
        uid = int(user_id)
    except:
        return False
    query = "SELECT 1 FROM blacklist WHERE user_id=?"
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            return cur.execute(query, uid).fetchone() is not None
    except Exception as e:
        print("❌ خطا در is_blacklisted:", e)
        return False

def get_blacklist() -> List[int]:
    query = "SELECT user_id FROM blacklist"
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            rows = cur.execute(query).fetchall()
            return [int(r[0]) for r in rows]
    except Exception as e:
        print("❌ خطا در get_blacklist:", e)
        return []

def fetch_logs(user_id: int) -> List[dict]:
    """
    بازگرداندن لاگ پیام‌های کاربر به صورت لیست دیکشنری.
    """
    try:
        uid = int(user_id)
    except:
        return []
    query = """
        SELECT direction, text, timestamp
        FROM message_log
        WHERE user_id = ?
        ORDER BY timestamp ASC
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            rows = cur.execute(query, uid).fetchall()
            logs = []
            for r in rows:
                logs.append({
                    "direction": r[0],
                    "text": r[1],
                    "timestamp": r[2],
                })
            return logs
    except Exception as e:
        print("❌ خطا در fetch_logs:", e)
        return []
