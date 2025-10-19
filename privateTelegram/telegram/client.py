from telethon import TelegramClient
from config.settings import settings

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
