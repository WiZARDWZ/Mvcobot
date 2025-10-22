"""Query metrics tracker for the private Telegram bot."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo


def _ensure_private_package() -> None:
    """Ensure the project root is importable when running from a frozen build."""
    import sys

    project_root = Path(__file__).resolve().parents[1].parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


try:
    from privateTelegram.config.settings import APP_DIR
except ModuleNotFoundError:  # pragma: no cover - support standalone scripts
    _ensure_private_package()
    from privateTelegram.config.settings import APP_DIR  # type: ignore

TZ = ZoneInfo("Asia/Tehran")
METRICS_FILE = APP_DIR / "private_metrics.json"
_MAX_MONTHS = 36

_lock = threading.Lock()
_data = {"total": 0, "monthly": {}}  # type: Dict[str, int]


def _load_metrics() -> None:
    try:
        raw = json.loads(METRICS_FILE.read_text("utf-8"))
    except FileNotFoundError:
        return
    except Exception as exc:  # pragma: no cover - defensive log
        print(f"⚠️ Failed to load private metrics: {exc}")
        return

    total = raw.get("totalQueries")
    monthly = raw.get("monthly")

    if isinstance(total, int) and total >= 0:
        _data["total"] = int(total)

    if isinstance(monthly, dict):
        cleaned: Dict[str, int] = {}
        for key, value in monthly.items():
            try:
                cleaned[str(key)] = max(0, int(value))
            except Exception:
                continue
        _data["monthly"] = cleaned


def _save_metrics() -> None:
    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "totalQueries": int(_data.get("total", 0)),
        "monthly": {k: int(v) for k, v in _data.get("monthly", {}).items()},
    }
    METRICS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")


def _coerce_timestamp(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(TZ)
    if value.tzinfo is None:
        return value.replace(tzinfo=TZ)
    return value.astimezone(TZ)


def _prune_months() -> None:
    months = sorted(_data["monthly"].keys())
    if len(months) <= _MAX_MONTHS:
        return
    for key in months[:-_MAX_MONTHS]:
        _data["monthly"].pop(key, None)


def record_query(timestamp: datetime | None = None) -> None:
    """Record a processed code lookup for the given timestamp."""
    ts = _coerce_timestamp(timestamp)
    key = f"{ts.year:04d}-{ts.month:02d}"
    with _lock:
        _data["total"] = int(_data.get("total", 0)) + 1
        monthly = _data.setdefault("monthly", {})
        monthly[key] = int(monthly.get(key, 0)) + 1
        _prune_months()
        _save_metrics()


def get_snapshot(limit: int = 12) -> Tuple[int, List[Tuple[int, int, int]]]:
    """Return the total and per-month counts for the last ``limit`` months."""
    with _lock:
        total = int(_data.get("total", 0))
        items = sorted(_data.get("monthly", {}).items())

    if limit > 0:
        items = items[-limit:]

    result: List[Tuple[int, int, int]] = []
    for key, count in items:
        try:
            year_str, month_str = key.split("-", 1)
            year = int(year_str)
            month = int(month_str)
            result.append((year, month, int(count)))
        except Exception:
            continue
    return total, result


# Load persisted metrics on import.
_load_metrics()


__all__ = ["record_query", "get_snapshot"]
