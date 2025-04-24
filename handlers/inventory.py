import re
import asyncio
from datetime import datetime
import pandas as pd
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from database.connector import fetch_all_inventory_data
from database.connector_bot import get_setting, is_blacklisted
from telegram.helpers import escape_markdown

AWAITING_PART_CODE = 1
_cached_inventory_data = []
_last_cache_update = None

# ================= Cache Updater =================
async def update_inventory_cache():
    global _cached_inventory_data, _last_cache_update
    while True:
        try:
            raw = fetch_all_inventory_data()
            if raw:
                # process each row into one or more records
                _cached_inventory_data = [
                    rec
                    for row in raw
                    for rec in _process_row(row)
                ]
                _last_cache_update = datetime.now()
                print(f"[{_last_cache_update}] Cache refreshed: {len(_cached_inventory_data)} records")
            else:
                print("⚠️ خطا در دریافت داده از دیتابیس.")
        except Exception as e:
            print("❌ خطا در به‌روزرسانی کش:", e)
        await asyncio.sleep(20 * 60)

# ================= Helpers =================
def _extract_brand_and_part(code: str):
    if pd.isna(code):
        return None, None
    parts = str(code).split("_")
    return parts[0], parts[1] if len(parts) > 1 else None

def _replace_partial(base: str, var: str):
    try:
        pfx, sfx = base.rsplit("-", 1)
    except ValueError:
        return base
    if var.isdigit() and len(var) < 5:
        return f"{pfx}-{sfx[:-len(var)]}{var}"
    if len(var) == 5:
        return f"{pfx}-{var}"
    return base

def _process_row(row: dict):
    """Extract all valid part number variants from a single DB row."""
    recs = []
    code = row.get("کد کالا", "")
    part, brand = _extract_brand_and_part(code)
    if not part:
        part = code

    parts = str(part).split('/')  # جداکردن کدها
    last_base_code = None

    for part_code in parts:
        part_code = part_code.strip()

        if '-' in part_code and len(part_code.split('-')[-1]) >= 5:
            last_base_code = part_code
            recs.append({
                "شماره قطعه": last_base_code,
                "برند": brand or row.get("نام تامین کننده", "نامشخص"),
                "نام کالا": row.get("نام کالا", "نامشخص"),
                "فی فروش": row.get("فی فروش", 0),
                "Iran Code": row.get("Iran Code")
            })
        elif last_base_code:
            new_code = _replace_partial(last_base_code, part_code)
            last_base_code = new_code  # به‌روزرسانی
            recs.append({
                "شماره قطعه": new_code,
                "برند": brand or row.get("نام تامین کننده", "نامشخص"),
                "نام کالا": row.get("نام کالا", "نامشخص"),
                "فی فروش": row.get("فی فروش", 0),
                "Iran Code": row.get("Iran Code")
            })

    return recs

def _normalize(code: str):
    # strip invisible/unicode junk, then remove separators
    cleaned = re.sub(r'[\u202d\u202c\u2068\u2069\u200e\u200f\u200b]', '', code)
    return re.sub(r'[-_/.,\s]', '', cleaned).upper()

def _find_products(code: str):
    key = _normalize(code)
    matches = [
        item for item in _cached_inventory_data
        if _normalize(item.get("شماره قطعه", "")) == key
    ]

    # اگر تطابق دقیق نداشت و کد حداقل 10 رقمی بود
    if not matches and len(key) >= 10:
        # جستجوی با شروع 10 رقم اول
        candidates = [
            item for item in _cached_inventory_data
            if _normalize(item.get("شماره قطعه", "")).startswith(key[:10])
        ]
        # اگر فقط یک مورد مشابه پیدا شد، همون رو برگردون
        if len(candidates) == 1:
            return candidates
        # اگر چند مورد مشابه بودن، همه‌شون رو برگردون (مثلاً رنگ‌های مختلف)
        elif len(candidates) > 1:
            return sorted(candidates, key=lambda x: _normalize(x.get("شماره قطعه", "")))

    return matches

