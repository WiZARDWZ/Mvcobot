import re
import asyncio
from datetime import datetime, timedelta
import pandas as pd
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from database.connector import fetch_all_inventory_data

# وضعیت مکالمه
AWAITING_PART_CODE = 1

# متغیرهای کش سراسری
_cached_inventory_data = []
_last_cache_update = None

# ================= توابع ساده‌سازی داده‌ها =================
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
    else:
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
                "برند": brand if brand else row.get("نام تامین کننده", "نامشخص"),
                "شماره قطعه": last_base_code,
                "نام کالا": row.get("نام کالا", "نامشخص"),
                "فی فروش": row.get("فی فروش", 0),
                "Iran Code": row.get("Iran Code")
            })
        elif last_base_code:
            new_code = replace_partial_code(last_base_code, part)
            last_base_code = new_code
            records.append({
                "برند": brand if brand else row.get("نام تامین کننده", "نامشخص"),
                "شماره قطعه": new_code,
                "نام کالا": row.get("نام کالا", "نامشخص"),
                "فی فروش": row.get("فی فروش", 0),
                "Iran Code": row.get("Iran Code")
            })
    return records

def process_data(raw_data):
    processed_records = []
    for row in raw_data:
        processed_records.extend(process_row(row))
    return processed_records

def normalize_code(code):
    return re.sub(r'[-_/.,\s]', '', code).upper()

def get_cached_data():
    return _cached_inventory_data

def find_similar_products(input_code):
    normalized_input = normalize_code(input_code)
    products = []
    for item in get_cached_data():
        product_code = item.get("شماره قطعه", "")
        if normalize_code(product_code) == normalized_input:
            products.append(item)
    return products

# ================= به‌روزرسانی دوره‌ای کش =================
async def update_inventory_cache():
    global _cached_inventory_data, _last_cache_update
    while True:
        try:
            raw_data = fetch_all_inventory_data()
            if raw_data:
                _cached_inventory_data = process_data(raw_data)
                _last_cache_update = datetime.now()
                print(f"[{datetime.now()}] کش موجودی به‌روز شد. تعداد رکورد: {len(_cached_inventory_data)}")
            else:
                print("دریافت داده از دیتابیس با خطا مواجه شد.")
        except Exception as e:
            print("خطا در به‌روزرسانی کش:", e)
        await asyncio.sleep(20 * 60)

# ================= هندلرهای مکالمه =================
async def handle_inventory_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("\U0001F50D لطفاً کد قطعه را وارد کنید:")
    return AWAITING_PART_CODE

async def handle_inventory_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    input_text = update.message.text.strip()
    pattern = r'(\d{5}(?:[-_/.,\s]+)?[A-Za-z0-9]{5})'
    codes = re.findall(pattern, input_text)
    if not codes:
        codes = [input_text]
    codes = list(set(codes))

    for part_code in codes:
        try:
            products = find_similar_products(part_code)
            if not products:
                await update.message.reply_text(f"\u26A0\ufe0f کد '{part_code}' متأسفانه موجود نمی‌باشد.")
            else:
                for item in products:
                    part_number = item.get("شماره قطعه", "نامشخص")
                    brand = item.get("برند", "نامشخص")
                    product_name = item.get("نام کالا", "نامشخص")
                    price = item.get("فی فروش", 0)
                    try:
                        formatted_price = f"{int(float(price)):,} ریال"
                    except Exception:
                        formatted_price = str(price)
                    iran_code = item.get("Iran Code")
                    iran_line = f"توضیحات: {iran_code}\n" if iran_code and str(iran_code).strip() != "" else ""
                    response = (
                        f"کد: \u2068{part_number}\u2069\n"
                        f"برند: {brand}\n"
                        f"نام کالا: {product_name}\n"
                        f"قیمت: {formatted_price}\n"
                        f"{iran_line}\n\n"
                        "\U0001F6F5 ارسال مستقیم از انبار با زمان تقریبی تحویل 60 دقیقه در هر ساعتی امکان پذیر می‌باشد (هزینه پیک دارد)"
                    )
                    await update.message.reply_text(response)
        except Exception as e:
            await update.message.reply_text(f"\u26A0\ufe0f خطایی رخ داد: {str(e)}")

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("بازگشت به منو اصلی", callback_data="main_menu")]]
    )
    await update.message.reply_text(
        "\U0001F50D لطفاً کد قطعه بعدی را وارد کنید یا /cancel را برای خروج وارد کنید:",
        reply_markup=keyboard
    )
    return AWAITING_PART_CODE

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text("❌ عملیات لغو شد.")
    elif update.message:
        await update.message.reply_text("❌ عملیات لغو شد.")
    return ConversationHandler.END
