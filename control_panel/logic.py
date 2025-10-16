from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from database.connector_bot import (
    add_to_blacklist,
    get_blacklist,
    get_connection,
    get_setting,
    remove_from_blacklist,
    set_setting,
)
from handlers.inventory import refresh_inventory_cache_once

LOGGER = logging.getLogger(__name__)

UTC = timezone.utc

PERSIAN_MONTHS = [
    "ژانویه",
    "فوریه",
    "مارس",
    "آوریل",
    "مه",
    "ژوئن",
    "ژوئیه",
    "اوت",
    "سپتامبر",
    "اکتبر",
    "نوامبر",
    "دسامبر",
]

DEFAULT_COMMANDS = [
    {
        "id": "cmd-start",
        "command": "/start",
        "description": "آغاز مکالمه با کاربر و نمایش منو.",
        "enabled": True,
        "lastUsedISO": None,
    },
    {
        "id": "cmd-help",
        "command": "/help",
        "description": "نمایش راهنمای استفاده از ربات.",
        "enabled": True,
        "lastUsedISO": None,
    },
]

COMMANDS_KEY = "panel_commands_v1"
PLATFORMS_KEY = "panel_platforms_v1"
CACHE_KEY = "inventory_cache_last_refresh"
TIMEZONE_KEY = "working_timezone"
LUNCH_START_KEY = "lunch_start"
LUNCH_END_KEY = "lunch_end"
QUERY_LIMIT_KEY = "query_limit"
DELIVERY_BEFORE_KEY = "delivery_before"
DELIVERY_AFTER_KEY = "delivery_after"
CHANGEOVER_KEY = "changeover_hour"


