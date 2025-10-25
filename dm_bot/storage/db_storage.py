"""Database-backed storage implementation for the DM bot."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

import pyodbc

from database.connector_bot import get_connection
from ..models import ensure_schema
from .base import Storage

LOGGER = logging.getLogger(__name__)


@contextmanager
def _cursor() -> Iterable[pyodbc.Cursor]:
    conn = get_connection()
    cursor = None
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        conn.close()


def _json_dumps(value: Dict[str, Any]) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _json_loads(payload: Optional[str]) -> Dict[str, Any]:
    if not payload:
        return {}
    try:
        data = json.loads(payload)
        if isinstance(data, dict):
            return data
    except Exception:
        LOGGER.warning("Invalid JSON conversation payload detected.")
    return {}


class DBStorage(Storage):
    """SQL Server implementation using the primary MVCO connection."""

    def __init__(self) -> None:
        ensure_schema(get_connection)

    # region settings
    def get_setting(self, key: str) -> Optional[str]:
        with _cursor() as cursor:
            row = cursor.execute(
                "SELECT [value] FROM bot_settings WHERE [key] = ?", key
            ).fetchone()
            return None if row is None else row[0]

    def set_setting(self, key: str, value: str) -> None:
        with _cursor() as cursor:
            cursor.execute(
                """
                MERGE bot_settings AS target
                USING (SELECT ? AS [key]) AS src
                    ON target.[key] = src.[key]
                WHEN MATCHED THEN
                    UPDATE SET [value] = ?, updated_at = SYSUTCDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT ([key], [value], updated_at)
                    VALUES (?, ?, SYSUTCDATETIME());
                """,
                key,
                value,
                key,
                value,
            )

    def get_settings(self, keys: List[str]) -> Dict[str, Optional[str]]:
        if not keys:
            return {}
        placeholders = ",".join("?" for _ in keys)
        with _cursor() as cursor:
            rows = cursor.execute(
                f"SELECT [key], [value] FROM bot_settings WHERE [key] IN ({placeholders})",
                *keys,
            ).fetchall()
        result = {key: None for key in keys}
        for row in rows:
            result[str(row[0])] = row[1]
        return result

    # endregion

    # region users/messages
    def upsert_user(self, user_id: int, **attrs: Any) -> None:
        meta_payload = _json_dumps(attrs)
        with _cursor() as cursor:
            cursor.execute(
                """
                MERGE dm_users AS target
                USING (SELECT ? AS user_id) AS src
                    ON target.user_id = src.user_id
                WHEN MATCHED THEN
                    UPDATE SET last_seen = SYSUTCDATETIME(), meta = ?
                WHEN NOT MATCHED THEN
                    INSERT (user_id, meta)
                    VALUES (?, ?);
                """,
                user_id,
                meta_payload,
                user_id,
                meta_payload,
            )

    def log_message(self, user_id: int, text: str, outgoing: bool) -> None:
        with _cursor() as cursor:
            cursor.execute(
                "INSERT INTO dm_messages (user_id, [text], outgoing) VALUES (?, ?, ?)",
                user_id,
                text,
                1 if outgoing else 0,
            )

    # endregion

    # region conversation
    def get_conversation(self, user_id: int) -> Dict[str, Any]:
        with _cursor() as cursor:
            row = cursor.execute(
                "SELECT state FROM dm_state WHERE user_id = ?", user_id
            ).fetchone()
        return _json_loads(None if row is None else row[0])

    def set_conversation(self, user_id: int, state: Dict[str, Any]) -> None:
        payload = _json_dumps(state)
        with _cursor() as cursor:
            cursor.execute(
                """
                MERGE dm_state AS target
                USING (SELECT ? AS user_id) AS src
                    ON target.user_id = src.user_id
                WHEN MATCHED THEN
                    UPDATE SET state = ?, updated_at = SYSUTCDATETIME()
                WHEN NOT MATCHED THEN
                    INSERT (user_id, state)
                    VALUES (?, ?);
                """,
                user_id,
                payload,
                user_id,
                payload,
            )

    # endregion


__all__ = ["DBStorage"]
