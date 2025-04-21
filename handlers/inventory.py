import re
import asyncio
from datetime import datetime, time
import pandas as pd
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.connector import fetch_all_inventory_data
from database.connector_bot import get_setting, is_blacklisted

AWAITING_PART_CODE = 1
_cached_inventory_data: list[dict] = []
_last_cache_update: datetime | None = None

# ---------------- ابزار بررسی ساعات ----------------
def is_within_working_hours() -> tuple[bool, str, str]:
    try:
        start_str = get_setting("working_start") or "08:00"
        end_str = get_setting("working_end") or "18:00"
        start = datetime.strptime(start_str, "%H:%M").time()
        end = datetime.strptime(end_str, "%H:%M").time()
        now = datetime.now().time()
        return start <= now < end, start_str, end_str
    except:
        return True, "08:00", "18:00"

# ---------------- دریافت متن تحویل ----------------
def get_delivery_info() -> str:
    now = datetime.now().time()
    changeover_str = get_setting("changeover_hour") or "15:00"
    try:
        changeover = datetime.strptime(changeover_str, "%H:%M").time()
    except:
        changeover = time(15, 0)
    before = get_setting("delivery_before") or "🚚 تحویل کالا هر روز ساعت 16 و پنجشنبه‌ها ساعت 12:30"
    after = get_setting("delivery_after") or "🛵 ارسال مستقیم از انبار — تحویل ۶۰ دقیقه‌ای (هزینه پیک دارد)"
    return before if now < changeover else after

# ---------------- ساده‌سازی داده‌ها ----------------
def extract_brand_and_part(code: str | None) -> tuple[str|None, str|None]:
    if not code or pd.isna(code):
        return None, None
    parts = str(code).split("_")
    return parts[0], (parts[1] if len(parts) > 1 else None)

def replace_partial_code(base_code: str, variant: str) -> str:
    try:
        prefix, suffix = base_code.rsplit('-', 1)
    except:
        return base_code
    if variant.isdigit() and len(variant) < 5:
        return f"{prefix}-{suffix[:-len(variant)]}{variant}"
    if len(variant) == 5:
        return f"{prefix}-{variant}"
    return base_code

def process_row(row: dict) -> list[dict]:
    records = []
    raw_code = row.get("کد کالا", "")
    part, brand = extract_brand_and_part(raw_code)
    if not part:
        part = raw_code
    current = part
    for segment in str(part).split("/"):
        seg = segment.strip()
        if "-" in seg:
            current = seg
        else:
            current = replace_partial_code(current, seg)
        records.append({
            "شماره قطعه": current,
            "برند": brand or row.get("نام تامین کننده", "نامشخص"),
            "نام کالا": row.get("نام کالا", "نامشخص"),
            "فی فروش": row.get("فی فروش", 0),
            "Iran Code": row.get("Iran Code")
        })
    return records

def process_data(raw: list[dict]) -> list[dict]:
    return [r for row in raw for r in process_row(row)]

# ---------------- به‌روزرسانی کش ----------------
async def update_inventory_cache():
    global _cached_inventory_data, _last_cache_update
    while True:
        raw = fetch_all_inventory_data()
        _cached_inventory_data = process_data(raw) if raw else []
        _last_cache_update = datetime.now()
        await asyncio.sleep(20 * 60)

# ---------------- اعتبارسنجی فرمت ----------------
def is_valid_code(text: str) -> bool:
    return bool(re.fullmatch(r'\d{5}[-_/]?\d{5}', text.strip()))

# ---------------- کیبورد راهنما ----------------
def get_next_prompt_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("بازگشت به منو اصلی", callback_data="main_menu")
    ]])

# ---------------- هندلر شروع استعلام ----------------
async def handle_inventory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    # بررسی بلک‌لیست
    if is_blacklisted(user_id):
        await update.message.reply_text(
            "⛔️ شما در لیست سیاه هستید.\n"
            "برای رفع مشکل با پشتیبانی تماس بگیرید."
        )
        return ConversationHandler.END

    # بررسی ساعات کاری
    ok, start, end = is_within_working_hours()
    if not ok:
        await update.message.reply_text(
            f"⏰ ساعات کاری ربات از {start} تا {end} می‌باشد.\n"
            "لطفاً در این بازه برای استعلام تلاش کنید."
        )
        return ConversationHandler.END

    # شروع
    await update.message.reply_text("🔍 لطفاً کد قطعه را وارد کنید:")
    return AWAITING_PART_CODE

# ---------------- هندلر دریافت کد ----------------
async def handle_inventory_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    # اگر کاربر دکمه توضیحات را زد
    if text == "نحوه ثبت سفارش":
        await update.message.reply_text(
            "📝 نحوه ثبت سفارش:\n"
            "برای ثبت سفارش، پس از استعلام کد قطعه، با بخش فروش تماس بگیرید."
        )
        return ConversationHandler.END
    if text == "نحوه تحویل":
        await update.message.reply_text(
            "🚚 نحوه تحویل:\n"
            "تحویل کالا هر روز ساعت 16 و پنجشنبه‌ها ساعت 12:30 در دفتر بازار."
        )
        return ConversationHandler.END
    if text == "تماس با ما":
        await update.message.reply_text(
            "📞 تماس با ما:\n"
            "۰۹۱۲۱۲۳۴۵۶۷"
        )
        return ConversationHandler.END

    # اعتبارسنجی فرمت
    if not is_valid_code(text):
        await update.message.reply_text(
            "⛔️ کد وارد شده معتبر نیست.\n"
            "لطفاً یکی از فرمت‌های زیر را وارد کنید:\n"
            "- 12345-12345\n"
            "- 12345_12345\n"
            "- 1234512345\n"
            "- 12345/12345"
        )
        return AWAITING_PART_CODE

    # آماده‌سازی پاسخ
    delivery = get_delivery_info()
    norm = re.sub(r'[-_/.,\s]', '', text).upper()
    matched = [
        item for item in _cached_inventory_data
        if re.sub(r'[-_/.,\s]', '', item["شماره قطعه"]).upper() == norm
    ]

    if not matched:
        await update.message.reply_text(f"⚠️ کد `{text}` موجود نمی‌باشد.", parse_mode="Markdown")
    else:
        for item in matched:
            iran = item.get("Iran Code")
            iran_line = f"توضیحات: {iran}\n" if iran else ""
            price = item.get("فی فروش", 0)
            try:
                price_str = f"{int(float(price)):,} ریال"
            except:
                price_str = str(price)
            msg = (
                f"کد: `{item['شماره قطعه']}`\n"
                f"برند: **{item['برند']}**\n"
                f"نام کالا: {item['نام کالا']}\n"
                f"قیمت: **{price_str}**\n"
                f"{iran_line}"
                f"{delivery}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")

    # حذف پیام راهنمای قبلی
    last_id = context.user_data.get("last_prompt_id")
    if last_id:
        try:
            await context.bot.delete_message(update.effective_chat.id, last_id)
        except:
            pass

    # ارسال پیام راهنمای جدید
    sent = await update.message.reply_text(
        "🔍 برای استعلام بعدی، کد را وارد کنید یا /cancel.",
        reply_markup=get_next_prompt_kb()
    )
    context.user_data["last_prompt_id"] = sent.message_id
    return AWAITING_PART_CODE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return ConversationHandler.END
