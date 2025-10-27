import json
import logging
import re
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pyodbc
from config import BOT_DB_CONFIG, DB_CONFIG
from utils.code_standardization import normalize_code
from .panel_inventory import build_part_name_map, process_data

LOGGER = logging.getLogger(__name__)

_SPAM_GUARD_WINDOW_SECONDS = 2

# def get_connection():
#     conn_str = (
#         f"DRIVER={BOT_DB_CONFIG['driver']};"
#         f"SERVER={BOT_DB_CONFIG['server']};"
#         f"DATABASE={BOT_DB_CONFIG['database']};"
#         f"Trusted_Connection={BOT_DB_CONFIG.get('trusted_connection','no')};"
#     )
#     return pyodbc.connect(conn_str, timeout=30)
_TABLES_ENSURED = False

_DEFAULT_WORKING_HOURS: List[Dict[str, Any]] = [
    {"day": 0, "open": "09:00", "close": "18:00", "closed": False},  # Monday
    {"day": 1, "open": "09:00", "close": "18:00", "closed": False},  # Tuesday
    {"day": 2, "open": "09:00", "close": "18:00", "closed": False},  # Wednesday
    {"day": 3, "open": "09:00", "close": "18:00", "closed": False},  # Thursday
    {"day": 4, "open": None, "close": None, "closed": True},            # Friday (closed)
    {"day": 5, "open": "09:00", "close": "18:00", "closed": False},  # Saturday
    {"day": 6, "open": "09:00", "close": "18:00", "closed": False},  # Sunday
]

_MAX_SEARCH_TOKENS = 5
_TOKEN_SPLIT_PATTERN = re.compile(r"[\s\-_/]+")

_INVENTORY_ITEMS_QUERY = """
    SELECT
        i.Code AS [کد کالا],
        i.iranCode AS [Iran Code],
        i.Title AS [نام کالا],
        i.UnitTitle AS [واحد سنجش],
        i.SaleGroupTitle AS [گروه فروش],
        p.PropertyAmount1 AS [مشخصات کالا]
    FROM inv.vwItem AS i
    LEFT JOIN inv.vwItemPropertyAmount AS p
        ON i.ItemID = p.ItemRef
    WHERE i.Type = 1
    ORDER BY i.Code
"""

_inventory_name_cache: Dict[str, str] = {}


def get_connection():
    conn_str = (
        f"DRIVER={BOT_DB_CONFIG['driver']};"
        f"SERVER={BOT_DB_CONFIG['server']};"
        f"DATABASE={BOT_DB_CONFIG['database']};"
        f"UID={BOT_DB_CONFIG['user']};"
        f"PWD={BOT_DB_CONFIG['password']};"
    )
    return pyodbc.connect(conn_str, timeout=30)


def _open_inventory_connection() -> pyodbc.Connection:
    cfg = DB_CONFIG
    conn_str = (
        f"DRIVER={cfg['driver']};"
        f"SERVER={cfg['server']};"
        f"DATABASE={cfg['database']};"
        f"UID={cfg['user']};"
        f"PWD={cfg['password']};"
        "Encrypt=yes;TrustServerCertificate=yes;"
    )
    return pyodbc.connect(conn_str, timeout=30)


def _fetch_part_names_from_inventory(
    code_pairs: Iterable[Tuple[str, str]]
) -> Dict[str, str]:
    """Return part-name mapping for the provided codes without stock filters.

    ``code_pairs`` must contain tuples of ``(code_norm, code_display)``. The
    query intentionally uses ``LEFT JOIN`` and avoids any ``quantity`` filter so
    that parts without stock still return their latest title.
    """

    unique_pairs: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for norm, display in code_pairs:
        norm_value = (norm or "").strip().upper()
        display_value = (display or "").strip().upper()
        key = norm_value or display_value.replace("-", "")
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append((norm_value, display_value))

    if not unique_pairs:
        return {}

    selects = " UNION ALL\n            ".join("SELECT ?, ?" for _ in unique_pairs)
    params: List[str] = []
    for norm_value, display_value in unique_pairs:
        params.extend([norm_value, display_value])

    primary_query = f"""
        DECLARE @FiscalYear INT = (SELECT MAX(FiscalYearId) FROM FMK.FiscalYear);

        WITH requested(code_norm, code_display) AS (
            {selects}
        ),
        items AS (
            SELECT
                REPLACE(i.Code, '-', '') AS code_norm,
                i.Code AS code_display,
                i.Title AS part_name
            FROM inv.vwItem AS i
        ),
        aggregated AS (
            SELECT
                req.code_norm,
                req.code_display,
                COALESCE(NULLIF(LTRIM(RTRIM(items.part_name)), ''), '-') AS part_name,
                MAX(COALESCE(stock.Quantity, 0)) AS quantity
            FROM requested AS req
            LEFT JOIN items
                ON items.code_norm = req.code_norm
            LEFT JOIN inv.vwItemStockSummary AS stock
                ON stock.ItemCode = items.code_display
               AND stock.FiscalYearRef = @FiscalYear
            GROUP BY
                req.code_norm,
                req.code_display,
                COALESCE(NULLIF(LTRIM(RTRIM(items.part_name)), ''), '-')
        )
        SELECT code_norm, code_display, part_name
        FROM aggregated
    """

    fallback_query = f"""
        WITH requested(code_norm, code_display) AS (
            {selects}
        ),
        items AS (
            SELECT
                REPLACE(i.Code, '-', '') AS code_norm,
                i.Code AS code_display,
                i.Title AS part_name
            FROM inv.vwItem AS i
        )
        SELECT
            req.code_norm,
            req.code_display,
            COALESCE(NULLIF(LTRIM(RTRIM(items.part_name)), ''), '-') AS part_name
        FROM requested AS req
        LEFT JOIN items
            ON items.code_norm = req.code_norm
    """

    try:
        with _open_inventory_connection() as conn:
            cur = conn.cursor()
            try:
                rows = cur.execute(primary_query, *params).fetchall()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                rows = cur.execute(fallback_query, *params).fetchall()
    except Exception:
        return {}

    result: Dict[str, str] = {}
    for row in rows:
        norm_value = (row[0] or "").strip().upper()
        display_value = (row[1] or "").strip().upper()
        part_name = (row[2] or "-").strip() or "-"
        key = norm_value or display_value.replace("-", "")
        if not key:
            continue
        if part_name == "-":
            continue
        result[key] = part_name

    return result


