"""Database helpers for the DM bot schema."""

from __future__ import annotations

import logging
from typing import Callable

import pyodbc

LOGGER = logging.getLogger(__name__)


DEFAULT_DM_SETTINGS = {
    "DM_ENABLED": "false",
    "DM_BOT_TOKEN": "",
    "DM_CHANNEL_ID": "",
    "WORK_HOURS_START": "09:00",
    "WORK_HOURS_END": "17:00",
    "DM_RATE_LIMIT": "20/min",
    "DM_WHITELIST": "",
    "DM_REPLY_START": "سلام! پیام شما دریافت شد و به زودی پاسخ داده می‌شود.",
    "DM_REPLY_OFF_HOURS": "⏰ خارج از ساعات کاری هستیم؛ به محض حضور همکاران پاسخ خواهیم داد.",
    "DM_REPLY_GENERIC": "پیام شما ثبت شد.",
}


SCHEMA_SQL = """
IF OBJECT_ID('bot_settings', 'U') IS NULL
BEGIN
    CREATE TABLE bot_settings (
        [key]        NVARCHAR(100) NOT NULL PRIMARY KEY,
        [value]      NVARCHAR(MAX) NOT NULL,
        updated_at   DATETIME2      NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;

IF OBJECT_ID('dm_users', 'U') IS NULL
BEGIN
    CREATE TABLE dm_users (
        user_id     BIGINT        NOT NULL PRIMARY KEY,
        first_seen  DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        last_seen   DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
        meta        NVARCHAR(MAX) NULL
    );
END;

IF OBJECT_ID('dm_messages', 'U') IS NULL
BEGIN
    CREATE TABLE dm_messages (
        id         BIGINT IDENTITY(1,1) PRIMARY KEY,
        user_id    BIGINT        NOT NULL,
        [text]     NVARCHAR(MAX) NOT NULL,
        outgoing   BIT           NOT NULL,
        created_at DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
    );
    CREATE INDEX IX_dm_messages_user_id_created_at
        ON dm_messages(user_id, created_at DESC);
END;

IF OBJECT_ID('dm_state', 'U') IS NULL
BEGIN
    CREATE TABLE dm_state (
        user_id BIGINT        NOT NULL PRIMARY KEY,
        state   NVARCHAR(MAX) NOT NULL,
        updated_at DATETIME2  NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
"""


SEED_SQL = """
MERGE bot_settings AS t
USING (VALUES
    ('DM_ENABLED',       'false'),
    ('DM_BOT_TOKEN',     ''),
    ('DM_CHANNEL_ID',    ''),
    ('WORK_HOURS_START', '09:00'),
    ('WORK_HOURS_END',   '17:00'),
    ('DM_RATE_LIMIT',    '20/min'),
    ('DM_WHITELIST',     ''),
    ('DM_REPLY_START',   'سلام! پیام شما دریافت شد و به زودی پاسخ داده می‌شود.'),
    ('DM_REPLY_OFF_HOURS', '⏰ خارج از ساعات کاری هستیم؛ به محض حضور همکاران پاسخ خواهیم داد.'),
    ('DM_REPLY_GENERIC', 'پیام شما ثبت شد.')
) AS s([key],[value])
ON t.[key] = s.[key]
WHEN NOT MATCHED THEN
    INSERT([key],[value]) VALUES(s.[key], s.[value]);
"""


def ensure_schema(get_connection: Callable[[], pyodbc.Connection]) -> None:
    """Ensure DM related tables exist along with default seed data."""

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(SCHEMA_SQL)
            cursor.execute(SEED_SQL)
            conn.commit()
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.exception("Failed to ensure DM schema: %s", exc)
        raise
