# -*- coding: utf-8 -*-
import re
import asyncio
import bisect
from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple, Optional

import pandas as pd
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown

from database.connector import fetch_all_inventory_data
from database.connector_bot import get_setting, is_blacklisted

# ================= Consts & Globals =================

# Conversation state
AWAITING_PART_CODE = 1

# Timezone
_TEHRAN = ZoneInfo("Asia/Tehran")

# Persian -> Latin digits (prebuilt for speed)
_P2E = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# Regex (precompiled)
_CODE_REGEX = re.compile(r"\b[A-Za-z0-9]{5}(?:[-_/\. ]+)?[A-Za-z0-9]{5}\b")      # plain 5+5
_CODE_WITH_SUFFIX = re.compile(
    r"\b([A-Za-z0-9]{5})(?:[-_/\. ]+)?([A-Za-z0-9]{5})([A-Za-z]+)\b"
)  # 5+5 + letters suffix (e.g., 12345-12345MWJ)
_PARTIAL_REGEX = re.compile(r"\b([A-Za-z0-9]{5})(?:[-_/\. ]+)?([A-Za-z0-9]{2,4})\b")

# Inventory cache/index
_cached_inventory_data: List[dict] = []
_inventory_index: Dict[str, List[dict]] = {}
_sorted_keys: List[str] = []


# ================= Small helpers =================

def _fmt_disp(norm: str) -> str:
    """Safe code display: 12345-12345 from any normalized key."""
    clean = re.sub(r"[^A-Za-z0-9]", "", norm or "")
    return f"{clean[:5]}-{clean[5:]}" if len(clean) > 5 else clean


def _normalize(code: str) -> str:
    """Normalize part code to uppercase alnum without separators / bidi marks."""
    cleaned = re.sub(r"[\u202d\u202c\u2068\u2069\u200e\u200f\u200b]", "", code or "")
    return re.sub(r"[-_/\. \s]", "", cleaned).upper()


def _normalize_input_text(raw: str) -> str:
    """For user input: normalize digits, bidi marks, dash-like chars, NBSP."""
    s = (raw or "").strip()
    s = s.translate(_P2E)
    s = re.sub(r"[\u200E\u200F\u202A-\u202E\u2066-\u2069\u200B]", "", s)
    s = re.sub(r"[‐-‒–—⁃−﹘﹣]", "-", s)  # unify dashes to '-'
    return s.replace("\u00A0", " ")


def _parse_time_setting(key: str, default_hhmm: str) -> time:
    """Parse HH:MM from settings with fallback."""
    val = (get_setting(key) or default_hhmm).strip()
    try:
        return datetime.strptime(val, "%H:%M").time()
    except Exception:
        return datetime.strptime(default_hhmm, "%H:%M").time()


def _extract_brand_and_part(code: str) -> Tuple[Optional[str], Optional[str]]:
    """Returns (part, brand) parsed from '<PART>_<BRAND>' if present."""
    if pd.isna(code):
        return None, None
    parts = str(code).split("_")
    part = parts[0] if parts else None
    brand = parts[1] if len(parts) > 1 else None
    return part, brand


def _replace_partial(base: str, var: str) -> str:
    """
    For a variant chunk 'var' (len<5 means tail override), reconstruct full last_base.
    """
    try:
        pfx, sfx = base.rsplit("-", 1)
    except ValueError:
        return base

    if len(var) < 5:
        cut_len = len(var)
        trimmed = sfx[:-cut_len] if len(sfx) >= cut_len else ""
        return f"{pfx}-{trimmed}{var}"  # e.g., 12345-67890 + 12  -> 12345-67812

    if len(var) >= 5:
        return f"{pfx}-{var}"

    return base


def _process_row(row: dict) -> List[dict]:
    """
    From a DB row, extract one or more normalized searchable records.

    - Source field priority: "کد کالا"
    - Split variants by '/', reconstruct (e.g. 12345-67890/12 -> 12345-67812)
    - Deduplicate per-row to avoid identical records.
    """
    recs: List[dict] = []
    seen_codes: set = set()

    code = row.get("کد کالا", "")
    part, brand = _extract_brand_and_part(code)
    if not part:
        part = code

    parts = str(part).split("/")
    last_base = None
    for pc in parts:
        pc = pc.strip()
        if "-" in pc and len(pc.split("-")[-1]) >= 5:
            last_base = pc
        elif last_base:
            last_base = _replace_partial(last_base, pc)

        if last_base:
            norm = _normalize(last_base)
            if norm in seen_codes:
                continue
            seen_codes.add(norm)
            recs.append({
                "شماره قطعه": last_base,
                "برند": brand or row.get("نام تامین کننده", "نامشخص"),
                "نام کالا": row.get("نام کالا", "نامشخص"),
                "فی فروش": row.get("فی فروش", 0),
                "Iran Code": row.get("Iran Code")
            })
    return recs