def _ensure_tables(cur) -> None:
    cur.execute(
        """
        IF OBJECT_ID('control_panel_audit_log', 'U') IS NULL
        BEGIN
            CREATE TABLE control_panel_audit_log (
                id INT IDENTITY(1,1) PRIMARY KEY,
                [timestamp] DATETIME NOT NULL DEFAULT (GETDATE()),
                actor NVARCHAR(100) NULL,
                message NVARCHAR(500) NOT NULL,
                details NVARCHAR(MAX) NULL
            );
            CREATE INDEX IX_control_panel_audit_log_timestamp
                ON control_panel_audit_log([timestamp]);
        END;
        IF OBJECT_ID('whatsapp_message_log', 'U') IS NULL
        BEGIN
            CREATE TABLE whatsapp_message_log (
                id INT IDENTITY(1,1) PRIMARY KEY,
                chat_identifier NVARCHAR(255) NULL,
                direction NVARCHAR(20) NOT NULL,
                [text] NVARCHAR(MAX) NULL,
                [timestamp] DATETIME NOT NULL DEFAULT (GETDATE())
            );
            CREATE INDEX IX_whatsapp_message_log_timestamp
                ON whatsapp_message_log([timestamp]);
        END;
        IF OBJECT_ID('control_panel_working_hours', 'U') IS NULL
        BEGIN
            CREATE TABLE control_panel_working_hours (
                day_of_week INT NOT NULL PRIMARY KEY,
                open_time TIME NULL,
                close_time TIME NULL,
                is_closed BIT NOT NULL DEFAULT (0),
                updated_at DATETIME NOT NULL DEFAULT (GETDATE())
            );
        END;
        WITH required AS (
            SELECT *
            FROM (VALUES
                (0, '09:00', '18:00', 0),
                (1, '09:00', '18:00', 0),
                (2, '09:00', '18:00', 0),
                (3, '09:00', '18:00', 0),
                (4, NULL,    NULL,    1),
                (5, '09:00', '18:00', 0),
                (6, '09:00', '18:00', 0)
            ) AS defaults(day_of_week, open_time, close_time, is_closed)
        )
        MERGE control_panel_working_hours AS target
        USING required AS src
            ON target.day_of_week = src.day_of_week
        WHEN NOT MATCHED THEN
            INSERT (day_of_week, open_time, close_time, is_closed, updated_at)
            VALUES (src.day_of_week, src.open_time, src.close_time, src.is_closed, GETDATE());
        IF OBJECT_ID('platform_code_log', 'U') IS NULL
        BEGIN
            CREATE TABLE platform_code_log (
                id BIGINT IDENTITY(1,1) PRIMARY KEY,
                platform NVARCHAR(50) NOT NULL,
                code_norm NVARCHAR(10) NOT NULL,
                code_display NVARCHAR(11) NOT NULL,
                part_name NVARCHAR(255) NULL,
                requested_at DATETIME2 NOT NULL DEFAULT (SYSUTCDATETIME())
            );
            CREATE INDEX IX_platform_code_log_requested_at
                ON platform_code_log(requested_at);
            CREATE INDEX IX_platform_code_log_code
                ON platform_code_log(code_norm, platform);
        END;
        """
    )


