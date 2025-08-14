import re
import asyncio
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown
import bisect

from database.connector import fetch_all_inventory_data
from database.connector_bot import get_setting, is_blacklisted

# Conversation state
AWAITING_PART_CODE = 1

# Cache & fast index
_cached_inventory_data: list[dict] = []
_inventory_index: dict[str, list[dict]] = {}
_sorted_keys: list[str] = []

# Patterns
_PART_PATTERN = re.compile(r'^[A-Za-z0-9]{5}(?:[-_/\. ]+)?[A-Za-z0-9]{5}$')
_CODE_REGEX   = re.compile(r'\b[A-Za-z0-9]{5}(?:[-_/\. ]+)?[A-Za-z0-9]{5}\b')  # plain 5+5
# full code (5+5) + optional color suffix letters (e.g. 12345-12345MWJ)
_CODE_WITH_SUFFIX = re.compile(r'\b([A-Za-z0-9]{5})(?:[-_/\. ]+)?([A-Za-z0-9]{5})([A-Za-z]+)\b')
# partial code: 5 + (2..4) -> total 7..9 chars
_PARTIAL_REGEX = re.compile(r'\b([A-Za-z0-9]{5})(?:[-_/\. ]+)?([A-Za-z0-9]{2,4})\b')

# TZ
_TEHRAN = ZoneInfo("Asia/Tehran")

# ---- FIX: safe display formatter for codes ----
def _fmt_disp(norm: str) -> str:
    clean = re.sub(r'[^A-Za-z0-9]', '', norm or '')
    return f"{clean[:5]}-{clean[5:]}"


def _parse_time_setting(key: str, default: str) -> time:
    val = get_setting(key) or default
    try:
        return datetime.strptime(val, "%H:%M").time()
    except:
        return datetime.strptime(default, "%H:%M").time()


async def refresh_inventory_cache_once():
    """Single-run refresh; called at startup and every 20 minutes by the scheduler."""
    global _cached_inventory_data, _inventory_index, _sorted_keys
    now_str = datetime.now(_TEHRAN).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now_str}] Starting inventory cache refresh from database...")

    try:
        raw = fetch_all_inventory_data()
        if not raw:
            print(f"[{now_str}] WARNING: No data received from database.")
            return

        raw_count = len(raw)  # raw DB rows

        # Simplify rows into normalized 'records'
        records = [rec for row in raw for rec in _process_row(row)]
        processed_count = len(records)  # final searchable codes
        _cached_inventory_data = records

        # Build fast index
        idx: dict[str, list[dict]] = {}
        for rec in records:
            key = _normalize(rec.get("شماره قطعه", ""))
            idx.setdefault(key, []).append(rec)
        _inventory_index = idx
        _sorted_keys = sorted(idx.keys())

        print(f"[{now_str}] OK: Inventory cache refreshed: "
              f"{raw_count} raw rows -> {processed_count} searchable codes.")
    except Exception as e:
        print(f"[{now_str}] ERROR: Failed to refresh cache: {e}")


async def update_inventory_cache():
    """Legacy background loop (if you ever need it outside JobQueue)."""
    while True:
        await refresh_inventory_cache_once()
        await asyncio.sleep(20 * 60)


def _extract_brand_and_part(code: str):
    """Returns (part, brand) parsed from '<PART>_<BRAND>' if present."""
    if pd.isna(code):
        return None, None
    parts = str(code).split("_")
    part = parts[0] if parts else None
    brand = parts[1] if len(parts) > 1 else None
    return part, brand


def _replace_partial(base: str, var: str):
    """
    Rewrite the tail of base with the shorter variant 'var'.
    """
    try:
        pfx, sfx = base.rsplit("-", 1)
    except ValueError:
        return base

    if len(var) < 5:
        cut_len = len(var)
        trimmed = sfx[:-cut_len] if len(sfx) >= cut_len else ""
        return f"{pfx}-{trimmed}{var}"

    if len(var) >= 5:
        return f"{pfx}-{var}"

    return base


def _process_row(row: dict) -> list[dict]:
    """
    Extract & normalize rows:
      - Source field priority: "کد کالا"
      - Split variants by '/', reconstruct with _replace_partial
    """
    recs: list[dict] = []
    code = row.get("کد کالا", "")
    part, brand = _extract_brand_and_part(code)
    if not part:
        part = code

    parts = str(part).split('/')
    last_base = None
    for pc in parts:
        pc = pc.strip()
        if '-' in pc and len(pc.split('-')[-1]) >= 5:
            last_base = pc
        elif last_base:
            last_base = _replace_partial(last_base, pc)
        if last_base:
            recs.append({
                "شماره قطعه": last_base,
                "برند": brand or row.get("نام تامین کننده", "نامشخص"),
                "نام کالا": row.get("نام کالا", "نامشخص"),
                "فی فروش": row.get("فی فروش", 0),
                "Iran Code": row.get("Iran Code")
            })
    return recs


def _normalize(code: str) -> str:
    cleaned = re.sub(r'[\u202d\u202c\u2068\u2069\u200e\u200f\u200b]', '', code or '')
    return re.sub(r'[-_/\.\s]', '', cleaned).upper()