def _find_products(key_norm: str) -> List[dict]:
    """
    O(1) exact lookup, otherwise prefix-range scan (>=10 chars).
    Partial (7..9) handled by caller.
    """
    exact = _inventory_index.get(key_norm, [])
    if exact:
        return exact

    if len(key_norm) >= 10:
        prefix = key_norm[:10]
        lo = bisect.bisect_left(_sorted_keys, prefix)
        hi = bisect.bisect_right(_sorted_keys, prefix + "\uffff")
        candidates: List[dict] = []
        for k in _sorted_keys[lo:hi]:
            candidates.extend(_inventory_index[k])
        if candidates:
            return sorted(candidates, key=lambda it: _normalize(it["شماره قطعه"]))
    return []


# ================= Settings snapshot & policy =================

class _Settings:
    def __init__(self) -> None:
        # working hours
        self.wk_start = _parse_time_setting("working_start", "08:00")
        self.wk_end = _parse_time_setting("working_end", "18:00")
        self.th_start = _parse_time_setting("thursday_start", "08:00")
        self.th_end = _parse_time_setting("thursday_end", "12:30")
        self.disable_friday = (get_setting("disable_friday") or "true").lower() == "true"

        # quota (0 = unlimited). DB-نمی‌سازد؛ در حافظهٔ کاربر تلگرام نگه می‌داریم.
        try:
            self.query_limit = int(get_setting("query_limit") or "0")
        except Exception:
            self.query_limit = 0

        # delivery changeover
        hhmm = (get_setting("changeover_hour") or "15:00").strip()
        try:
            self.changeover = datetime.strptime(hhmm, "%H:%M").time()
        except Exception:
            self.changeover = time(15, 0)

        # delivery text (support both key families)
        self.delivery_before = (
            get_setting("delivery_before")
            or get_setting("delivery_info_before")
            or "🚚 تحویل کالا هر روز ساعت 16 و پنج‌شنبه‌ها 12:30"
        )
        self.delivery_after = (
            get_setting("delivery_after")
            or get_setting("delivery_info_after")
            or "🛵 ارسال مستقیم از انبار (حدود 60 دقیقه)"
        )


def _within_working_hours(now: datetime, st: _Settings) -> bool:
    wd, tnow = now.weekday(), now.time()
    if wd == 4:  # Friday (Python: Monday=0 ... Sunday=6)
        return (not st.disable_friday) and (st.wk_start <= tnow < st.wk_end)
    if wd == 3:  # Thursday
        return st.th_start <= tnow < st.th_end
    # Saturday-Wednesday
    return st.wk_start <= tnow < st.wk_end


def _delivery_line_for(now: datetime, st: _Settings) -> str:
    return st.delivery_before if now.time() < st.changeover else st.delivery_after


def _format_price(value) -> str:
    try:
        pv = int(float(value))
        return f"{pv:,} ریال"
    except Exception:
        return str(value or "")


def _format_item_reply_md(item: dict, delivery_line: str) -> str:
    # Protect against None/NaN
    raw_code = str(item.get("شماره قطعه", "") or "")
    brand = str(item.get("برند", "") or "—")
    name = str(item.get("نام کالا", "") or "")
    price_text = _format_price(item.get("فی فروش", 0))
    iran_txt = str(item.get("Iran Code", "") or "")

    # Escape once
    code_md = escape_markdown("\u200E" + raw_code + "\u200E", version=1)
    brand_md = escape_markdown(brand, version=1)
    name_md = escape_markdown(name, version=1)
    price_md = escape_markdown(price_text, version=1)
    delivery_md = escape_markdown(delivery_line, version=1)
    iran_line = f"توضیحات: {escape_markdown(iran_txt, version=1)}" if iran_txt else ""

    body = (
        f"*کد:* `{code_md}`\n"
        f"*برند:* {brand_md}\n"
        f"نام کالا: {name_md}\n"
        f"*قیمت:* {price_md}\n"
    )
    if iran_line:
        body += f"{iran_line}\n"
    body += delivery_md
    return body


