# messages.py
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telethon import events
from telethon.tl.custom import Message

from telegram.client import (
    client,
    get_admin_group_ids,
    get_main_group_id,
    get_new_group_id,
    get_secondary_group_ids,
)

from config.settings import settings
from utils.time_checks import is_within_active_hours
import utils.state as state
from utils.formatting import (
    normalize_code,
    fix_part_number_display,
    escape_markdown,
)
from processor.finder import find_similar_products, find_partial_matches

TZ = ZoneInfo("Asia/Tehran")

# ───────────────────────── Regex patterns ──────────────────────────
FULL_PATTERN    = re.compile(r'^[A-Za-z0-9]{5}[-_/\. ]?[A-Za-z0-9]{5}$')
PARTIAL_PATTERN = re.compile(r'^\d{5}[-_/\. ]?[A-Za-z0-9]{1,4}$')
TOKEN_PATTERN   = re.compile(r'[A-Za-z0-9]{5}[-_/\. ]?[A-Za-z0-9]{1,5}')
CLEAN_CTRL      = re.compile(r'[\u2066-\u2069\u200E-\u200F\u202A-\u202E\u200B]')

# ───────────────────────── Config lists ────────────────────────────
ESCALATION_GROUP_ID = -4718450399  # شناسه گروه Escalation

EXCLUDED = {
    "موبیس", "موب", "mob", "mobis",
    "korea", "china", "chin", "چین", "gen", "کد", "code"
}

# ────────────────────────── Main handler (Groups) ───────────────────────────
def _listen_chat_ids() -> set[int]:
    ids = set()
    main_id = get_main_group_id()
    new_id = get_new_group_id()
    if main_id:
        ids.add(main_id)
    if new_id:
        ids.add(new_id)
    ids.update(get_admin_group_ids())
    ids.update(get_secondary_group_ids())
    return {int(chat_id) for chat_id in ids if chat_id}


def _should_handle_group(event: Message) -> bool:
    try:
        if event.is_private:
            return False
        return int(event.chat_id or 0) in _listen_chat_ids()
    except Exception:
        return False


def _admin_ids_set() -> set[int]:
    return {int(i) for i in get_admin_group_ids()}


@client.on(events.NewMessage(func=_should_handle_group))
async def handle_new_message(event):
    chat_id = int(event.chat_id)
    sender = await event.get_sender()
    user_id = int(sender.id)
    now_dt = datetime.now(TZ)

    # 1) Clean raw text
    raw  = event.raw_text or ""
    text = CLEAN_CTRL.sub("", raw).strip()

    # 2) Blacklist
    if user_id in settings.get("blacklist", []):
        return

    # 3) Per-user counter
    counts = state.user_query_counts.setdefault(
        user_id, {"count": 0, "start": now_dt}
    )

    # 4) Group-level limits
    main_group_id = get_main_group_id()
    admin_ids = _admin_ids_set()

    if chat_id == main_group_id and user_id not in admin_ids:
        if not is_within_active_hours():
            return
        if now_dt - counts["start"] >= timedelta(hours=24):
            counts.update({"count": 0, "start": now_dt})
        if counts["count"] >= settings.get("query_limit", 50):
            return

    # 5) Detect code-like tokens
    raw_tokens = TOKEN_PATTERN.findall(text)
    tokens     = [t for t in raw_tokens if re.search(r'\d', t)]

    # helper to count valid words (letters only, excludes list)
    def valid_word_count(s: str) -> int:
        clean = re.sub(r'[^\w\sآ-ی]', ' ', s)
        words = [w for w in clean.split() if re.fullmatch(r'[آ-یA-Za-z]+', w)]
        return sum(1 for w in words if w.lower() not in EXCLUDED)

    # 6) No tokens → forward immediately if ≥2 valid words
    if not tokens:
        if valid_word_count(text) >= 2:
            await client.send_message(
                ESCALATION_GROUP_ID,
                f"🔔 پیام نامشخص از کاربر `{user_id}`:"
            )
            await client.forward_messages(
                ESCALATION_GROUP_ID,
                event.message,
                chat_id
            )
        return

    # 7) Tokens exist → strip each token then forward if leftover has ≥2 valid words
    parts = re.split(r'\s+', text)
    leftover = ' '.join(p for p in parts if p not in tokens)
    if valid_word_count(leftover) >= 2:
        await client.send_message(
            ESCALATION_GROUP_ID,
            f"🔔 پیام نامشخص از کاربر `{user_id}`:"
        )
        await client.forward_messages(
            ESCALATION_GROUP_ID,
            event.message,
            chat_id
        )

    # 8) Handle look-ups for each token (logic unchanged)
    for token in tokens:
        norm = normalize_code(token)

        # 8a) Partial code
        if PARTIAL_PATTERN.match(token):
            state.total_queries += 1
            suggestions = find_partial_matches(norm)
            if not suggestions:
                continue
            full_code = suggestions[0]["product_code"]
            disp_code = fix_part_number_display(full_code)
            await client.send_message(
                user_id,
                f"🔍 آیا منظور شما {disp_code} است؟!"
            )

            norm_full = normalize_code(full_code)
            prods = find_similar_products(norm_full)
            if prods:
                if user_id not in admin_ids:
                    counts["count"] += 1
                state.sent_messages[f"{user_id}:{norm_full}"] = now_dt
                for p in prods:
                    _send_product(user_id, p, now_dt)

        # 8b) Full code
        elif FULL_PATTERN.match(token):
            state.total_queries += 1
            key = f"{user_id}:{norm}"
            if chat_id == main_group_id and user_id not in admin_ids:
                last = state.sent_messages.get(key)
                if last and now_dt - last < timedelta(minutes=30):
                    continue
            if user_id not in admin_ids:
                counts["count"] += 1
            state.sent_messages[key] = now_dt
            prods = find_similar_products(norm)
            if prods:
                for p in prods:
                    _send_product(user_id, p, now_dt)

