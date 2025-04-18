import re
import asyncio
from datetime import datetime
import pandas as pd
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from database.connector import fetch_all_inventory_data
from database.connector_bot import get_setting

AWAITING_PART_CODE = 1
_cached_inventory_data = []
_last_cache_update = None

# ------------------ توابع کمکی ------------------ #
def extract_brand_and_part(code):
    if pd.isna(code):
        return None, None
    parts = str(code).split("_")
    part_number = parts[0]
    brand = parts[1] if len(parts) > 1 else None
    return part_number, brand

def replace_partial_code(base_code, variant):
    try:
        base_prefix, base_suffix = base_code.rsplit('-', 1)
    except Exception:
        return base_code
    if variant.isdigit() and len(variant) < 5:
        new_suffix = base_suffix[:-len(variant)] + variant
        return f"{base_prefix}-{new_suffix}"
    elif len(variant) == 5:
        return f"{base_prefix}-{variant}"
    return base_code

def process_row(row):
    records = []
    code = row.get("کد کالا", "")
    part_number, brand = extract_brand_and_part(code)
    if not part_number:
        part_number = code
    parts = str(part_number).split('/')
    last_base_code = None
    for part in parts:
        part = part.strip()
        if '-' in part and len(part.split('-')[-1]) >= 5:
            last_base_code = part
            records.append({
                "برند": brand or row.get("نام تامین کننده", "نامشخص"),
                "شماره قطعه": last_base_code,
                "نام کالا": row.get("نام کالا", "نامشخص"),
                "فی فروش": row.get("فی فروش", 0),
                "Iran Code": row.get("Iran Code")
            })
        elif last_base_code:
            new_code = replace_partial_code(last_base_code, part)
            last_base_code = new_code
            records.append({
                "برند": brand or row.get("نام تامین کننده", "نامشخص"),
                "شماره قطعه": new_code,
                "نام کالا": row.get("نام کالا", "نامشخص"),
                "فی فروش": row.get("فی فروش", 0),
                "Iran Code": row.get("Iran Code")
            })
    return records

def process_data(raw_data):
    return [record for row in raw_data for record in process_row(row)]

def normalize_code(code):
    code = re.sub(r'[\u202d\u202c\u2068\u2069\u200e\u200f\u200b]', '', str(code))
    return re.sub(r'[-_/.,\s]', '', code).upper()

def get_cached_data():
    return _cached_inventory_data

def find_similar_products(input_code):
    norm_input = normalize_code(input_code)
    return [item for item in get_cached_data() if normalize_code(item.get("شماره قطعه", "")) == norm_input]

# ------------------ به‌روزرسانی کش ------------------ #
async def update_inventory_cache():
    global _cached_inventory_data, _last_cache_update
    while True:
        try:
            raw_data = fetch_all_inventory_data()
            if raw_data:
                _cached_inventory_data = process_data(raw_data)
                _last_cache_update = datetime.now()
                print(f"[{_last_cache_update}] کش موجودی به‌روز شد. رکوردها: {len(_cached_inventory_data)}")
            else:
                print("⚠️ خطا در دریافت موجودی از دیتابیس.")
        except Exception as e:
            print("❌ خطا در به‌روزرسانی کش:", e)
        await asyncio.sleep(20 * 60)

# ------------------ هندلرهای تلگرام ------------------ #
async def handle_inventory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("🔍 لطفاً کد قطعه را وارد کنید:")
    return AWAITING_PART_CODE

async def handle_inventory_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    pattern = r'(\d{5}(?:[-_/.,\s]+)?[A-Za-z0-9]{5})'
    codes = re.findall(pattern, input_text)
    if not codes:
        await update.message.reply_text(
            "⛔️ کد وارد شده معتبر نیست. لطفاً کدی با یکی از فرمت‌های زیر وارد کنید:\n"
            "- 12345-12345\n- 12345_12345\n- 1234512345\n- 12345/12345"
        )
        return AWAITING_PART_CODE

    # دریافت متن تحویل بر اساس ساعت
    try:
        now = datetime.now().time()

        raw_changeover = get_setting("changeover_hour")
        changeover_str = raw_changeover if isinstance(raw_changeover, str) else "15:00"
        changeover = datetime.strptime(changeover_str, "%H:%M").time()

        delivery_before = get_setting("delivery_before")
        delivery_after = get_setting("delivery_after")

        if now < changeover:
            delivery_info = delivery_before if isinstance(delivery_before, str) else "🛵 ارسال قبل از ساعت تعیین‌شده"
        else:
            delivery_info = delivery_after if isinstance(delivery_after, str) else "🛵 ارسال بعد از ساعت تعیین‌شده"

    except Exception as e:
        print("❌ خطا در تنظیمات ارسال:", e)
        delivery_info = "🛵 ارسال سریع از انبار — تحویل ۶۰ دقیقه‌ای (هزینه پیک دارد)"

    for part_code in list(set(codes)):
        try:
            products = find_similar_products(part_code)
            if not products:
                await update.message.reply_text(f"⚠️ کد '{part_code}' متأسفانه موجود نمی‌باشد.")
            else:
                for item in products:
                    part = item.get("شماره قطعه", "نامشخص")
                    brand = item.get("برند", "نامشخص")
                    name = item.get("نام کالا", "نامشخص")
                    price = item.get("فی فروش", 0)
                    try:
                        formatted_price = f"{int(float(price)):,} ریال"
                    except:
                        formatted_price = str(price)
                    iran = item.get("Iran Code")
                    iran_line = f"توضیحات: {iran}\n" if iran and str(iran).strip() else ""
                    text = (
                        f"کد: \u2068{part}\u2069\n"
                        f"برند: {brand}\n"
                        f"نام کالا: {name}\n"
                        f"قیمت: {formatted_price}\n"
                        f"{iran_line}\n"
                        f"{delivery_info}"
                    )
                    await update.message.reply_text(text)
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در پردازش: {str(e)}")

    # حذف پیام راهنمای قبلی (اگه وجود داشته باشه)
    try:
        old_msg_id = context.user_data.get("last_prompt_id")
        if old_msg_id:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=old_msg_id
            )
    except Exception as e:
        print("❌ خطا در حذف پیام قبلی:", e)

    # ارسال پیام راهنمای جدید
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("بازگشت به منو اصلی", callback_data="main_menu")]]
    )
    sent = await update.message.reply_text(
        "🔍 لطفاً کد قطعه بعدی را وارد کنید یا /cancel را برای خروج وارد کنید:",
        reply_markup=keyboard
    )
    context.user_data["last_prompt_id"] = sent.message_id

    return AWAITING_PART_CODE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return ConversationHandler.END