def _check_and_inc_user_quota(update: Update, context: ContextTypes.DEFAULT_TYPE, st: _Settings) -> Optional[str]:
    """
    Return error text if quota exceeded; otherwise increment and return None.
    NOTE: در این نسخه DB درگیر نیست؛ به ازای هر کاربر در user_data نگه می‌داریم.
    """
    if st.query_limit <= 0:
        return None  # unlimited

    today = datetime.now(_TEHRAN).date().isoformat()
    ud = context.user_data
    if ud.get("q_date") != today:
        ud["q_date"] = today
        ud["q_count"] = 0

    if ud["q_count"] >= st.query_limit:
        return f"⛔️ شما به محدودیت استعلام روزانه ({st.query_limit}) رسیده‌اید."

    ud["q_count"] += 1
    return None


# ================= Cache refresh =================

async def refresh_inventory_cache_once():
    """
    Single-run refresh; called at startup and by JobQueue every 20 minutes.
    Keeps O(1)+prefix index structures in memory.
    """
    global _cached_inventory_data, _inventory_index, _sorted_keys
    now_str = datetime.now(_TEHRAN).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] Starting inventory cache refresh from database...")

    try:
        raw = fetch_all_inventory_data()
        if not raw:
            print(f"[{now_str}] WARNING: No data received from database.")
            return

        # Flatten & dedup rows into searchable records
        records = [rec for row in raw for rec in _process_row(row)]
        _cached_inventory_data = records

        # Build fast exact + sorted prefix scan
        idx: Dict[str, List[dict]] = {}
        for rec in records:
            key = _normalize(rec.get("شماره قطعه", ""))
            idx.setdefault(key, []).append(rec)

        _inventory_index = idx
        _sorted_keys = sorted(idx.keys())

        print(f"[{now_str}] OK: Inventory cache refreshed: {len(raw)} rows -> {len(records)} codes.")
    except Exception as e:
        print(f"[{now_str}] ERROR: Failed to refresh cache: {e}")


async def update_inventory_cache():
    """Legacy background loop (not used when JobQueue exists)."""
    while True:
        await refresh_inventory_cache_once()
        await asyncio.sleep(20 * 60)


# ================= Telegram Handlers =================

async def handle_inventory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # quick guards
    if get_setting("enabled") != "true":
        await update.message.reply_text("⛔️ ربات غیرفعال است. لطفاً بعداً مراجعه کنید.")
        return ConversationHandler.END

    uid = update.effective_user.id
    if is_blacklisted(uid):
        await update.message.reply_text("⛔️ شما در لیست سیاه هستید.")
        return ConversationHandler.END

    st = _Settings()
    now = datetime.now(_TEHRAN)
    if not _within_working_hours(now, st):
        await update.message.reply_text(
            f"⏰ ساعات کاری ربات:\n"
            f"  • شنبه تا چهارشنبه: {st.wk_start.strftime('%H:%M')} تا {st.wk_end.strftime('%H:%M')}\n"
            f"  • پنج‌شنبه: {st.th_start.strftime('%H:%M')} تا {st.th_end.strftime('%H:%M')}\n\n"
            "لطفاً در این بازه‌ها برای استعلام تلاش کنید."
        )
        return ConversationHandler.END

    sent = await update.message.reply_text("🔍 لطفاً کد قطعه را وارد کنید:")
    context.user_data["last_prompt_id"] = sent.message_id
    return AWAITING_PART_CODE