class ControlPanelError(Exception):
    """Raised for validation or domain errors that should be surfaced to the API."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class Metrics:
    totals: Dict[str, int]
    monthly: List[Dict[str, Any]]
    cache: Dict[str, Optional[str]]
    status: Dict[str, Any]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_time(value: Optional[str], field_name: str) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    try:
        datetime.strptime(text, "%H:%M")
    except Exception:
        raise ControlPanelError(f"زمان {field_name} باید در قالب HH:MM باشد.")
    return text


def _safe_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _load_json_setting(key: str, default: Any) -> Any:
    raw = get_setting(key)
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        LOGGER.warning("Failed to decode JSON setting %s", key)
        return default


def _save_json_setting(key: str, value: Any) -> None:
    try:
        set_setting(key, json.dumps(value, ensure_ascii=False))
    except Exception:
        LOGGER.exception("Failed to persist JSON setting %s", key)
        raise ControlPanelError("ذخیره‌سازی تنظیمات امکان‌پذیر نبود. دوباره تلاش کنید.", status=500)


def _format_month_label(year: int, month: int) -> str:
    index = max(1, min(month, 12)) - 1
    month_name = PERSIAN_MONTHS[index]
    return f"{month_name} {year}"


def _aggregate_metrics_from_db() -> Metrics:
    totals = {"telegram": 0, "whatsapp": 0, "all": 0}
    monthly: List[Dict[str, Any]] = []
    status = _build_status_snapshot()

    fallback = False
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            rows = cur.execute(
                """
                SELECT
                    YEAR(timestamp) AS y,
                    MONTH(timestamp) AS m,
                    COUNT(*) AS cnt
                FROM message_log
                WHERE timestamp >= DATEADD(MONTH, -11, GETDATE())
                GROUP BY YEAR(timestamp), MONTH(timestamp)
                ORDER BY y, m
                """
            ).fetchall()

            total_count = 0
            for row in rows:
                year, month, count = int(row[0]), int(row[1]), int(row[2])
                total_count += count
                monthly.append(
                    {
                        "month": _format_month_label(year, month),
                        "telegram": count,
                        "whatsapp": 0,
                        "all": count,
                    }
                )

            totals["telegram"] = total_count
            totals["all"] = total_count
    except Exception as exc:
        fallback = True
        LOGGER.warning("Failed to aggregate metrics from database: %s", exc)
        monthly = _build_mock_monthly()
        totals = _build_mock_totals()

    cache_info = {
        "lastUpdatedISO": get_setting(CACHE_KEY) or _now_iso(),
        "usingFallback": fallback,
    }
    status["dataSource"] = "fallback" if fallback else "live"
    status["usingFallback"] = fallback
    return Metrics(totals=totals, monthly=monthly, cache=cache_info, status=status)


def _build_mock_totals() -> Dict[str, int]:
    telegram = 320
    whatsapp = 0
    return {"telegram": telegram, "whatsapp": whatsapp, "all": telegram + whatsapp}


def _build_mock_monthly() -> List[Dict[str, Any]]:
    today = datetime.now()
    results: List[Dict[str, Any]] = []
    for offset in range(11, -1, -1):
        current = today - timedelta(days=30 * offset)
        year = current.year
        month = current.month
        label = _format_month_label(year, month)
        telegram = 50 + (offset * 3)
        results.append(
            {
                "month": label,
                "telegram": telegram,
                "whatsapp": 0,
                "all": telegram,
            }
        )
    return results


def _build_status_snapshot() -> Dict[str, Any]:
    enabled = (get_setting("enabled") or "true").lower() == "true"
    weekly = _build_weekly_schedule()
    platforms = _load_json_setting(PLATFORMS_KEY, {"telegram": enabled, "whatsapp": True})
    message = "ربات فعال و آماده پاسخ‌گویی است." if enabled else "ربات غیرفعال است."

    timezone_value = get_setting(TIMEZONE_KEY) or "Asia/Tehran"

    lunch_start = get_setting(LUNCH_START_KEY) or ""
    lunch_end = get_setting(LUNCH_END_KEY) or ""
    query_limit = _safe_int(get_setting(QUERY_LIMIT_KEY))
    delivery_before = get_setting(DELIVERY_BEFORE_KEY) or ""
    delivery_after = get_setting(DELIVERY_AFTER_KEY) or ""
    changeover_hour = get_setting(CHANGEOVER_KEY) or ""

    operations = {
        "lunchBreak": {
            "start": lunch_start or None,
            "end": lunch_end or None,
        },
        "queryLimit": query_limit,
        "delivery": {
            "before": delivery_before,
            "after": delivery_after,
            "changeover": changeover_hour or None,
        },
    }

    return {
        "active": enabled,
        "message": message,
        "workingHours": {
            "timezone": timezone_value,
            "weekly": weekly,
        },
        "platforms": platforms,
        "operations": operations,
        "dataSource": "live",
    }


def _build_weekly_schedule() -> List[Dict[str, Any]]:
    weekly: List[Dict[str, Any]] = []
    general_open = get_setting("working_start") or "08:00"
    general_close = get_setting("working_end") or "18:00"
    th_open = get_setting("thursday_start") or general_open
    th_close = get_setting("thursday_end") or general_close
    friday_disabled = (get_setting("disable_friday") or "true").lower() == "true"

    for day in range(7):
        if day == 4:  # پنج‌شنبه
            open_time = th_open if th_open.strip() else None
            close_time = th_close if th_close.strip() else None
        elif day == 5:  # جمعه
            open_time = None if friday_disabled else general_open
            close_time = None if friday_disabled else general_close
        else:
            open_time = general_open if general_open.strip() else None
            close_time = general_close if general_close.strip() else None

        weekly.append({"day": day, "open": open_time, "close": close_time})
    return weekly


def get_metrics() -> Dict[str, Any]:
    metrics = _aggregate_metrics_from_db()
    return {
        "totals": metrics.totals,
        "monthly": metrics.monthly,
        "cache": metrics.cache,
        "status": metrics.status,
    }


def get_commands() -> List[Dict[str, Any]]:
    commands = _load_json_setting(COMMANDS_KEY, DEFAULT_COMMANDS)
    if not isinstance(commands, list):
        commands = DEFAULT_COMMANDS
    return commands


def create_command(payload: Dict[str, Any]) -> Dict[str, Any]:
    command = (payload.get("command") or "").strip()
    if not command:
        raise ControlPanelError("دستور نمی‌تواند خالی باشد.")
    if not command.startswith("/"):
        raise ControlPanelError("دستور باید با / آغاز شود.")

    description = (payload.get("description") or "").strip()
    enabled = bool(payload.get("enabled", True))

    commands = get_commands()
    if any(item.get("command") == command for item in commands):
        raise ControlPanelError("این دستور قبلاً ثبت شده است.")

    new_item = {
        "id": f"cmd-{int(datetime.now().timestamp() * 1000)}",
        "command": command,
        "description": description,
        "enabled": enabled,
        "lastUsedISO": None,
    }
    commands.insert(0, new_item)
    _save_json_setting(COMMANDS_KEY, commands)
    return new_item


def update_command(command_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    commands = get_commands()
    for idx, item in enumerate(commands):
        if item.get("id") == command_id:
            updated = {**item}
            if "command" in payload:
                value = (payload.get("command") or "").strip()
                if not value:
                    raise ControlPanelError("دستور نمی‌تواند خالی باشد.")
                if not value.startswith("/"):
                    raise ControlPanelError("دستور باید با / آغاز شود.")
                updated["command"] = value
            if "description" in payload:
                updated["description"] = (payload.get("description") or "").strip()
            if "enabled" in payload:
                updated["enabled"] = bool(payload.get("enabled"))
            commands[idx] = updated
            _save_json_setting(COMMANDS_KEY, commands)
            return updated
    raise ControlPanelError("دستور مورد نظر یافت نشد.", status=404)


def delete_command(command_id: str) -> Dict[str, Any]:
    commands = get_commands()
    new_commands = [item for item in commands if item.get("id") != command_id]
    if len(new_commands) == len(commands):
        raise ControlPanelError("دستور مورد نظر یافت نشد.", status=404)
    _save_json_setting(COMMANDS_KEY, new_commands)
    return {"success": True}


def get_blocklist() -> List[Dict[str, Any]]:
    entries = []
    try:
        for user_id in get_blacklist():
            entries.append(
                {
                    "id": str(user_id),
                    "userId": int(user_id),
                    "platform": "telegram",
                    "phoneOrUser": str(user_id),
                    "reason": None,
                    "createdAtISO": None,
                }
            )
    except Exception as exc:
        LOGGER.warning("Failed to fetch blocklist: %s", exc)
        raise ControlPanelError("دریافت لیست مسدود امکان‌پذیر نبود.", status=500)
    return entries


def add_block_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_user_id = payload.get("userId") or payload.get("phoneOrUser")
    if raw_user_id is None:
        raise ControlPanelError("شناسه کاربر ضروری است.")
    try:
        user_id = int(str(raw_user_id).strip())
    except Exception:
        raise ControlPanelError("شناسه کاربر باید عددی باشد.")
    try:
        add_to_blacklist(user_id)
    except Exception as exc:
        LOGGER.warning("Failed to add user %s to blacklist: %s", user_id, exc)
        raise ControlPanelError("افزودن به لیست مسدود با خطا مواجه شد.", status=500)

    return {
        "id": str(user_id),
        "userId": user_id,
        "platform": "telegram",
        "phoneOrUser": str(user_id),
        "reason": None,
        "createdAtISO": _now_iso(),
    }


def remove_block_item(item_id: str) -> Dict[str, Any]:
    try:
        user_id = int(str(item_id).strip())
    except Exception:
        raise ControlPanelError("شناسه نامعتبر است.")
    try:
        remove_from_blacklist(user_id)
    except Exception as exc:
        LOGGER.warning("Failed to remove user %s from blacklist: %s", user_id, exc)
        raise ControlPanelError("حذف از لیست مسدود امکان‌پذیر نبود.", status=500)
    return {"success": True}


def get_settings() -> Dict[str, Any]:
    status = _build_status_snapshot()
    operations = status.get("operations", {})
    return {
        "timezone": status["workingHours"]["timezone"],
        "weekly": status["workingHours"]["weekly"],
        "platforms": status["platforms"],
        "lunchBreak": operations.get("lunchBreak", {"start": None, "end": None}),
        "queryLimit": operations.get("queryLimit"),
        "deliveryInfo": operations.get(
            "delivery",
            {"before": "", "after": "", "changeover": None},
        ),
        "dataSource": status.get("dataSource", "live"),
    }


def update_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    timezone_value = payload.get("timezone")
    if timezone_value is not None:
        timezone_clean = timezone_value.strip() or "Asia/Tehran"
        set_setting(TIMEZONE_KEY, timezone_clean)

    weekly = payload.get("weekly")
    if weekly is not None:
        if not isinstance(weekly, list):
            raise ControlPanelError("ساختار ساعات کاری نامعتبر است.")

        weekly_by_day = {item.get("day"): item for item in weekly if isinstance(item, dict)}

        reference_days = [6, 0, 1, 2, 3]  # روزهای کاری معمول
        general = next((weekly_by_day.get(day) for day in reference_days if weekly_by_day.get(day)), None)
        thursday = weekly_by_day.get(4)
        friday = weekly_by_day.get(5)

        if general:
            open_time = (general.get("open") or "08:00").strip()
            close_time = (general.get("close") or "18:00").strip()
            set_setting("working_start", open_time or "08:00")
            set_setting("working_end", close_time or "18:00")

        if thursday:
            set_setting("thursday_start", (thursday.get("open") or "").strip())
            set_setting("thursday_end", (thursday.get("close") or "").strip())

        if friday:
            is_closed = not (friday.get("open") and friday.get("close"))
            set_setting("disable_friday", "true" if is_closed else "false")

    platforms = payload.get("platforms")
    if isinstance(platforms, dict):
        _save_json_setting(PLATFORMS_KEY, platforms)

    if "lunchBreak" in payload:
        lunch_break = payload.get("lunchBreak") or {}
        if not isinstance(lunch_break, dict):
            raise ControlPanelError("ساختار بازه ناهار نامعتبر است.")
        start = _normalize_time(lunch_break.get("start"), "شروع ناهار")
        end = _normalize_time(lunch_break.get("end"), "پایان ناهار")
        set_setting(LUNCH_START_KEY, start)
        set_setting(LUNCH_END_KEY, end)

    if "queryLimit" in payload:
        limit_value = payload.get("queryLimit")
        if limit_value in (None, ""):
            set_setting(QUERY_LIMIT_KEY, "")
        else:
            try:
                limit_int = int(str(limit_value).strip())
            except Exception:
                raise ControlPanelError("محدودیت استعلام باید عددی باشد.")
            if limit_int < 0:
                raise ControlPanelError("محدودیت استعلام نمی‌تواند منفی باشد.")
            set_setting(QUERY_LIMIT_KEY, str(limit_int))

    if "deliveryInfo" in payload:
        delivery_info = payload.get("deliveryInfo") or {}
        if not isinstance(delivery_info, dict):
            raise ControlPanelError("ساختار تنظیمات تحویل نامعتبر است.")
        before_text = str(delivery_info.get("before") or "").strip()
        after_text = str(delivery_info.get("after") or "").strip()
        changeover_value = _normalize_time(
            delivery_info.get("changeover"), "ساعت تغییر متن"
        )
        set_setting(DELIVERY_BEFORE_KEY, before_text)
        set_setting(DELIVERY_AFTER_KEY, after_text)
        set_setting(CHANGEOVER_KEY, changeover_value)

    return get_settings()


def toggle_bot(active: bool) -> Dict[str, Any]:
    set_setting("enabled", "true" if active else "false")
    status = _build_status_snapshot()
    return status


def invalidate_cache() -> Dict[str, Any]:
    try:
        # refresh_inventory_cache_once is async
        import asyncio

        asyncio.run(refresh_inventory_cache_once())
    except Exception as exc:
        LOGGER.warning("Failed to refresh inventory cache: %s", exc)
        raise ControlPanelError("به‌روزرسانی کش با خطا مواجه شد.", status=500)

    timestamp = _now_iso()
    set_setting(CACHE_KEY, timestamp)
    return {"lastUpdatedISO": timestamp}


def get_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "time": _now_iso(),
    }
