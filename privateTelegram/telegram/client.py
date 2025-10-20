from telethon import TelegramClient

def _ensure_private_package() -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1].parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


try:
    from privateTelegram.config.settings import settings
except ModuleNotFoundError:
    _ensure_private_package()
    from privateTelegram.config.settings import settings

# ایجاد کلاینت تلگرام
client = TelegramClient(
    "session",
    settings["api_id"],
    settings["api_hash"]
)

# آیدی گروه‌ها
MAIN_GROUP_ID = settings["main_group_id"]
NEW_GROUP_ID = settings["new_group_id"]
ADMIN_GROUP_IDS = settings["admin_group_ids"]
