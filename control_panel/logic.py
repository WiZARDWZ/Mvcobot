from __future__ import annotations

import json
import logging
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from database.connector_bot import (
    add_to_blacklist,
    fetch_audit_log_entries,
    fetch_working_hours_entries,
    get_blacklist,
    get_connection,
    get_setting,
    record_audit_event,
    remove_from_blacklist,
    save_working_hours_entries,
    set_setting,
)
from handlers.inventory import refresh_inventory_cache_once
from . import runtime

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
AUDIT_LOG_KEY = "panel_audit_log_v1"

WORKING_DAY_ORDER = [5, 6, 0, 1, 2, 3, 4]  # Saturday → Friday (Python weekday numbering)

MAX_AUDIT_LOG_ENTRIES = 200


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


def _load_audit_log_fallback() -> List[Dict[str, Any]]:
    data = _load_json_setting(AUDIT_LOG_KEY, [])
    if not isinstance(data, list):
        return []

    entries: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        message = str(item.get("message") or "").strip()
        timestamp = item.get("timestamp") or ""
        if not message or not timestamp:
            continue
        entry = {
            "id": str(item.get("id") or f"log-{len(entries) + 1}"),
            "timestamp": timestamp,
            "message": message,
        }
        if item.get("actor"):
            entry["actor"] = str(item.get("actor"))
        if item.get("details"):
            entry["details"] = item.get("details")
        entries.append(entry)
        if len(entries) >= MAX_AUDIT_LOG_ENTRIES:
            break
    return entries


def _persist_audit_log_fallback(entries: List[Dict[str, Any]]) -> None:
    try:
        _save_json_setting(AUDIT_LOG_KEY, entries[:MAX_AUDIT_LOG_ENTRIES])
    except ControlPanelError:
        # Audit log persistence failures should not block the primary action.
        LOGGER.debug("Failed to persist audit trail entry", exc_info=True)


def _append_audit_event(message: str, *, actor: str = "کنترل‌پنل", details: Optional[Any] = None) -> None:
    entry = {
        "id": f"log-{int(datetime.now().timestamp() * 1000)}",
        "timestamp": _now_iso(),
        "message": message,
        "actor": actor,
    }
    if details:
        entry["details"] = details
    try:
        record_audit_event(message, actor=actor, details=details)
        return
    except Exception:
        LOGGER.debug("Falling back to settings-based audit trail persistence", exc_info=True)

    entries = _load_audit_log_fallback()
    entries.insert(0, entry)
    _persist_audit_log_fallback(entries)


def _format_month_label(year: int, month: int) -> str:
    index = max(1, min(month, 12)) - 1
    month_name = PERSIAN_MONTHS[index]
    return f"{month_name} {year}"


def _is_globally_enabled() -> bool:
    return (get_setting("enabled") or "true").strip().lower() == "true"


def _table_exists(cur, table_name: str) -> bool:
    try:
        schema = None
        name = table_name
        if "." in table_name:
            schema, name = table_name.split(".", 1)
        candidates = {name.strip("[]"), name, name.upper(), name.lower()}
        for candidate in candidates:
            if not candidate:
                continue
            params = [candidate]
            schema_clause = ""
            if schema:
                schema_clause = " AND TABLE_SCHEMA = ?"
                params.append(schema)
            row = cur.execute(
                f"SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = ?{schema_clause}",
                params,
            ).fetchone()
            if row:
                return True
    except Exception:
        return False
    return False


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    try:
        schema = None
        table = table_name
        if "." in table_name:
            schema, table = table_name.split(".", 1)
        params = [table.strip("[]"), column_name]
        schema_clause = ""
        if schema:
            schema_clause = " AND TABLE_SCHEMA = ?"
            params.insert(1, schema)
        row = cur.execute(
            f"SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ?{schema_clause} AND COLUMN_NAME = ?",
            params,
        ).fetchone()
        return bool(row)
    except Exception:
        return False


