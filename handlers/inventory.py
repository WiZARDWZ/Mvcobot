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

# حالت انتظار دریافت کد قطعه
AWAITING_PART_CODE = 1

# کش کامل داده‌ها و ایندکس برای جستجوی سریع O(1)
_cached_inventory_data: list[dict] = []
_inventory_index: dict[str, list[dict]] = {}
_sorted_keys: list[str] = []

# الگوها
_PART_PATTERN = re.compile(r'^[A-Za-z0-9]{5}(?:[-_/\. ]+)?[A-Za-z0-9]{5}$')
_CODE_REGEX   = re.compile(r'\b[A-Za-z0-9]{5}(?:[-_/\. ]+)?[A-Za-z0-9]{5}\b')

# منطقهٔ زمانی تهران
_TEHRAN = ZoneInfo("Asia/Tehran")


def _parse_time_setting(key: str, default: str) -> time:
    val = get_setting(key) or default
    try:
        return datetime.strptime(val, "%H:%M").time()
    except:
        return datetime.strptime(default, "%H:%M").time()


async def update_inventory_cache():
    global _cached_inventory_data, _inventory_index, _sorted_keys
    while True:
        try:
            raw = fetch_all_inventory_data()
            if raw:
                records = [rec for row in raw for rec in _process_row(row)]
                _cached_inventory_data = records

                idx: dict[str, list[dict]] = {}
                for rec in records:
                    key = _normalize(rec.get("شماره قطعه", ""))
                    idx.setdefault(key, []).append(rec)
                _inventory_index = idx
                _sorted_keys = sorted(idx.keys())

                now = datetime.now(_TEHRAN)
                print(f"[{now}] Cache refreshed: {len(records)} records")
            else:
                print("⚠️ خطا در دریافت داده از دیتابیس.")
        except Exception as e:
            print("❌ خطا در به‌روزرسانی کش:", e)
        await asyncio.sleep(20 * 60)


def _extract_brand_and_part(code: str):
    if pd.isna(code):
        return None, None
    parts = str(code).split("_")
    return parts[0], parts[1] if len(parts) > 1 else None


def _replace_partial(base: str, var: str):
    """بازنویسی بخش انتهایی کد مادر با قطعهٔ کوتاه‌تر

    اگر *var* کمتر از ۵ کاراکتر باشد (فارغ از اینکه صرفاً رقم باشد یا ترکیب
    حروف/رقم)، به همان اندازه از انتهای بخش ۵ رقمیِ کد مادر جایگزین می‌شود.

    مثال:
        base = "22224-3c100"
        _replace_partial(base, "AA0") ➜ "22224-3cAA0"
        _replace_partial(base, "AB0") ➜ "22224-3cAB0"
    """
    try:
        pfx, sfx = base.rsplit("-", 1)
    except ValueError:  # اگر خط تیره پیدا نشد
        return base

    if len(var) < 5:  # جای‌گذاری روی همان تعداد کاراکتر انتهایی
        cut_len = len(var)
        trimmed = sfx[:-cut_len] if len(sfx) >= cut_len else ""
        return f"{pfx}-{trimmed}{var}"

    if len(var) >= 5:  # واریانت با طول ۵ یا بیشتر کل پسوند را می‌پوشاند
        return f"{pfx}-{var}"

    return base  # در غیر این صورت تغییری نده