def ensure_control_panel_tables() -> bool:
    """Create audit/log tables when missing. Returns True on success."""

    global _TABLES_ENSURED
    if _TABLES_ENSURED:
        return True
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            _ensure_tables(cur)
            conn.commit()
        _TABLES_ENSURED = True
        return True
    except Exception as e:
        print("❌ خطا در ensure_control_panel_tables:", e)
        _TABLES_ENSURED = False
        return False


def _format_time_value(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, time):
        return value.strftime("%H:%M")
    text = str(value).strip()
    if not text:
        return None
    if len(text) >= 5 and ":" in text:
        return text[:5]
    return text


def fetch_working_hours_entries() -> List[Dict[str, Any]]:
    if not ensure_control_panel_tables():
        raise RuntimeError("control panel tables are unavailable")

    query = """
        SELECT day_of_week, open_time, close_time, is_closed
        FROM control_panel_working_hours
    """

    entries: List[Dict[str, Any]] = []
    with get_connection() as conn:
        cur = conn.cursor()
        rows = cur.execute(query).fetchall()
    for row in rows:
        day = int(row[0])
        open_value = _format_time_value(row[1])
        close_value = _format_time_value(row[2])
        is_closed = bool(row[3])
        if is_closed:
            open_value = None
            close_value = None
        entries.append({
            "day": day,
            "open": open_value,
            "close": close_value,
            "closed": is_closed,
        })
    if not entries:
        return [dict(item) for item in _DEFAULT_WORKING_HOURS]
    return entries


def save_working_hours_entries(entries: Iterable[Dict[str, Any]]) -> None:
    if not ensure_control_panel_tables():
        raise RuntimeError("control panel tables are unavailable")

    sql = """
        MERGE control_panel_working_hours AS target
        USING (SELECT ? AS day_of_week) AS src
            ON target.day_of_week = src.day_of_week
        WHEN MATCHED THEN
            UPDATE SET
                open_time = ?,
                close_time = ?,
                is_closed = ?,
                updated_at = GETDATE()
        WHEN NOT MATCHED THEN
            INSERT (day_of_week, open_time, close_time, is_closed, updated_at)
            VALUES (src.day_of_week, ?, ?, ?, GETDATE());
    """

    payload = []
    for item in entries:
        day = int(item.get("day"))
        open_value = _format_time_value(item.get("open"))
        close_value = _format_time_value(item.get("close"))
        closed = bool(item.get("closed")) or not (open_value and close_value)
        if closed:
            open_value = None
            close_value = None
        payload.append((day, open_value, close_value, 1 if closed else 0))

    with get_connection() as conn:
        cur = conn.cursor()
        for day, open_value, close_value, closed_flag in payload:
            cur.execute(
                sql,
                day,
                open_value,
                close_value,
                closed_flag,
                open_value,
                close_value,
                closed_flag,
            )
        conn.commit()
def log_message(user_id, chat_id, direction, text):
    try:
        uid = int(user_id)
        cid = int(chat_id)
        d = str(direction)
        t = str(text)
    except:
        return
    query = """
        INSERT INTO message_log (user_id, chat_id, direction, text, timestamp)
        VALUES (?, ?, ?, ?, GETDATE())
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, uid, cid, d, t)
            conn.commit()
    except Exception as e:
        print("❌ خطا در log_message:", e)


def log_whatsapp_message(chat_identifier: Optional[str], direction: str, text: str) -> None:
    direction = str(direction or "out")
    chat_value = None if chat_identifier is None else str(chat_identifier)[:255]
    payload = str(text or "")
    if not ensure_control_panel_tables():
        return
    query = """
        INSERT INTO whatsapp_message_log (chat_identifier, direction, [text], [timestamp])
        VALUES (?, ?, ?, GETDATE())
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, chat_value, direction, payload)
            conn.commit()
    except Exception as e:
        print("❌ خطا در log_whatsapp_message:", e)