async def handle_inventory_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # quick guards
    if get_setting("enabled") != "true":
        await update.message.reply_text("⛔️ ربات غیرفعال است. لطفاً بعداً مراجعه کنید.")
        return ConversationHandler.END

    uid = update.effective_user.id
    if is_blacklisted(uid):
        await update.message.reply_text("⛔️ شما در لیست سیاه هستید.")
        return ConversationHandler.END

    st = _Settings()
    now = datetime.now(_TEHRAN)
    if not _within_working_hours(now, st):
        await update.message.reply_text(
            f"⏰ ساعات کاری ربات:\n"
            f"  • شنبه تا چهارشنبه: {st.wk_start.strftime('%H:%M')} تا {st.wk_end.strftime('%H:%M')}\n"
            f"  • پنج‌شنبه: {st.th_start.strftime('%H:%M')} تا {st.th_end.strftime('%H:%M')}\n\n"
            "لطفاً در این بازه‌ها برای استعلام تلاش کنید."
        )
        return ConversationHandler.END

    # daily quota (in-memory, no DB)
    q_err = _check_and_inc_user_quota(update, context, st)
    if q_err:
        await update.message.reply_text(q_err)
        return AWAITING_PART_CODE

    # Clean input
    raw = _normalize_input_text(update.message.text)

    # Extract tokens (بدون فیلترِ هم‌پوشانی partialها، طبق خواستهٔ شما)
    full_plain_its = list(_CODE_REGEX.finditer(raw))
    full_suffix_its = list(_CODE_WITH_SUFFIX.finditer(raw))
    part_its = list(_PARTIAL_REGEX.finditer(raw))

    # Ordered tokens with type info
    tokens: List[Dict] = []
    for m in full_plain_its:
        disp = m.group(0)
        tokens.append({"norm": _normalize(disp), "display": disp, "is_full": True})
    for m in full_suffix_its:
        g1, g2 = m.group(1), m.group(2)
        disp = f"{g1}-{g2}"
        tokens.append({"norm": _normalize(g1 + g2), "display": disp, "is_full": True})
    for m in part_its:
        g1, g2 = m.group(1), m.group(2)
        disp = f"{g1}-{g2}"
        tokens.append({"norm": _normalize(g1 + g2), "display": disp, "is_full": False})

    # Dedupe by (norm,is_full)  (ممکن است خروجی full و partial برای یک کد، هر دو بیایند)
    seen = set()
    dedup_tokens = []
    for t in tokens:
        key = (t["norm"], t["is_full"])
        if key not in seen:
            seen.add(key)
            dedup_tokens.append(t)

    if not dedup_tokens:
        await update.message.reply_text("❗️ لطفاً کد صحیح وارد کنید (دو بخش ۵ کاراکتری).")
        return AWAITING_PART_CODE

    # Collect invalid leftovers (صرفاً برای راهنمایی)
    leftover = raw
    for m in full_plain_its:
        leftover = leftover.replace(m.group(0), " ")
    for m in full_suffix_its:
        leftover = leftover.replace(m.group(0), " ")
    for m in part_its:
        leftover = leftover.replace(m.group(0), " ")
    invalid_parts = [tok for tok in re.split(r"\s+", leftover) if tok]

    # Process tokens
    delivery = _delivery_line_for(now, st)

    for t in dedup_tokens:
        norm, is_full = t["norm"], t["is_full"]

        if is_full and len(norm) >= 10:
            products = _find_products(norm)
            if not products:
                await update.message.reply_text(
                    f"\u200F⚠️ \u202A`{_fmt_disp(norm)}`\u202C متأسفانه موجود نمی‌باشد.\u200F",
                    parse_mode="Markdown"
                )
                continue

            for item in products:
                text_md = _format_item_reply_md(item, delivery)
                await update.message.reply_text(text_md, parse_mode="Markdown")
            continue

        if (not is_full) and 7 <= len(norm) < 10:
            # Prefix-range scan
            lo = bisect.bisect_left(_sorted_keys, norm)
            hi = bisect.bisect_right(_sorted_keys, norm + "\uffff")
            candidates = [rec for k in _sorted_keys[lo:hi] for rec in _inventory_index.get(k, [])]

            if candidates:
                suggestion = sorted(candidates, key=lambda it: _normalize(it["شماره قطعه"]))[0]
                text_md = _format_item_reply_md(suggestion, delivery)
                await update.message.reply_text(text_md, parse_mode="Markdown")
                continue

            await update.message.reply_text(
                f"\u200F⚠️ \u202A`{_fmt_disp(norm)}`\u202C متأسفانه موجود نمی‌باشد.\u200F",
                parse_mode="Markdown"
            )
            continue

        # Fallback invalid/too short
        await update.message.reply_text(
            f"\u200F⚠️ \u202A`{_fmt_disp(norm)}`\u202C متأسفانه موجود نمی‌باشد.\u200F",
            parse_mode="Markdown"
        )

    # Report invalid tokens (if any) once
    if invalid_parts:
        bad = ", ".join(f"`{escape_markdown(x, version=1)}`" for x in invalid_parts)
        await update.message.reply_text(
            "⛔️ فرمت یک یا چند کد نامعتبر است:\n"
            f"{bad}\n\n"
            "لطفاً فقط یکی از فرمت‌های زیر را وارد کنید:\n"
            "- `12345-12345`\n"
            "- `12345_12345`\n"
            "- `1234512345`\n"
            "- `12345/12345`\n"
            "- `12345 12345`\n"
            "- `12345.12345`\n\n",
            parse_mode="Markdown"
        )

    # Keep only one prompt message alive (delete previous prompt)
    try:
        prev_id = context.user_data.get("last_prompt_id")
        if prev_id:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=prev_id
            )
    except Exception:
        pass

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 بازگشت به منوی اصلی", callback_data="main_menu")]
    ])
    sent = await update.message.reply_text(
        "🔍 برای استعلام بعدی، کد را وارد کنید یا /cancel.",
        reply_markup=keyboard
    )
    context.user_data["last_prompt_id"] = sent.message_id
    return AWAITING_PART_CODE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return ConversationHandler.END