# ────────────────────────── New handler (Private Messages) ───────────────────────────
@client.on(events.NewMessage(incoming=True))
async def handle_private_message(event):
    """
    پاسخ‌گویی خودکار در پیام‌های خصوصی کاربران بر اساس همان منطق گروه.
    با کلید settings['dm_enabled'] قابل فعال/غیرفعال‌شدن است.
    """
    if not event.is_private:
        return
    if not settings.get("dm_enabled", True):
        # پاسخ‌گویی PM خاموش است
        return

    sender = await event.get_sender()
    user_id = int(sender.id)
    chat_id = int(event.chat_id)  # در PM برابر با user_id است
    now_dt = datetime.now(TZ)
    admin_ids = _admin_ids_set()

    # Clean & blacklist
    raw  = event.raw_text or ""
    text = CLEAN_CTRL.sub("", raw).strip()
    if user_id in settings.get("blacklist", []):
        return

    # Per-user counter (24h window)
    counts = state.user_query_counts.setdefault(
        user_id, {"count": 0, "start": now_dt}
    )
    if not is_within_active_hours() and user_id not in admin_ids:
        return
    if now_dt - counts["start"] >= timedelta(hours=24):
        counts.update({"count": 0, "start": now_dt})
    if counts["count"] >= settings.get("query_limit", 50) and user_id not in admin_ids:
        return

    # Extract tokens
    raw_tokens = TOKEN_PATTERN.findall(text)
    tokens     = [t for t in raw_tokens if re.search(r'\d', t)]

    def valid_word_count(s: str) -> int:
        clean = re.sub(r'[^\w\sآ-ی]', ' ', s)
        words = [w for w in clean.split() if re.fullmatch(r'[آ-یA-Za-z]+', w)]
        return sum(1 for w in words if w.lower() not in EXCLUDED)

    # Forward unknown PMs with context to گروه Escalation
    if not tokens:
        if valid_word_count(text) >= 2:
            await client.send_message(
                ESCALATION_GROUP_ID,
                f"🔔 پیام خصوصی نامشخص از کاربر `{user_id}`:"
            )
            await client.forward_messages(
                ESCALATION_GROUP_ID,
                event.message,
                chat_id
            )
        return

    parts = re.split(r'\s+', text)
    leftover = ' '.join(p for p in parts if p not in tokens)
    if valid_word_count(leftover) >= 2:
        await client.send_message(
            ESCALATION_GROUP_ID,
            f"🔔 پیام خصوصی نامشخص از کاربر `{user_id}`:"
        )
        await client.forward_messages(
            ESCALATION_GROUP_ID,
            event.message,
            chat_id
        )

    # Lookup logic (partial / full)
    for token in tokens:
        norm = normalize_code(token)

        # Partial code in PM
        if PARTIAL_PATTERN.match(token):
            state.total_queries += 1
            suggestions = find_partial_matches(norm)
            if not suggestions:
                continue

            full_code = suggestions[0]["product_code"]
            disp_code = fix_part_number_display(full_code)
            await client.send_message(
                user_id,
                f"🔍 آیا منظور شما {disp_code} است؟!"
            )

            norm_full = normalize_code(full_code)
            prods = find_similar_products(norm_full)
            if prods:
                if user_id not in admin_ids:
                    counts["count"] += 1
                state.sent_messages[f"{user_id}:{norm_full}"] = now_dt
                for p in prods:
                    _send_product(user_id, p, now_dt)

        # Full code in PM
        elif FULL_PATTERN.match(token):
            state.total_queries += 1
            key = f"{user_id}:{norm}"
            if user_id not in admin_ids:
                last = state.sent_messages.get(key)
                if last and now_dt - last < timedelta(minutes=30):
                    # جلوگیری از ارسال تکراری ظرف ۳۰ دقیقه
                    continue
                counts["count"] += 1

            state.sent_messages[key] = now_dt
            prods = find_similar_products(norm)
            if prods:
                for p in prods:
                    _send_product(user_id, p, now_dt)

# ─────────────────────── Helper to send product ────────────────────
def _send_product(user_id: int, p: dict, now_dt: datetime) -> None:
    code_md  = escape_markdown(fix_part_number_display(p["product_code"]), 1)
    brand_md = escape_markdown(p["brand"], 1)
    name_md  = escape_markdown(p["name"], 1)

    try:
        val = int(float(p.get("price", p.get("فی فروش", 0))))
        price_str = f"{val:,} ریال"
    except:
        price_str = str(p.get("price", p.get("فی فروش", 0)))
    price_md = escape_markdown(price_str, 1)

    iran_txt  = p.get("iran_code") or ""
    iran_line = f"توضیحات: {escape_markdown(iran_txt,1)}\n" if iran_txt else ""

    change_t = datetime.strptime(settings["changeover_hour"], "%H:%M").time()
    footer   = (
        settings["delivery_info"]["before_15"]
        if now_dt.time() < change_t
        else settings["delivery_info"]["after_15"]
    )

    msg = (
        f"کد: `{code_md}`\n"
        f"برند: {brand_md}\n"
        f"نام کالا: {name_md}\n"
        f"قیمت: {price_md}\n"
        f"{iran_line}\n{footer}"
    )
    client.loop.create_task(
        client.send_message(user_id, msg, parse_mode="markdown")
    )