def record_code_request(
    *,
    platform: str,
    code_norm: str,
    code_display: str,
    part_name: Optional[str],
    requested_at: datetime,
) -> None:
    if not ensure_control_panel_tables():
        raise RuntimeError("control panel tables are unavailable")

    platform_value = (platform or "unknown").strip() or "unknown"
    platform_value = platform_value[:50]
    norm_value = (code_norm or "").strip().upper()[:10]
    display_value = (code_display or "").strip().upper()[:11]
    if not norm_value:
        raise ValueError("code_norm is required")
    if not display_value:
        padded = norm_value.ljust(10, "X")[:10]
        display_value = f"{padded[:5]}-{padded[5:]}"

    name_value = (part_name or "-").strip() or "-"
    name_value = name_value[:255]

    timestamp = requested_at
    if timestamp.tzinfo is not None:
        timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)

    guard_seconds = int(max(1, _SPAM_GUARD_WINDOW_SECONDS))
    query = """
        DECLARE @now DATETIME2 = ?;
        DECLARE @platform NVARCHAR(50) = ?;
        DECLARE @code_norm NVARCHAR(10) = ?;
        DECLARE @code_display NVARCHAR(11) = ?;
        DECLARE @part_name NVARCHAR(255) = ?;
        DECLARE @guard_seconds INT = ?;

        IF NOT EXISTS (
            SELECT 1
            FROM platform_code_log
            WHERE platform = @platform
              AND code_norm = @code_norm
              AND requested_at >= DATEADD(SECOND, -@guard_seconds, @now)
        )
        BEGIN
            INSERT INTO platform_code_log (platform, code_norm, code_display, part_name, requested_at)
            VALUES (@platform, @code_norm, @code_display, @part_name, @now);
        END
        ELSE IF (
            @part_name IS NOT NULL
            AND LTRIM(RTRIM(@part_name)) <> ''
            AND @part_name <> '-'
        )
        BEGIN
            UPDATE platform_code_log
            SET part_name = @part_name
            WHERE id IN (
                SELECT TOP (1) id
                FROM platform_code_log
                WHERE platform = @platform
                  AND code_norm = @code_norm
                  AND (
                      part_name IS NULL
                      OR part_name = '-'
                      OR LTRIM(RTRIM(part_name)) = ''
                  )
                ORDER BY requested_at DESC, id DESC
            );
        END
    """

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            query,
            timestamp,
            platform_value,
            norm_value,
            display_value,
            name_value,
            guard_seconds,
        )
        conn.commit()


def _prepare_search_tokens(search: Optional[str]) -> List[Tuple[str, str]]:
    if not search:
        return []

    tokens: List[Tuple[str, str]] = []
    seen: set[str] = set()
    for raw in re.split(r"\s+", str(search)):
        token = raw.strip()
        if not token:
            continue
        upper_token = token.upper()
        if upper_token in seen:
            continue
        seen.add(upper_token)
        normalized = normalize_code(token).upper()
        tokens.append((upper_token, normalized))
        if len(tokens) >= _MAX_SEARCH_TOKENS:
            break
    return tokens


def _split_words(value: str) -> List[str]:
    if not value:
        return []
    cleaned = _TOKEN_SPLIT_PATTERN.sub(" ", str(value).upper())
    return [segment for segment in cleaned.split() if segment]


def _token_matches_text(token: str, text: str) -> bool:
    if not token or not text:
        return False
    for segment in _split_words(text):
        if segment.startswith(token):
            return True
    return False


def _record_matches_tokens(
    tokens: Iterable[Tuple[str, str]],
    *,
    code_display: str,
    code_norm: str,
    part_name: str,
) -> bool:
    upper_norm = (code_norm or "").upper()
    for raw_token, normalized_token in tokens:
        if _token_matches_text(raw_token, code_display):
            continue
        if normalized_token and upper_norm.startswith(normalized_token):
            continue
        if _token_matches_text(raw_token, part_name):
            continue
        return False
    return True


def _load_inventory_name_map() -> Dict[str, str]:
    try:
        with _open_inventory_connection() as conn:
            cur = conn.cursor()
            rows = cur.execute(_INVENTORY_ITEMS_QUERY).fetchall()
            columns = [column[0] for column in cur.description] if cur.description else []
    except Exception:
        LOGGER.exception("Failed to fetch inventory items for control panel")
        return {}

    raw_rows: List[Dict[str, Any]] = []
    if not columns:
        columns = [
            "کد کالا",
            "Iran Code",
            "نام کالا",
            "واحد سنجش",
            "گروه فروش",
            "مشخصات کالا",
        ]
    for row in rows:
        entry: Dict[str, Any] = {}
        for idx, column in enumerate(columns):
            if idx >= len(row):
                break
            entry[column] = row[idx]
        raw_rows.append(entry)

    processed_records = process_data(raw_rows)
    mapping = build_part_name_map(processed_records)

    LOGGER.debug(
        "Loaded %d inventory part names from %d records", len(mapping), len(processed_records)
    )
    return mapping


def get_inventory_name_map(*, refresh: bool = False) -> Dict[str, str]:
    global _inventory_name_cache

    if refresh or not _inventory_name_cache:
        mapping = _load_inventory_name_map()
        _inventory_name_cache = mapping

    return dict(_inventory_name_cache)


def _resolve_code_range(range_key: str) -> Optional[datetime]:
    key = (range_key or "1m").strip().lower()
    if key in {"all", "کل", "0", "*"}:
        return None

    mapping = {
        "1m": 30,
        "2m": 60,
        "3m": 90,
        "6m": 180,
        "1y": 365,
    }

    days = mapping.get(key)
    if days is None:
        days = mapping["1m"]
    start = datetime.utcnow() - timedelta(days=days)
    return start.replace(tzinfo=None)