def _find_products(key: str) -> list[dict]:
    """
    Exact O(1) lookup first.
    If not found and key length >= 10 (full code), search by 10-char prefix range.
    For partial (7..9), suggestions are handled in the handler.
    """
    exact = _inventory_index.get(key, [])
    if exact:
        return exact

    if len(key) >= 10:
        prefix = key[:10]
        lo = bisect.bisect_left(_sorted_keys, prefix)
        hi = bisect.bisect_right(_sorted_keys, prefix + "\uffff")
        candidates: list[dict] = []
        for k in _sorted_keys[lo:hi]:
            candidates.extend(_inventory_index[k])
        if candidates:
            return sorted(candidates, key=lambda it: _normalize(it["شماره قطعه"]))
    return []


# ================= Telegram Handlers =================

async def handle_inventory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if get_setting("enabled") != "true":
        await update.message.reply_text("⛔️ ربات غیرفعال است. لطفاً بعداً مراجعه کنید.")
        return ConversationHandler.END

    uid = update.effective_user.id
    if is_blacklisted(uid):
        await update.message.reply_text("⛔️ شما در لیست سیاه هستید.")
        return ConversationHandler.END

    wk_start = _parse_time_setting("working_start", "08:00")
    wk_end   = _parse_time_setting("working_end",   "18:00")
    th_start = _parse_time_setting("thursday_start","08:00")
    th_end   = _parse_time_setting("thursday_end",  "12:30")
    now      = datetime.now(_TEHRAN)
    wd       = now.weekday()
    now_time = now.time()

    disable_friday = (get_setting("disable_friday") or "true").lower() == "true"
    if ((wd == 4 and (disable_friday or not (wk_start <= now_time < wk_end))) or
        (wd == 3 and not (th_start <= now_time < th_end)) or
        (wd not in (3,4) and not (wk_start <= now_time < wk_end))):
        await update.message.reply_text(
            f"⏰ ساعات کاری ربات:\n"
            f"  • شنبه تا چهارشنبه: {wk_start.strftime('%H:%M')} تا {wk_end.strftime('%H:%M')}\n"
            f"  • پنج‌شنبه: {th_start.strftime('%H:%M')} تا {th_end.strftime('%H:%M')}\n\n"
            "لطفاً در این بازه‌ها برای استعلام تلاش کنید."
        )
        return ConversationHandler.END

    sent = await update.message.reply_text("🔍 لطفاً کد قطعه را وارد کنید:")
    context.user_data["last_prompt_id"] = sent.message_id
    return AWAITING_PART_CODE


