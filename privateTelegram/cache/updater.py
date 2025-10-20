import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from privateTelegram.config.settings import settings
import utils.state as state
from processor.transformer import process_data

# SQL Server connector
from db.sql_server import get_sql_data
# Excel connector
from db.excel_connector import get_excel_data

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
