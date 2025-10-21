from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def _ensure_private_package() -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1].parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


try:
    from privateTelegram.config.settings import settings
    from privateTelegram.utils.state import sent_messages
    from privateTelegram.telegram.client import NEW_GROUP_ID
except ModuleNotFoundError:
    _ensure_private_package()
    from privateTelegram.config.settings import settings
    from privateTelegram.utils.state import sent_messages
    from privateTelegram.telegram.client import NEW_GROUP_ID

TZ = ZoneInfo("Asia/Tehran")

def is_within_active_hours():
    if not settings.get("enabled", True):
        return False
    now_dt = datetime.now(TZ)
    now = now_dt.time()

    # Lunch break
    lb = settings.get("lunch_break", {"start": "12:00", "end": "13:00"})
    ls = datetime.strptime(lb["start"], "%H:%M").time()
    le = datetime.strptime(lb["end"], "%H:%M").time()
    if ls <= now < le:
        return False

    # Friday off
    if settings.get("disable_friday", True) and now_dt.weekday() == 4:
        return False

    # Thursday hours
    if now_dt.weekday() == 3:
        th = settings.get("thursday_hours", {"start": "08:00", "end": "14:00"})
        ts = datetime.strptime(th["start"], "%H:%M").time()
        te = datetime.strptime(th["end"], "%H:%M").time()
        return ts <= now < te

    # Normal days
    wh = settings.get("working_hours", {"start": "08:00", "end": "18:00"})
    ws = datetime.strptime(wh["start"], "%H:%M").time()
    we = datetime.strptime(wh["end"], "%H:%M").time()
    return ws <= now < we

def is_recently_sent(user_id, code, group_id):
    if group_id == NEW_GROUP_ID:
        return False
    key = f"{user_id}:{code}"
    last = sent_messages.get(key)
    if last and datetime.now(TZ) - last < timedelta(hours=24):
        return True
    return False

def log_sent_message(user_id, code):
    key = f"{user_id}:{code}"
    sent_messages[key] = datetime.now(TZ)