def fetch_code_statistics(
    *,
    range_key: str,
    sort_order: str,
    page: int,
    page_size: int,
    search: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    if not ensure_control_panel_tables():
        raise RuntimeError("control panel tables are unavailable")

    try:
        inventory_map = get_inventory_name_map()
    except Exception:
        LOGGER.debug("Unable to load inventory name cache", exc_info=True)
        inventory_map = {}

    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 100))
    offset = (page - 1) * page_size
    order = "ASC" if (sort_order or "").lower().startswith("a") else "DESC"
    start = _resolve_code_range(range_key)

    params: List[Any] = []
    filters: List[str] = []
    if start is not None:
        filters.append("requested_at >= ?")
        params.append(start)

    search_tokens = _prepare_search_tokens(search)
    name_code_matches: List[str] = []
    if search_tokens and inventory_map:
        for norm_code, part_name in inventory_map.items():
            if all(_token_matches_text(raw_token, part_name) for raw_token, _ in search_tokens):
                name_code_matches.append(norm_code)
        # keep the IN clause reasonably small
        if len(name_code_matches) > 500:
            name_code_matches = name_code_matches[:500]

    if search_tokens:
        code_expr = (
            "UPPER(N' ' + REPLACE(REPLACE(REPLACE(platform_code_log.code_display, '-', N' '), '/', N' '), N'_', N' '))"
        )
        name_expr = (
            "UPPER(N' ' + REPLACE(REPLACE(REPLACE(COALESCE(platform_code_log.part_name, N''), '-', N' '), '/', N' '), N'_', N' '))"
        )
        token_clauses: List[str] = []
        for raw_token, normalized_token in search_tokens:
            clause_parts = [
                f"{code_expr} LIKE UPPER(N'% ' + CAST(? AS NVARCHAR(200)) + N'%')",
                f"{name_expr} LIKE UPPER(N'% ' + CAST(? AS NVARCHAR(200)) + N'%')",
            ]
            params.extend([raw_token, raw_token])
            if normalized_token:
                clause_parts.append(
                    "UPPER(platform_code_log.code_norm) LIKE UPPER(CAST(? AS NVARCHAR(50)) + N'%')"
                )
                params.append(normalized_token)
            token_clauses.append("(" + " OR ".join(clause_parts) + ")")

        combined_clause = "(" + " AND ".join(token_clauses) + ")" if token_clauses else ""
        clause_options: List[str] = []
        if combined_clause:
            clause_options.append(combined_clause)
        if name_code_matches:
            placeholders = ", ".join("?" for _ in name_code_matches)
            clause_options.append(f"platform_code_log.code_norm IN ({placeholders})")
        if clause_options:
            filters.append("(" + " OR ".join(clause_options) + ")")
            params.extend(name_code_matches)

    where_clause = ""
    if filters:
        where_clause = "WHERE " + " AND ".join(filters)

    base_query = f"""
        WITH filtered AS (
            SELECT code_norm, code_display, part_name, requested_at, platform
            FROM platform_code_log
            {where_clause}
        ),
        aggregated AS (
            SELECT
                code_norm,
                code_display,
                COUNT(*) AS request_count
            FROM filtered
            GROUP BY code_norm, code_display
        ),
        labeled AS (
            SELECT
                a.code_norm,
                a.code_display,
                a.request_count,
                COALESCE(NULLIF(latest.part_name, ''), '-') AS part_name
            FROM aggregated AS a
            OUTER APPLY (
                SELECT TOP 1 part_name
                FROM filtered AS f
                WHERE f.code_norm = a.code_norm
                  AND f.code_display = a.code_display
                ORDER BY
                    CASE
                        WHEN f.part_name IS NOT NULL
                             AND LTRIM(RTRIM(f.part_name)) <> ''
                             AND f.part_name <> '-' THEN 0
                        ELSE 1
                    END,
                    f.requested_at DESC
            ) AS latest
        )
    """

    count_query = base_query + "\n    SELECT COUNT(*) FROM labeled"

    data_query_template = base_query + f"""
        SELECT code_display, code_norm, part_name, request_count
        FROM labeled
        ORDER BY request_count {order}, code_display ASC
        {{pagination_clause}}
    """

    with get_connection() as conn:
        cur = conn.cursor()
        pagination_clause = ""
        exec_params = list(params)

        if not search_tokens:
            if params:
                total_row = cur.execute(count_query, *params).fetchone()
            else:
                total_row = cur.execute(count_query).fetchone()
            total = int(total_row[0]) if total_row else 0
            pagination_clause = "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
            exec_params.extend([offset, page_size])
        else:
            total = 0

        final_query = data_query_template.format(pagination_clause=pagination_clause)
        rows = cur.execute(final_query, *exec_params).fetchall()

    records: List[Dict[str, Any]] = []
    for row in rows:
        code_display, code_norm, part_name_value, count_value = row
        code_display_text = str(code_display or "").strip()
        code_norm_text = str(code_norm or "").strip().upper()
        normalized_code = code_norm_text or normalize_code(code_display_text).upper()
        mapped_name = inventory_map.get(normalized_code, "") if normalized_code else ""
        part_name_text = str(part_name_value or "").strip()
        final_name = mapped_name or part_name_text or "-"
        records.append(
            {
                "code": code_display_text,
                "norm": normalized_code,
                "part_name": final_name,
                "request_count": int(count_value or 0),
            }
        )

    if search_tokens:
        filtered_records: List[Dict[str, Any]] = []
        for item in records:
            if _record_matches_tokens(
                search_tokens,
                code_display=item["code"],
                code_norm=item.get("norm", ""),
                part_name=item.get("part_name", ""),
            ):
                filtered_records.append(item)
        records = filtered_records
        total = len(records)

        if total:
            max_offset = ((total - 1) // page_size) * page_size
            start_index = min(max(offset, 0), max_offset)
        else:
            start_index = 0
        end_index = start_index + page_size
        paged_records = records[start_index:end_index]
    else:
        paged_records = records

    items: List[Dict[str, Any]] = []
    for item in paged_records:
        items.append(
            {
                "code": item["code"],
                "part_name": item.get("part_name", "-"),
                "request_count": item.get("request_count", 0),
            }
        )

    if not search_tokens:
        return items, total

    return items, len(records)


def fetch_code_statistics_for_export(
    *,
    date_from: Optional[datetime],
    date_to: Optional[datetime],
    min_request_count: Optional[int],
    include_peak_period: bool,
    peak_period: str,
) -> List[Dict[str, Any]]:
    if not ensure_control_panel_tables():
        raise RuntimeError("control panel tables are unavailable")

    try:
        inventory_map = get_inventory_name_map()
    except Exception:
        LOGGER.debug("Unable to load inventory name cache", exc_info=True)
        inventory_map = {}

    filters: List[str] = []
    params: List[Any] = []

    if date_from is not None:
        filters.append("requested_at >= ?")
        params.append(date_from)

    if date_to is not None:
        filters.append("requested_at <= ?")
        params.append(date_to)

    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    peak_join = ""
    peak_select = "NULL AS peak_period, NULL AS peak_count"
    peak_group_expression = ""

    if include_peak_period:
        normalized_period = (peak_period or "day").lower()
        if normalized_period == "year":
            peak_group_expression = "CAST(YEAR(f.requested_at) AS NVARCHAR(4))"
        elif normalized_period == "month":
            peak_group_expression = (
                "CONCAT(CAST(YEAR(f.requested_at) AS NVARCHAR(4)), N'-', RIGHT('0' + CAST(MONTH(f.requested_at) AS NVARCHAR(2)), 2))"
            )
        else:
            peak_group_expression = "CONVERT(NVARCHAR(10), f.requested_at, 23)"

        peak_join = f"""
        OUTER APPLY (
            SELECT TOP 1
                {peak_group_expression} AS peak_period,
                COUNT(*) AS peak_count
            FROM filtered AS f
            WHERE f.code_norm = a.code_norm
              AND f.code_display = a.code_display
            GROUP BY {peak_group_expression}
            ORDER BY COUNT(*) DESC, {peak_group_expression} ASC
        ) AS peak
        """
        peak_select = "peak.peak_period, peak.peak_count"

    final_filter_clause = ""
    final_params = list(params)
    if min_request_count is not None:
        final_filter_clause = "WHERE labeled.request_count >= ?"
        final_params.append(int(min_request_count))

    query = f"""
        WITH filtered AS (
            SELECT code_norm, code_display, part_name, requested_at
            FROM platform_code_log
            {where_clause}
        ),
        aggregated AS (
            SELECT
                code_norm,
                code_display,
                COUNT(*) AS request_count
            FROM filtered
            GROUP BY code_norm, code_display
        ),
        labeled AS (
            SELECT
                a.code_norm,
                a.code_display,
                a.request_count,
                COALESCE(NULLIF(latest.part_name, ''), '-') AS part_name,
                {peak_select}
            FROM aggregated AS a
            OUTER APPLY (
                SELECT TOP 1 part_name
                FROM filtered AS f
                WHERE f.code_norm = a.code_norm
                  AND f.code_display = a.code_display
                ORDER BY
                    CASE
                        WHEN f.part_name IS NOT NULL
                             AND LTRIM(RTRIM(f.part_name)) <> ''
                             AND f.part_name <> '-' THEN 0
                        ELSE 1
                    END,
                    f.requested_at DESC
            ) AS latest
            {peak_join}
        )
        SELECT
            code_norm,
            code_display,
            part_name,
            request_count,
            peak_period,
            peak_count
        FROM labeled
        {final_filter_clause}
        ORDER BY request_count DESC, code_display ASC
    """

    with get_connection() as conn:
        cur = conn.cursor()
        rows = cur.execute(query, *final_params).fetchall()

    result: List[Dict[str, Any]] = []
    for row in rows:
        code_norm_value = (row[0] or "").strip().upper()
        code_display_value = (row[1] or "").strip()
        part_name_value = (row[2] or "").strip()
        request_count_value = int(row[3] or 0)
        peak_period_value = (row[4] or "").strip() if len(row) > 4 else ""
        peak_count_value = int(row[5] or 0) if len(row) > 5 and row[5] is not None else 0

        normalized_code = code_norm_value or normalize_code(code_display_value).upper()
        mapped_name = inventory_map.get(normalized_code, "") if normalized_code else ""
        final_name = mapped_name or part_name_value or "-"

        result.append(
            {
                "code_norm": normalized_code,
                "code_display": code_display_value,
                "part_name": final_name,
                "request_count": request_count_value,
                "peak_period": peak_period_value,
                "peak_count": peak_count_value,
            }
        )

    return result


def refresh_missing_code_names(limit: int = 250) -> int:
    if not ensure_control_panel_tables():
        raise RuntimeError("control panel tables are unavailable")

    try:
        safe_limit = int(limit)
    except Exception:
        safe_limit = 250
    safe_limit = max(1, min(safe_limit, 1000))

    missing_query = """
        WITH missing AS (
            SELECT
                code_norm,
                code_display,
                MAX(requested_at) AS last_requested_at
            FROM platform_code_log
            WHERE part_name IS NULL
               OR LTRIM(RTRIM(part_name)) = ''
               OR part_name = '-'
            GROUP BY code_norm, code_display
        )
        SELECT TOP (?) code_norm, code_display
        FROM missing
        ORDER BY last_requested_at DESC
    """

    with get_connection() as conn:
        cur = conn.cursor()
        rows = cur.execute(missing_query, safe_limit).fetchall()

    if not rows:
        return 0

    pairs: List[Tuple[str, str]] = []
    for row in rows:
        norm_value = (row[0] or "").strip().upper()
        display_value = (row[1] or "").strip().upper()
        if not norm_value:
            continue
        pairs.append((norm_value, display_value))

    replacements = _fetch_part_names_from_inventory(pairs)
    if not replacements:
        return 0

    updated_rows = 0
    update_query = """
        UPDATE platform_code_log
        SET part_name = ?
        WHERE code_norm = ?
          AND (
              part_name IS NULL
              OR part_name = '-'
              OR LTRIM(RTRIM(part_name)) = ''
          )
    """

    with get_connection() as conn:
        cur = conn.cursor()
        for norm_value, display_value in pairs:
            key = norm_value or display_value.replace("-", "")
            part_name = replacements.get(key)
            if not part_name or part_name == "-":
                continue
            cur.execute(update_query, part_name, norm_value)
            updated_rows += cur.rowcount or 0
        conn.commit()

    return int(updated_rows)


def _serialize_details(details: Any) -> Optional[str]:
    if details is None:
        return None
    if isinstance(details, str):
        return details
    try:
        return json.dumps(details, ensure_ascii=False)
    except Exception:
        return str(details)


def record_audit_event(message: str, *, actor: str = "کنترل‌پنل", details: Any = None) -> None:
    if not ensure_control_panel_tables():
        raise RuntimeError("control panel tables are unavailable")
    msg = str(message or "").strip()
    if not msg:
        raise ValueError("message is required")
    actor_value = str(actor or "کنترل‌پنل")[:100]
    details_value = _serialize_details(details)
    query = """
        INSERT INTO control_panel_audit_log ([timestamp], actor, message, details)
        VALUES (GETDATE(), ?, ?, ?)
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(query, actor_value, msg[:500], details_value)
        conn.commit()


def fetch_audit_log_entries(limit: int = 200, offset: int = 0) -> Tuple[List[dict], int]:
    if not ensure_control_panel_tables():
        raise RuntimeError("control panel tables are unavailable")
    limit = max(1, min(int(limit or 0), 500))
    offset = max(0, int(offset or 0))
    base_query = """
        SELECT
            id,
            [timestamp],
            actor,
            message,
            details
        FROM control_panel_audit_log
        ORDER BY [timestamp] DESC, id DESC
    """
    paginated_query = base_query + " OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
    count_query = "SELECT COUNT(*) FROM control_panel_audit_log"
    entries: List[dict] = []
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            rows = cur.execute(paginated_query, offset, limit).fetchall()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            fetch_size = limit + offset
            fallback_query = f"""
                SELECT TOP {fetch_size}
                    id,
                    [timestamp],
                    actor,
                    message,
                    details
                FROM control_panel_audit_log
                ORDER BY [timestamp] DESC, id DESC
            """
            rows = cur.execute(fallback_query).fetchall()
            if offset:
                rows = rows[offset:]
        total_row = cur.execute(count_query).fetchone()
    total = int(total_row[0]) if total_row else 0
    for row in rows:
        ts = row[1]
        if hasattr(ts, "isoformat"):
            ts_iso = ts.isoformat()
        else:
            ts_iso = str(ts)
        details_raw = row[4]
        parsed_details: Any = None
        if details_raw not in (None, ""):
            try:
                parsed_details = json.loads(details_raw)
            except Exception:
                parsed_details = details_raw
        entry = {
            "id": f"log-{row[0]}",
            "timestamp": ts_iso,
            "message": row[3],
        }
        if row[2]:
            entry["actor"] = row[2]
        if parsed_details not in (None, ""):
            entry["details"] = parsed_details
        entries.append(entry)
    return entries, total

def get_setting(key) -> Optional[str]:
    k = str(key)
    query = "SELECT [value] FROM bot_settings WHERE [key]=?"
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            row = cur.execute(query, k).fetchone()
            return row[0] if row else None
    except Exception as e:
        print("❌ خطا در get_setting:", e)
        return None

def set_setting(key, value):
    k, v = str(key), str(value)
    query = """
      MERGE bot_settings AS target
      USING (SELECT ? AS [key], ? AS [value]) AS src
        ON target.[key]=src.[key]
      WHEN MATCHED THEN UPDATE SET [value]=src.[value]
      WHEN NOT MATCHED THEN INSERT ([key],[value]) VALUES (src.[key],src.[value]);
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, k, v)
            conn.commit()
    except Exception as e:
        print("❌ خطا در set_setting:", e)


