import asyncio

from telethon import TelegramClient

def _ensure_private_package() -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1].parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


try:
    from privateTelegram.config.settings import APP_DIR, settings
except ModuleNotFoundError:
    _ensure_private_package()
    from privateTelegram.config.settings import APP_DIR, settings


def _ensure_event_loop() -> asyncio.AbstractEventLoop:
    """Return an event loop for the current thread, creating one if needed."""
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        # No running loop; attempt to fetch the policy loop or create a new one.
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        else:
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        return loop


SESSION_BASENAME = APP_DIR / "session"
EVENT_LOOP = _ensure_event_loop()

# ایجاد کلاینت تلگرام
client = TelegramClient(
    str(SESSION_BASENAME),
    settings["api_id"],
    settings["api_hash"],
    loop=EVENT_LOOP,
)

# آیدی گروه‌ها
MAIN_GROUP_ID = settings["main_group_id"]
NEW_GROUP_ID = settings["new_group_id"]
ADMIN_GROUP_IDS = settings["admin_group_ids"]
