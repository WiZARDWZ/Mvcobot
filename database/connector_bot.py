import pyodbc
from datetime import datetime
from typing import Optional
from config import BOT_DB_CONFIG

def get_connection():
    # ساخت صحیح connection string با استفاده از کلیدهای dict
    conn_str = (
        f"DRIVER={BOT_DB_CONFIG['driver']};"
        f"SERVER={BOT_DB_CONFIG['server']};"
        f"DATABASE={BOT_DB_CONFIG['database']};"
        f"Trusted_Connection={BOT_DB_CONFIG.get('trusted_connection', 'no')};"
    )
    return pyodbc.connect(conn_str, timeout=30)


def log_message(user_id: int, chat_id: int, direction: str, text: str):
    query = """
    INSERT INTO message_log (user_id, chat_id, direction, text, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, user_id, chat_id, direction, text, datetime.now())
            conn.commit()
    except Exception as e:
        print("❌ خطا در log_message:", e)


def get_setting(key: str) -> Optional[str]:
    query = "SELECT [value] FROM bot_settings WHERE [key] = ?"
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            result = cursor.execute(query, key).fetchone()
            # result یک tuple یا None هست
            return result[0] if result else None
    except Exception as e:
        print("❌ خطا در get_setting:", e)
        return None


def set_setting(key: str, value: str):
    query = """
    MERGE bot_settings AS target
    USING (SELECT ? AS [key], ? AS [value]) AS src
      ON target.[key] = src.[key]
    WHEN MATCHED THEN
      UPDATE SET [value] = src.[value]
    WHEN NOT MATCHED THEN
      INSERT ([key], [value]) VALUES (src.[key], src.[value]);
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, key, value)
            conn.commit()
    except Exception as e:
        print("❌ خطا در set_setting:", e)


def add_to_blacklist(user_id: int, reason: Optional[str] = None):
    query = """
    IF NOT EXISTS (SELECT 1 FROM blacklist WHERE user_id = ?)
    BEGIN
        INSERT INTO blacklist (user_id, reason) VALUES (?, ?)
    END
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, user_id, user_id, reason)
            conn.commit()
    except Exception as e:
        print("❌ خطا در add_to_blacklist:", e)


def remove_from_blacklist(user_id: int):
    query = "DELETE FROM blacklist WHERE user_id = ?"
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, user_id)
            conn.commit()
    except Exception as e:
        print("❌ خطا در remove_from_blacklist:", e)


def is_blacklisted(user_id: int) -> bool:
    query = "SELECT 1 FROM blacklist WHERE user_id = ?"
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            result = cursor.execute(query, user_id).fetchone()
            return result is not None
    except Exception as e:
        print("❌ خطا در is_blacklisted:", e)
        return False
def get_blacklist() -> list[int]:
    try:
        with pyodbc.connect(BOT_DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id FROM blacklist")
                rows = cursor.fetchall()
                return [row[0] for row in rows]
    except Exception as e:
        print("❌ خطا در get_blacklist:", e)
        return []

    # -------تنظیمات تحویل
def get_setting(key: str) -> str | None:
        try:
            with pyodbc.connect(BOT_DB_CONFIG) as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT [value] FROM bot_settings WHERE [key] = ?", (key,))
                    row = cursor.fetchone()
                    return row[0] if row else None
        except Exception as e:
            print("❌ خطا در get_setting:", e)
            return None