def add_to_blacklist(user_id):
    try:
        uid = int(user_id)
    except:
        return

    insert_with_timestamp = (
        "IF NOT EXISTS (SELECT 1 FROM blacklist WHERE user_id=?) "
        "INSERT INTO blacklist(user_id, created_at) VALUES(?, GETDATE())"
    )
    insert_without_timestamp = (
        "IF NOT EXISTS (SELECT 1 FROM blacklist WHERE user_id=?) "
        "INSERT INTO blacklist(user_id) VALUES(?)"
    )

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute(insert_with_timestamp, uid, uid)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                cur.execute(insert_without_timestamp, uid, uid)
            conn.commit()
    except Exception as e:
        print("❌ خطا در add_to_blacklist:", e)

def remove_from_blacklist(user_id):
    try:
        uid = int(user_id)
    except:
        return
    query = "DELETE FROM blacklist WHERE user_id=?"
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, uid)
            conn.commit()
    except Exception as e:
        print("❌ خطا در remove_from_blacklist:", e)

def is_blacklisted(user_id) -> bool:
    try:
        uid = int(user_id)
    except:
        return False
    query = "SELECT 1 FROM blacklist WHERE user_id=?"
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            return cur.execute(query, uid).fetchone() is not None
    except Exception as e:
        print("❌ خطا در is_blacklisted:", e)
        return False

