import json
import pyodbc
from typing import Optional, List, Tuple, Any
from config import BOT_DB_CONFIG

# def get_connection():
#     conn_str = (
#         f"DRIVER={BOT_DB_CONFIG['driver']};"
#         f"SERVER={BOT_DB_CONFIG['server']};"
#         f"DATABASE={BOT_DB_CONFIG['database']};"
#         f"Trusted_Connection={BOT_DB_CONFIG.get('trusted_connection','no')};"
#     )
#     return pyodbc.connect(conn_str, timeout=30)
_TABLES_ENSURED = False


def get_connection():
    conn_str = (
        f"DRIVER={BOT_DB_CONFIG['driver']};"
        f"SERVER={BOT_DB_CONFIG['server']};"
        f"DATABASE={BOT_DB_CONFIG['database']};"
        f"UID={BOT_DB_CONFIG['user']};"
        f"PWD={BOT_DB_CONFIG['password']};"
    )
    return pyodbc.connect(conn_str, timeout=30)


def _ensure_tables(cur) -> None:
    cur.execute(
        """
        IF OBJECT_ID('control_panel_audit_log', 'U') IS NULL
        BEGIN
            CREATE TABLE control_panel_audit_log (
                id INT IDENTITY(1,1) PRIMARY KEY,
                [timestamp] DATETIME NOT NULL DEFAULT (GETDATE()),
                actor NVARCHAR(100) NULL,
                message NVARCHAR(500) NOT NULL,
                details NVARCHAR(MAX) NULL
            );
            CREATE INDEX IX_control_panel_audit_log_timestamp
                ON control_panel_audit_log([timestamp]);
        END;
        IF OBJECT_ID('whatsapp_message_log', 'U') IS NULL
        BEGIN
            CREATE TABLE whatsapp_message_log (
                id INT IDENTITY(1,1) PRIMARY KEY,
                chat_identifier NVARCHAR(255) NULL,
                direction NVARCHAR(20) NOT NULL,
                [text] NVARCHAR(MAX) NULL,
                [timestamp] DATETIME NOT NULL DEFAULT (GETDATE())
            );
            CREATE INDEX IX_whatsapp_message_log_timestamp
                ON whatsapp_message_log([timestamp]);
        END;
        """
    )


def ensure_control_panel_tables() -> bool:
    """Create audit/log tables when missing. Returns True on success."""

    global _TABLES_ENSURED
    if _TABLES_ENSURED:
        return True
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            _ensure_tables(cur)
            conn.commit()
        _TABLES_ENSURED = True
        return True
    except Exception as e:
        print("❌ خطا در ensure_control_panel_tables:", e)
        _TABLES_ENSURED = False
        return False
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


def log_whatsapp_message(chat_identifier: Optional[str], direction: str, text: str) -> None:
    direction = str(direction or "out")
    chat_value = None if chat_identifier is None else str(chat_identifier)[:255]
    payload = str(text or "")
    if not ensure_control_panel_tables():
        return
    query = """
        INSERT INTO whatsapp_message_log (chat_identifier, direction, [text], [timestamp])
        VALUES (?, ?, ?, GETDATE())
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, chat_value, direction, payload)
            conn.commit()
    except Exception as e:
        print("❌ خطا در log_whatsapp_message:", e)


def _serialize_details(details: Any) -> Optional[str]:
    if details is None:
        return None
    if isinstance(details, str):
        return details
    try:
        return json.dumps(details, ensure_ascii=False)
    except Exception:
        return str(details)


def record_audit_event(message: str, *, actor: str = "کنترل‌پنل", details: Any = None) -> None:
    if not ensure_control_panel_tables():
        raise RuntimeError("control panel tables are unavailable")
    msg = str(message or "").strip()
    if not msg:
        raise ValueError("message is required")
    actor_value = str(actor or "کنترل‌پنل")[:100]
    details_value = _serialize_details(details)
    query = """
        INSERT INTO control_panel_audit_log ([timestamp], actor, message, details)
        VALUES (GETDATE(), ?, ?, ?)
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, actor_value, msg[:500], details_value)
        conn.commit()


def fetch_audit_log_entries(limit: int = 200) -> Tuple[List[dict], int]:
    if not ensure_control_panel_tables():
        raise RuntimeError("control panel tables are unavailable")
    limit = max(1, min(limit, 500))
    query = f"""
        SELECT TOP {limit}
            id,
            [timestamp],
            actor,
            message,
            details
        FROM control_panel_audit_log
        ORDER BY [timestamp] DESC, id DESC
    """
    count_query = "SELECT COUNT(*) FROM control_panel_audit_log"
    entries: List[dict] = []
    with get_connection() as conn:
        cur = conn.cursor()
        rows = cur.execute(query).fetchall()
        total_row = cur.execute(count_query).fetchone()
    total = int(total_row[0]) if total_row else 0
    for row in rows:
        ts = row[1]
        if hasattr(ts, "isoformat"):
            ts_iso = ts.isoformat()
        else:
            ts_iso = str(ts)
        details_raw = row[4]
        parsed_details: Any = None
        if details_raw not in (None, ""):
            try:
                parsed_details = json.loads(details_raw)
            except Exception:
                parsed_details = details_raw
        entry = {
            "id": f"log-{row[0]}",
            "timestamp": ts_iso,
            "message": row[3],
        }
        if row[2]:
            entry["actor"] = row[2]
        if parsed_details not in (None, ""):
            entry["details"] = parsed_details
        entries.append(entry)
    return entries, total

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