async def handle_inventory_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if get_setting("enabled") != "true":
        await update.message.reply_text("⛔️ ربات غیرفعال است. لطفاً بعداً مراجعه کنید.")
        return ConversationHandler.END

    uid = update.effective_user.id
    if is_blacklisted(uid):
        await update.message.reply_text("⛔️ شما در لیست سیاه هستید.")
        return ConversationHandler.END

    wk_start = _parse_time_setting("working_start", "08:00")
    wk_end   = _parse_time_setting("working_end",   "18:00")
    th_start = _parse_time_setting("thursday_start","08:00")
    th_end   = _parse_time_setting("thursday_end",  "12:30")
    now      = datetime.now(_TEHRAN)
    wd, now_time = now.weekday(), now.time()

    disable_friday = (get_setting("disable_friday") or "true").lower() == "true"
    if ((wd == 4 and (disable_friday or not (wk_start <= now_time < wk_end))) or
        (wd == 3 and not (th_start <= now_time < th_end)) or
        (wd not in (3,4) and not (wk_start <= now_time < wk_end))):
        await update.message.reply_text(
            f"⏰ ساعات کاری ربات:\n"
            f"  • شنبه تا چهارشنبه: {wk_start.strftime('%H:%M')} تا {wk_end.strftime('%H:%M')}\n"
            f"  • پنج‌شنبه: {th_start.strftime('%H:%M')} تا {th_end.strftime('%H:%M')}\n\n"
            "لطفاً در این بازه‌ها برای استعلام تلاش کنید."
        )
        return ConversationHandler.END

    # Clean input (digits + bidi cleanup)
    raw = update.message.text.strip()
    raw = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    raw = re.sub(r'[\u200E\u200F\u202A-\u202E\u2066-\u2069\u200B]', '', raw)
    # ---- FIX: normalize dash-like chars & NBSP ----
    raw = re.sub(r'[‐-‒–—⁃−﹘﹣]', '-', raw)
    raw = raw.replace('\u00A0', ' ')

    # ===== Extract tokens =====
    full_plain_its  = list(_CODE_REGEX.finditer(raw))
    full_suffix_its = list(_CODE_WITH_SUFFIX.finditer(raw))
    part_its        = list(_PARTIAL_REGEX.finditer(raw))

    # Avoid overlapping: remove partials inside full matches
    full_spans = [(m.start(), m.end()) for m in full_plain_its] + [(m.start(), m.end()) for m in full_suffix_its]
    def _in_full_spans(m):
        s, e = m.start(), m.end()
        return any(s >= fs and e <= fe for (fs, fe) in full_spans)
    part_its = [m for m in part_its if not _in_full_spans(m)]

    # Build ordered tokens with type info
    tokens = []
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

    # Dedupe
    seen = set(); dedup_tokens = []
    for t in tokens:
        key = (t["norm"], t["is_full"])
        if key not in seen:
            seen.add(key); dedup_tokens.append(t)

    if not dedup_tokens:
        await update.message.reply_text("❗️ لطفاً کد صحیح وارد کنید (دو بخش ۵ کاراکتری).")
        return AWAITING_PART_CODE

    # Collect invalid leftovers (for the "invalid_parts" message)
    leftover = raw
    for m in full_plain_its:  leftover = leftover.replace(m.group(0), " ")
    for m in full_suffix_its: leftover = leftover.replace(m.group(0), " ")
    for m in part_its:        leftover = leftover.replace(m.group(0), " ")
    invalid_parts = [tok for tok in re.split(r'\s+', leftover) if tok]

    # ===== Process tokens =====
    for t in dedup_tokens:
        norm, disp, is_full = t["norm"], t["display"], t["is_full"]

        if is_full and len(norm) >= 10:
            products = _find_products(norm)

            if not products:
                await update.message.reply_text(
                    f"\u200F⚠️ \u202A`{_fmt_disp(norm)}`\u202C متأسفانه موجود نمی‌باشد.\u200F",
                    parse_mode="Markdown"
                )
                continue

            changeover = time(15, 0)
            before_msg = get_setting("delivery_before") or "🚚 تحویل کالا هر روز ساعت 16 و پنج‌شنبه‌ها 12:30"
            after_msg  = get_setting("delivery_after")  or "🛵 ارسال مستقیم از انبار (حدود 60 دقیقه)"
            now_time   = datetime.now(_TEHRAN).time()
            delivery   = before_msg if now_time < changeover else after_msg

            for item in products:
                raw_code = item["شماره قطعه"]
                code_md  = escape_markdown("\u200E"+raw_code+"\u200E", version=1)
                brand_md = escape_markdown(item["برند"], version=1)
                name_md  = escape_markdown(item["نام کالا"], version=1)
                try:
                    pv      = int(float(item.get("فی فروش", 0)))
                    price_md = escape_markdown(f"{pv:,} ریال", version=1)
                except:
                    price_md = escape_markdown(str(item.get("فی فروش",0)), version=1)
                iran_txt  = item.get("Iran Code") or ""
                iran_line = f"توضیحات: {escape_markdown(iran_txt, version=1)}" if iran_txt else ""
                delivery_md = escape_markdown(delivery, version=1)
                await update.message.reply_text(
                    f"*کد:* `{code_md}`\n"
                    f"*برند:* {brand_md}\n"
                    f"نام کالا: {name_md}\n"
                    f"*قیمت:* {price_md}\n"
                    + (f"{iran_line}\n" if iran_line else "")
                    + f"{delivery_md}",
                    parse_mode="Markdown"
                )
            continue

        if not is_full and 7 <= len(norm) < 10:
            lo = bisect.bisect_left(_sorted_keys, norm)
            hi = bisect.bisect_right(_sorted_keys, norm + "\uffff")
            candidates = [rec for k in _sorted_keys[lo:hi] for rec in _inventory_index.get(k, [])]

            if candidates:
                suggestion = sorted(candidates, key=lambda it: _normalize(it["شماره قطعه"]))[0]
                await update.message.reply_text("🔍 آیا منظور شما این کالا است؟")

                raw_code   = suggestion["شماره قطعه"]
                code_md    = escape_markdown("\u200E"+raw_code+"\u200E", version=1)
                brand_md   = escape_markdown(suggestion["برند"], version=1)
                name_md    = escape_markdown(suggestion["نام کالا"], version=1)
                try:
                    pv       = int(float(suggestion.get("فی فروش", 0)))
                    price_md = escape_markdown(f"{pv:,} ریال", version=1)
                except:
                    price_md = escape_markdown(str(suggestion.get("فی فروش", 0)), version=1)

                iran_txt  = suggestion.get("Iran Code") or f"با کد{raw_code} موجود است."
                iran_line = f"توضیحات: {escape_markdown(iran_txt, version=1)}"

                await update.message.reply_text(
                    f"*کد:* `{code_md}`\n"
                    f"*برند:* {brand_md}\n"
                    f"نام کالا: {name_md}\n"
                    f"*قیمت:* {price_md}\n"
                    f"{iran_line}",
                    parse_mode="Markdown"
                )
                continue

            # No suggestion (partial)  ---- FIX: use user-facing disp, not undefined var
            await update.message.reply_text(f"⚠️ {disp} متأسفانه موجود نمی‌باشد.‏")
            continue

        # Fallback too short/invalid
        await update.message.reply_text(
            f"\u200F⚠️ \u202A`{_fmt_disp(norm)}`\u202C متأسفانه موجود نمی‌باشد.\u200F",
            parse_mode="Markdown"
        )

    # Report invalid tokens (if any)
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

    # === Ensure only ONE prompt message exists (delete old prompt, send new) ===
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