def _coerce_iso(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        try:
            return value.isoformat()
        except Exception:
            return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.isoformat()
    except Exception:
        return text


def get_blacklist_with_meta() -> List[Dict[str, Any]]:
    query_with_created = (
        "SELECT user_id, created_at FROM blacklist "
        "ORDER BY created_at DESC, user_id DESC"
    )
    query_without_created = "SELECT user_id FROM blacklist ORDER BY user_id DESC"

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            try:
                rows = cur.execute(query_with_created).fetchall()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                rows = cur.execute(query_without_created).fetchall()
                return [
                    {"user_id": int(row[0]), "created_at": None}
                    for row in rows
                ]

            result: List[Dict[str, Any]] = []
            for row in rows:
                user_value = row[0]
                created_value = row[1] if len(row) > 1 else None
                try:
                    user_id = int(user_value)
                except Exception:
                    continue
                result.append(
                    {
                        "user_id": user_id,
                        "created_at": _coerce_iso(created_value),
                    }
                )
            return result
    except Exception as e:
        print("❌ خطا در get_blacklist_with_meta:", e)
        return []


def get_blacklist() -> List[int]:
    return [entry["user_id"] for entry in get_blacklist_with_meta()]

def fetch_logs(user_id: int) -> List[dict]:
    """
    بازگرداندن لاگ پیام‌های کاربر به صورت لیست دیکشنری.
    """
    try:
        uid = int(user_id)
    except:
        return []
    query = """
        SELECT direction, text, timestamp
        FROM message_log
        WHERE user_id = ?
        ORDER BY timestamp ASC
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            rows = cur.execute(query, uid).fetchall()
            logs = []
            for r in rows:
                logs.append({
                    "direction": r[0],
                    "text": r[1],
                    "timestamp": r[2],
                })
            return logs
    except Exception as e:
        print("❌ خطا در fetch_logs:", e)
        return []
