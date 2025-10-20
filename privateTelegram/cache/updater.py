import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo


def _ensure_private_package() -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1].parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


try:
    from privateTelegram.config.settings import settings
    from privateTelegram.utils import state
    from privateTelegram.processor.transformer import process_data
except ModuleNotFoundError:
    _ensure_private_package()
    from privateTelegram.config.settings import settings
    from privateTelegram.utils import state
    from privateTelegram.processor.transformer import process_data

# SQL Server connector
try:
    from privateTelegram.db.sql_server import get_sql_data
    from privateTelegram.db.excel_connector import get_excel_data
except ModuleNotFoundError:
    _ensure_private_package()
    from privateTelegram.db.sql_server import get_sql_data
    from privateTelegram.db.excel_connector import get_excel_data

TZ = ZoneInfo("Asia/Tehran")

async def update_cache_periodically():
    while True:
        source = settings.get("data_source", "sql").lower()
        if source == "excel":
            raw = get_excel_data()
        else:
            raw = get_sql_data()

        if raw:
            processed = process_data(raw)
            # Update the shared state
            state.cached_simplified_data.clear()
            state.cached_simplified_data.extend(processed)
            state.last_cache_update = datetime.now(TZ)
            print(f"Cache updated from {source}: {len(processed)} records.")
        else:
            print(f"⚠️ داده‌ای از منبع «{source}» دریافت نشد.")

        await asyncio.sleep(settings.get("cache_duration_minutes", 20) * 60)

def get_cached_data():
    return state.cached_simplified_data