# ================= Telegram Handlers =================
async def handle_inventory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if is_blacklisted(uid):
        await update.message.reply_text("⛔️ شما در لیست سیاه هستید. لطفاً برای رفع مشکل با پشتیبانی تماس بگیرید.")
        return ConversationHandler.END

    start = get_setting("working_start") or "08:00"
    end   = get_setting("working_end")   or "18:00"
    now_time = datetime.now().time()
    if not (datetime.strptime(start, "%H:%M").time() <= now_time < datetime.strptime(end, "%H:%M").time()):
        await update.message.reply_text(f"⏰ ساعات کاری ربات از {start} تا {end} می‌باشد. لطفاً در این بازه برای استعلام تلاش کنید.")
        return ConversationHandler.END

    sent = await update.message.reply_text("🔍 لطفاً کد قطعه را وارد کنید:")
    context.user_data["last_prompt_id"] = sent.message_id
    return AWAITING_PART_CODE

async def handle_inventory_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if is_blacklisted(uid):
        await update.message.reply_text("⛔️ شما در لیست سیاه هستید.")
        return ConversationHandler.END

    # بررسی ساعات کاری
    start = get_setting("working_start") or "08:00"
    end   = get_setting("working_end")   or "18:00"
    now_time = datetime.now().time()
    if not (datetime.strptime(start, "%H:%M").time() <= now_time < datetime.strptime(end, "%H:%M").time()):
        await update.message.reply_text(f"⏰ ساعات کاری ربات از {start} تا {end} می‌باشد.")
        return ConversationHandler.END

    raw = update.message.text.strip()
    # جداکردن خطوط ورودی
    lines = [ln.strip() for ln in re.split(r'[\r\n]+', raw) if ln.strip()]
    pattern = r'^[A-Za-z0-9]{5}[-_/\.]?[A-Za-z0-9]{5}$'

    valid = [ln for ln in lines if re.fullmatch(pattern, ln)]
    invalid = [ln for ln in lines if not re.fullmatch(pattern, ln)]

    # آماده‌سازی متن تحویل
    now = datetime.now().time()
    chg = datetime.strptime(get_setting("changeover_hour") or "15:00", "%H:%M").time()
    before = get_setting("delivery_before") or "🚚 تحویل کالا هر روز ساعت 16 و پنجشنبه‌ها 12:30"
    after  = get_setting("delivery_after")  or "🛵 ارسال مستقیم از انبار (حدود 60 دقیقه)"
    delivery_info = before if now < chg else after

    # ۱) پاسخ به کدهای معتبر
    seen = set()
    for ln in valid:
        norm = re.sub(r'[-_/\.]', '', ln).upper()
        if norm in seen:
            continue
        seen.add(norm)

        products = _find_products(norm)
        if not products:
            disp = ln if "-" in ln else ln[:5] + "-" + ln[5:]
            await update.message.reply_text(
        f"⚠️ کد \u2068{disp}\u2069 متأسفانه موجود نمی‌باشد.",
        parse_mode="Markdown")
        else:
            for item in products:
                price = item.get("فی فروش", 0)
                try:
                    price_str = f"{int(float(price)):,} ریال"
                except:
                    price_str = str(price)
                iran = item.get("Iran Code") or ""
                iran_line = f"توضیحات: {iran}\n" if iran else ""
                await update.message.reply_text(
                    f"**کد:** `\u2066{item['شماره قطعه']}\u2069`\n"
                    f"برند: **{item['برند']}**\n"
                    f"نام کالا: {item['نام کالا']}\n"
                    f"قیمت: **{price_str}**\n"
                    f"{iran_line}\n"
                    f"{delivery_info}",
                    parse_mode="Markdown"
                )
    # ۲) سپس در صورت وجود کد نامعتبر، پیام خطای جداگانه
    if invalid:
        inv_list = "、".join(invalid)
        await update.message.reply_text(
            "⛔️ فرمت یک یا چند کد نامعتبر است:\n"
            f"({inv_list})\n\n"
            "لطفاً فقط یکی از فرمت‌های زیر را وارد کنید:\n"
            "- 12345-12345\n"
            "- 12345_12345\n"
            "- 1234512345\n"
            "- 12345/12345\n"
            "- 12345.12345\n\n"
            "نیازی به وارد کردن کد رنگ نیست"
        )

    # ۳) حذف پیام راهنما و ارسال مجدد منوی انتهایی
    try:
        old = context.user_data.get("last_prompt_id")
        if old:
            await context.bot.delete_message(update.effective_chat.id, old)
    except:
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
