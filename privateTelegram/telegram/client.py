from __future__ import annotations

from typing import Iterable, List

from telethon import TelegramClient

from privateTelegram.config.settings import settings

# ایجاد کلاینت تلگرام
client = TelegramClient(
    "session",
    settings["api_id"],
    settings["api_hash"],
)


def get_main_group_id() -> int:
    return int(settings.get("main_group_id", 0) or 0)


def get_new_group_id() -> int:
    return int(settings.get("new_group_id", 0) or 0)


def get_admin_group_ids() -> List[int]:
    values: Iterable[int] = settings.get("admin_group_ids", []) or []
    return [int(value) for value in values]


def get_secondary_group_ids() -> List[int]:
    values: Iterable[int] = settings.get("secondary_group_ids", []) or []
    return [int(value) for value in values]