def _collect_metrics(cur) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
    totals = {"telegram": 0, "whatsapp": 0, "all": 0}
    monthly_map: OrderedDict = OrderedDict()

    def record(year: int, month: int, telegram: int = 0, whatsapp: int = 0) -> None:
        key = (year, month)
        bucket = monthly_map.setdefault(key, {"telegram": 0, "whatsapp": 0})
        bucket["telegram"] += telegram
        bucket["whatsapp"] += whatsapp

    if _column_exists(cur, "message_log", "platform"):
        rows = cur.execute(
            """
            SELECT
                YEAR(timestamp) AS y,
                MONTH(timestamp) AS m,
                SUM(CASE WHEN LOWER(platform) = 'telegram' THEN 1 ELSE 0 END) AS telegram_cnt,
                SUM(CASE WHEN LOWER(platform) = 'whatsapp' THEN 1 ELSE 0 END) AS whatsapp_cnt
            FROM message_log
            WHERE timestamp >= DATEADD(MONTH, -11, GETDATE())
            GROUP BY YEAR(timestamp), MONTH(timestamp)
            ORDER BY y, m
            """
        ).fetchall()
        for row in rows:
            year, month = int(row[0]), int(row[1])
            telegram_cnt = int(row[2] or 0)
            whatsapp_cnt = int(row[3] or 0)
            totals["telegram"] += telegram_cnt
            totals["whatsapp"] += whatsapp_cnt
            record(year, month, telegram_cnt, whatsapp_cnt)
    else:
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
        for row in rows:
            year, month = int(row[0]), int(row[1])
            count = int(row[2] or 0)
            totals["telegram"] += count
            record(year, month, telegram=count)

    whatsapp_sources = [
        "wa_message_log",
        "whatsapp_message_log",
        "whatsapp_log",
        "message_log_whatsapp",
    ]
    for table in whatsapp_sources:
        if _table_exists(cur, table):
            rows = cur.execute(
                f"""
                SELECT
                    YEAR(timestamp) AS y,
                    MONTH(timestamp) AS m,
                    COUNT(*) AS cnt
                FROM {table}
                WHERE timestamp >= DATEADD(MONTH, -11, GETDATE())
                GROUP BY YEAR(timestamp), MONTH(timestamp)
                ORDER BY y, m
                """
            ).fetchall()
            for row in rows:
                year, month = int(row[0]), int(row[1])
                count = int(row[2] or 0)
                totals["whatsapp"] += count
                record(year, month, whatsapp=count)
            break

    totals["all"] = totals["telegram"] + totals["whatsapp"]

    monthly: List[Dict[str, Any]] = []
    for (year, month), values in monthly_map.items():
        telegram = values.get("telegram", 0)
        whatsapp = values.get("whatsapp", 0)
        monthly.append(
            {
                "month": _format_month_label(year, month),
                "telegram": telegram,
                "whatsapp": whatsapp,
                "all": telegram + whatsapp,
            }
        )

    return totals, monthly


def _aggregate_metrics_from_db() -> Metrics:
    status = _build_status_snapshot()

    fallback = False
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            totals, monthly = _collect_metrics(cur)
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
    whatsapp = 185
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
        whatsapp = 35 + (offset * 2)
        results.append(
            {
                "month": label,
                "telegram": telegram,
                "whatsapp": whatsapp,
                "all": telegram + whatsapp,
            }
        )
    return results


def _load_platform_settings(enabled: bool) -> Dict[str, bool]:
    stored = _load_json_setting(PLATFORMS_KEY, None)
    defaults = {"telegram": enabled, "whatsapp": True}
    merged = {**defaults}
    if isinstance(stored, dict):
        for key, value in stored.items():
            if key in merged:
                merged[key] = bool(value)
    if not enabled:
        return {name: False for name in merged}
    return merged