def _process_row(row: dict) -> list[dict]:
    recs = []
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
    exact = _inventory_index.get(key, [])
    if exact:
        return exact
    if len(key) >= 10:
        prefix = key[:10]
        lo = bisect.bisect_left(_sorted_keys, prefix)
        hi = bisect.bisect_right(_sorted_keys, prefix + "\uffff")
        candidates = []
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

    if (wd == 4 or
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

    if (wd == 4 or
        (wd == 3 and not (th_start <= now_time < th_end)) or
        (wd not in (3,4) and not (wk_start <= now_time < wk_end))):
        await update.message.reply_text(
            f"⏰ ساعات کاری ربات:\n"
            f"  • شنبه تا چهارشنبه: {wk_start.strftime('%H:%M')} تا {wk_end.strftime('%H:%M')}\n"
            f"  • پنج‌شنبه: {th_start.strftime('%H:%M')} تا {th_end.strftime('%H:%M')}\n\n"
            "لطفاً در این بازه‌ها برای استعلام تلاش کنید."
        )
        return ConversationHandler.END

    # پاکسازی اولیه
    raw = update.message.text.strip()
    raw = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    raw = re.sub(r'[\u200E\u200F\u202A-\u202E\u2066-\u2069\u200B]', '', raw)

    valid_codes   = _CODE_REGEX.findall(raw)
    leftover      = _CODE_REGEX.sub(' ', raw)
    invalid_parts = [tok for tok in re.split(r'\s+', leftover) if tok]

    for code_str in valid_codes:
        norm     = _normalize(code_str)
        products = _find_products(norm)

        if not products:
            # پیشنهاد برای کد ناقص (طول بین 7 تا <10)
            if 7 <= len(norm) < 10:
                lo, hi = (bisect.bisect_left(_sorted_keys, norm),
                          bisect.bisect_right(_sorted_keys, norm + "\uffff"))
                candidates = [rec for k in _sorted_keys[lo:hi] for rec in _inventory_index[k]]
                if candidates:
                    suggestion = sorted(candidates, key=lambda it: _normalize(it["شماره قطعه"]))[0]
                    disp       = code_str.replace(' ', '')  # نمایش استاندارد
                    if '-' not in disp:
                        clean = re.sub(r'[^A-Za-z0-9]', '', code_str)
                        disp = f"{clean[:5]}-{clean[5:]}"
                        await update.message.reply_text(
                            f"\u200F⚠️ \u202A`{disp}`\u202C متأسفانه موجود نمی‌باشد.\u200F",
                            parse_mode="Markdown"
                        )
                    await update.message.reply_text("🔍 آیا منظور شما این کالا است؟")
                    raw_code  = suggestion["شماره قطعه"]
                    code_md   = escape_markdown("\u200E"+raw_code+"\u200E", version=1)
                    brand_md  = escape_markdown(suggestion["برند"], version=1)
                    name_md   = escape_markdown(suggestion["نام کالا"], version=1)
                    try:
                        pv     = int(float(suggestion.get("فی فروش", 0)))
                        price_md = escape_markdown(f"{pv:,} ریال", version=1)
                    except:
                        price_md = escape_markdown(str(suggestion.get("فی فروش",0)), version=1)

                    # ✅ فقط اگر Iran Code موجود باشد، توضیحات را نمایش بده
                    iran_txt = suggestion.get("Iran Code") or ""
                    iran_line = f"توضیحات: {escape_markdown(iran_txt, version=1)}\n" if iran_txt else ""

                    await update.message.reply_text(
                        f"*کد:* `{code_md}`\n"
                        f"*برند:* {brand_md}\n"
                        f"نام کالا: {name_md}\n"
                        f"*قیمت:* {price_md}\n"
                        f"{iran_line}",
                        parse_mode="Markdown"
                    )
                    continue

            # حالت عادی «موجود نیست»
            clean = re.sub(r'[^A-Za-z0-9]', '', code_str)
            disp = f"{clean[:5]}-{clean[5:]}"
            await update.message.reply_text(
                f"\u200F⚠️ \u202A`{disp}`\u202C متأسفانه موجود نمی‌باشد.\u200F",
                parse_mode="Markdown"
            )
            continue

        # کالا(ها) موجود
        changeover = time(15, 0)
        before_msg = get_setting("delivery_before") or "🚚 تحویل کالا هر روز ساعت 16 و پنج‌شنبه‌ها 12:30"
        after_msg  = get_setting("delivery_after")  or "🛵 ارسال مستقیم از انبار (حدود 60 دقیقه)"
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
            iran_txt = item.get("Iran Code") or ""
            iran_line= f"توضیحات: {escape_markdown(iran_txt, version=1)}\n" if iran_txt else ""
            delivery_md = escape_markdown(delivery, version=1)
            await update.message.reply_text(
                f"*کد:* `{code_md}`\n"
                f"*برند:* {brand_md}\n"
                f"نام کالا: {name_md}\n"
                f"*قیمت:* {price_md}\n"
                f"{iran_line}\n"
                f"{delivery_md}",
                parse_mode="Markdown"
            )

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

    # حذف پیام راهنمای قبلی
    try:
        prev = context.user_data.get("last_prompt_id")
        if prev:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=prev
            )
    except:
        pass

    # ارسال پیام جدید و ذخیره‌ی شناسه‌ی آن
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
