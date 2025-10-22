"""Cache refresh helpers for the private Telegram bot."""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List
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
except ModuleNotFoundError:
    _ensure_private_package()
    from privateTelegram.config.settings import settings  # type: ignore
    from privateTelegram.utils import state  # type: ignore

try:
    from privateTelegram.db.sql_server import get_sql_data
    from privateTelegram.db.excel_connector import get_excel_data
except ModuleNotFoundError:
    _ensure_private_package()
    from privateTelegram.db.sql_server import get_sql_data  # type: ignore
    from privateTelegram.db.excel_connector import get_excel_data  # type: ignore

_ProcessFn = Callable[[Iterable[Dict[str, Any]]], List[Dict[str, Any]]]
_process_data: _ProcessFn | None = None


def _load_process_data() -> _ProcessFn:
    """Lazy import to avoid circular package initialisation."""
    global _process_data
    if _process_data is None:
        try:
            from privateTelegram.processor.transformer import process_data
        except ModuleNotFoundError:
            _ensure_private_package()
            from privateTelegram.processor.transformer import process_data  # type: ignore
        _process_data = process_data
    return _process_data


TZ = ZoneInfo("Asia/Tehran")


def _refresh_cache_once(process_data: _ProcessFn | None = None) -> bool:
    loader = process_data or _load_process_data()
    source = settings.get("data_source", "sql").lower()
    if source == "excel":
        raw = get_excel_data()
    else:
        raw = get_sql_data()

    if not raw:
        return False

    processed = loader(raw)
    state.cached_simplified_data.clear()
    state.cached_simplified_data.extend(processed)
    state.last_cache_update = datetime.now(TZ)
    print(f"Cache updated from {source}: {len(processed)} records.")
    return True


def refresh_cache_once() -> bool:
    """Refresh the private Telegram cache immediately."""
    return _refresh_cache_once()


async def update_cache_periodically() -> None:
    process_data = _load_process_data()

    while True:
        try:
            updated = _refresh_cache_once(process_data)
            if not updated:
                source = settings.get("data_source", "sql")
                print(f"⚠️ داده‌ای از منبع «{source}» دریافت نشد.")
        except Exception as exc:
            print(f"⚠️ به‌روزرسانی کش خصوصی ناموفق بود: {exc}")

        await asyncio.sleep(settings.get("cache_duration_minutes", 20) * 60)