def _merge_platform_flags(current: Dict[str, bool], overrides: Dict[str, Any]) -> Dict[str, bool]:
    merged = {**current}
    for key, value in overrides.items():
        if key in merged:
            merged[key] = bool(value)
    return merged


def _order_weekly_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize and order weekly schedule entries.

    Ensures day identifiers are integers, coerces empty strings to ``None`` and
    always provides a ``closed`` flag so the UI can reliably map persisted
    values even when the backend serialises numbers as strings (e.g. through
    certain ODBC drivers).
    """

    order_map = {day: index for index, day in enumerate(WORKING_DAY_ORDER)}
    normalised: List[Dict[str, Any]] = []

    for item in items:
        try:
            day = int(item.get("day"))
        except Exception:
            continue
        if day < 0 or day > 6:
            continue

        open_value = item.get("open")
        close_value = item.get("close")

        if isinstance(open_value, str):
            open_value = open_value.strip()
            if ":" in open_value and len(open_value) >= 5:
                open_value = open_value[:5]
        if isinstance(close_value, str):
            close_value = close_value.strip()
            if ":" in close_value and len(close_value) >= 5:
                close_value = close_value[:5]

        if hasattr(open_value, "strftime"):
            open_value = open_value.strftime("%H:%M")
        if hasattr(close_value, "strftime"):
            close_value = close_value.strftime("%H:%M")

        open_text = open_value if open_value else None
        close_text = close_value if close_value else None
        closed_flag = bool(item.get("closed")) or not (open_text and close_text)

        normalised.append(
            {
                "day": day,
                "open": None if closed_flag else open_text,
                "close": None if closed_flag else close_text,
                "closed": closed_flag,
            }
        )

    normalised.sort(
        key=lambda entry: order_map.get(entry["day"], len(WORKING_DAY_ORDER))
    )
    return normalised


def _legacy_weekly_schedule() -> List[Dict[str, Any]]:
    general_open = (get_setting("working_start") or "08:00").strip()
    general_close = (get_setting("working_end") or "18:00").strip()
    th_open = (get_setting("thursday_start") or general_open).strip()
    th_close = (get_setting("thursday_end") or general_close).strip()
    friday_disabled = (get_setting("disable_friday") or "true").lower() == "true"

    legacy: List[Dict[str, Any]] = []
    for day in WORKING_DAY_ORDER:
        if day == 3:  # Thursday
            open_time = th_open or None
            close_time = th_close or None
        elif day == 4:  # Friday
            if friday_disabled:
                open_time = None
                close_time = None
            else:
                open_time = general_open or None
                close_time = general_close or None
        else:
            open_time = general_open or None
            close_time = general_close or None
        legacy.append(
            {
                "day": day,
                "open": open_time,
                "close": close_time,
                "closed": not (open_time and close_time),
            }
        )
    return legacy


def _build_weekly_schedule() -> List[Dict[str, Any]]:
    try:
        entries = fetch_working_hours_entries()
    except Exception:
        LOGGER.debug("Falling back to legacy working hours settings", exc_info=True)
        return _order_weekly_items(_legacy_weekly_schedule())

    weekly: List[Dict[str, Any]] = []
    seen: set[int] = set()
    for entry in entries:
        try:
            day = int(entry.get("day"))
        except Exception:
            continue
        if day < 0 or day > 6 or day in seen:
            continue
        open_value = entry.get("open")
        close_value = entry.get("close")
        if entry.get("closed") or not (open_value and close_value):
            open_value = None
            close_value = None
        weekly.append({"day": day, "open": open_value, "close": close_value})
        seen.add(day)

    if len(weekly) < len(WORKING_DAY_ORDER):
        fallback_map = {item["day"]: item for item in _legacy_weekly_schedule()}
        for day in WORKING_DAY_ORDER:
            if day not in seen and day in fallback_map:
                weekly.append(fallback_map[day])

    return _order_weekly_items(weekly)


def _normalize_weekly_payload(payload: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: Dict[int, Dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        try:
            day = int(item.get("day"))
        except Exception:
            raise ControlPanelError("شناسه روز نامعتبر است.")
        if day < 0 or day > 6:
            raise ControlPanelError("شناسه روز باید بین 0 و 6 باشد.")

        open_raw = item.get("open")
        close_raw = item.get("close")
        if open_raw in (None, "") or close_raw in (None, ""):
            normalized[day] = {"day": day, "open": None, "close": None, "closed": True}
            continue

        open_text = _normalize_time(open_raw, "شروع کار")
        close_text = _normalize_time(close_raw, "پایان کار")
        try:
            open_time = datetime.strptime(open_text, "%H:%M").time()
            close_time = datetime.strptime(close_text, "%H:%M").time()
        except Exception:
            raise ControlPanelError("ساعت وارد شده نامعتبر است.")
        if open_time >= close_time:
            raise ControlPanelError("ساعت پایان باید بعد از ساعت شروع باشد.")

        normalized[day] = {
            "day": day,
            "open": open_text,
            "close": close_text,
            "closed": False,
        }

    if not normalized:
        raise ControlPanelError("هیچ ساعتی برای ذخیره ارسال نشده است.")

    return _order_weekly_items(list(normalized.values()))


def _sync_legacy_working_settings(entries: Iterable[Dict[str, Any]]) -> None:
    entries_map = {int(item["day"]): item for item in entries if "day" in item}
    general_candidates = [0, 1, 2, 5, 6, 3]
    general = next(
        (
            entries_map[day]
            for day in general_candidates
            if day in entries_map
            and entries_map[day].get("open")
            and entries_map[day].get("close")
        ),
        None,
    )
    if general:
        set_setting("working_start", general.get("open") or "09:00")
        set_setting("working_end", general.get("close") or "18:00")

    thursday = entries_map.get(3)
    if thursday and thursday.get("open") and thursday.get("close"):
        set_setting("thursday_start", thursday.get("open") or "")
        set_setting("thursday_end", thursday.get("close") or "")
    else:
        set_setting("thursday_start", "")
        set_setting("thursday_end", "")

    friday = entries_map.get(4)
    if not friday or friday.get("closed") or not (friday.get("open") and friday.get("close")):
        set_setting("disable_friday", "true")
    else:
        set_setting("disable_friday", "false")


def _build_status_snapshot() -> Dict[str, Any]:
    enabled = _is_globally_enabled()
    weekly = _build_weekly_schedule()
    platforms = _load_platform_settings(enabled)
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
    _append_audit_event(
        "ثبت دستور جدید",
        details=f"{command} (شناسه {new_item['id']})",
    )
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
            _append_audit_event(
                "ویرایش دستور",
                details=f"{updated['command']} (شناسه {command_id})",
            )
            return updated
    raise ControlPanelError("دستور مورد نظر یافت نشد.", status=404)


def delete_command(command_id: str) -> Dict[str, Any]:
    commands = get_commands()
    new_commands = [item for item in commands if item.get("id") != command_id]
    if len(new_commands) == len(commands):
        raise ControlPanelError("دستور مورد نظر یافت نشد.", status=404)
    _save_json_setting(COMMANDS_KEY, new_commands)
    _append_audit_event("حذف دستور", details=f"شناسه {command_id}")
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

    _append_audit_event("افزودن به لیست مسدود", details=f"کاربر {user_id}")
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
    _append_audit_event("حذف از لیست مسدود", details=f"کاربر {user_id}")
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


def get_audit_log(limit: int = 50) -> Dict[str, Any]:
    live_limit = limit if isinstance(limit, int) and limit > 0 else MAX_AUDIT_LOG_ENTRIES
    try:
        entries, total = fetch_audit_log_entries(live_limit)
        if limit > 0 and len(entries) > limit:
            entries = entries[:limit]
        return {
            "items": entries,
            "total": total,
            "dataSource": "live",
        }
    except Exception:
        LOGGER.debug("Falling back to settings-based audit log entries", exc_info=True)

    entries = _load_audit_log_fallback()
    total = len(entries)
    if limit > 0:
        entries = entries[:limit]
    return {
        "items": entries,
        "total": total,
        "dataSource": "fallback",
    }


def update_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    changes: List[str] = []
    timezone_value = payload.get("timezone")
    if timezone_value is not None:
        timezone_clean = timezone_value.strip() or "Asia/Tehran"
        set_setting(TIMEZONE_KEY, timezone_clean)
        changes.append("منطقه زمانی")

    weekly = payload.get("weekly")
    if weekly is not None:
        if not isinstance(weekly, list):
            raise ControlPanelError("ساختار ساعات کاری نامعتبر است.")

        normalized = _normalize_weekly_payload(weekly)
        try:
            current = {int(item.get("day")): item for item in fetch_working_hours_entries()}
        except Exception:
            current = {}
        for entry in normalized:
            current[int(entry["day"])] = entry
        try:
            save_working_hours_entries(current.values())
        except Exception:
            LOGGER.exception("Failed to persist working hours entries")
            raise ControlPanelError(
                "ذخیره‌سازی ساعات کاری امکان‌پذیر نبود. دوباره تلاش کنید.",
                status=500,
            )
        try:
            _sync_legacy_working_settings(current.values())
        except Exception:
            LOGGER.debug("Failed to sync legacy working hour settings", exc_info=True)
        try:
            runtime.refresh_working_hours_cache()
        except Exception:
            LOGGER.debug("Failed to refresh runtime working hours cache", exc_info=True)
        changes.append("ساعات کاری")

    platforms = payload.get("platforms")
    if isinstance(platforms, dict):
        current = _load_platform_settings(True)
        normalized = _merge_platform_flags(current, platforms)
        _save_json_setting(PLATFORMS_KEY, normalized)
        try:
            active = _is_globally_enabled()
            effective = _load_platform_settings(active)
            runtime.apply_platform_states(effective, active=active)
        except Exception:
            LOGGER.debug("Skipping runtime platform sync due to runtime error.", exc_info=True)
        changes.append("پلتفرم‌ها")

    if "lunchBreak" in payload:
        lunch_break = payload.get("lunchBreak") or {}
        if not isinstance(lunch_break, dict):
            raise ControlPanelError("ساختار بازه ناهار نامعتبر است.")
        start = _normalize_time(lunch_break.get("start"), "شروع ناهار")
        end = _normalize_time(lunch_break.get("end"), "پایان ناهار")
        set_setting(LUNCH_START_KEY, start)
        set_setting(LUNCH_END_KEY, end)
        changes.append("استراحت ناهار")

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
        changes.append("محدودیت استعلام")

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
        changes.append("اطلاعات تحویل")

    if changes:
        unique_changes = []
        for item in changes:
            if item not in unique_changes:
                unique_changes.append(item)
        details = "، ".join(unique_changes)
        _append_audit_event("به‌روزرسانی تنظیمات", details=details)

    return get_settings()


def toggle_bot(active: bool) -> Dict[str, Any]:
    set_setting("enabled", "true" if active else "false")
    try:
        platforms = _load_platform_settings(active)
        runtime.apply_platform_states(platforms, active=active)
    except Exception:
        LOGGER.debug("Skipping runtime platform sync due to runtime error.", exc_info=True)
    status = _build_status_snapshot()
    _append_audit_event(
        "تغییر وضعیت ربات",
        details="فعال" if active else "غیرفعال",
    )
    return status


def get_platform_snapshot() -> Tuple[bool, Dict[str, bool]]:
    enabled = _is_globally_enabled()
    platforms = _load_platform_settings(enabled)
    return enabled, platforms


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
    _append_audit_event("به‌روزرسانی کش کالا", details=timestamp)
    return {"lastUpdatedISO": timestamp}


def get_health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "time": _now_iso(),
    }
