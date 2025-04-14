import asyncio
import pandas as pd
import pyodbc
import re
from datetime import datetime, timedelta
import json
from telethon import TelegramClient, events
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ================= تنظیمات اصلی =================
settings = {
    "enabled": True,
    "db_type": "sql_server",            # استفاده از SQL Server
    "cache_duration_minutes": 20,       # هر 20 دقیقه به‌روزرسانی کش
    "working_hours": {"start": "08:00", "end": "18:00"},
    "thursday_hours": {"start": "08:00", "end": "14:00"},
    "disable_friday": True,
    "blacklist": [],
    "lunch_break": {"start": "12:00", "end": "13:00"},
    "delivery_info": {
        "before_15": "تحویل کالا هر روز ساعت 16 و پنجشنبه‌ها ساعت 12:30 در دفتر بازار",
        "after_15": "‼️ ارسال مستقیم از انبار با زمان تقریبی تحویل 45 دقیقه امکان‌پذیر است (هزینه پیک دارد)"
    },
    "changeover_hour": "15:00"
}

def load_settings():
    try:
        with open("bot_settings.json", "r", encoding="utf-8") as f:
            settings.update(json.load(f))
    except FileNotFoundError:
        save_settings()

def save_settings():
    with open("bot_settings.json", "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

load_settings()

# ================= تنظیمات SQL Server =================
SQL_SERVER_CONFIG = {
    "driver": "{ODBC Driver 17 for SQL Server}",
    "server": "WIN-9R9B3VCBI6G\SEPIDAR", 
    "database": "Sepidar01",
    "user": "damavand",
    "password": "damavand",
    "trusted_connection": "yes"
}

# ================= تنظیمات تلگرام =================
API_ID = 28467783
API_HASH = "fc56957891f9e5bb9923071d9ba8bd29"
PHONE_NUMBER = "+989025029290"
MAIN_GROUP_ID = -1001403812583
NEW_GROUP_ID = -1002391888673
ADMIN_GROUP_ID = -1002391888673

# ================= متغیرهای کش و محدودیت‌ها =================
cached_simplified_data = []
last_cache_update = None
sent_messages = {}
user_query_counts = {}
QUERY_LIMIT = 50
total_queries = 0

# ================= توابع اتصال به SQL Server =================
def get_sql_data():
    connection_string = (
        f"Driver={SQL_SERVER_CONFIG['driver']};"
        f"Server={SQL_SERVER_CONFIG['server']};"
        f"Database={SQL_SERVER_CONFIG['database']};"
        f"UID={SQL_SERVER_CONFIG['user']};"
        f"PWD={SQL_SERVER_CONFIG['password']};"
    )
    try:
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        sql_query = """
DECLARE @RgParamFiscalYearID INT = (SELECT MAX(FiscalYearId) FROM FMK.FiscalYear);

WITH purch AS (
    SELECT 
        r.Number,
        r.Date,
        r.DelivererCode,
        r.DelivererTitle,
        ri.ItemCode,
        ri.ItemTitle,
        ri.Quantity,
        ri.Fee,
        ri.Price,
        r.StockTitle,
        ri.TracingTitle
    FROM 
        inv.vwInventoryReceipt r 
    LEFT JOIN 
        INV.vwInventoryReceiptItem ri 
        ON r.InventoryReceiptID = ri.InventoryReceiptRef
    WHERE 
        r.FiscalYearRef = @RgParamFiscalYearID 
        AND r.Type = 1
),
Item AS (
    SELECT 
        i.UnitTitle,
        i.Code,
        i.SaleGroupTitle,
        p.PropertyAmount1,
        i.Title,
        ii.StockTitle
    FROM 
        inv.vwItem i
    LEFT JOIN 
        inv.vwItemPropertyAmount p 
        ON i.ItemID = p.ItemRef
    LEFT JOIN 
        inv.vwItemStock ii 
        ON i.ItemID = ii.ItemRef
    WHERE 
        i.Type = 1
),
StockSumery AS (
    SELECT 
        ItemCode, 
        StockTitle, 
        SUM(Quantity) AS Quantity, 
        TracingTitle
    FROM 
        inv.vwItemStockSummary
    WHERE 
        FiscalYearRef = @RgParamFiscalYearID
    GROUP BY 
        ItemCode, 
        StockTitle, 
        TracingTitle
),
FeeSale AS (
    SELECT 
        ItemCode, 
        TracingTitle, 
        Fee
    FROM 
        sls.vwPriceNoteItem
    WHERE 
        Fee > 0
)

SELECT 
    i.Code AS [کد کالا],
    i.Title AS [نام کالا],
    i.UnitTitle AS [واحد سنجش],
    i.SaleGroupTitle AS [گروه فروش],
    i.PropertyAmount1 AS [مشخصات کالا],
    p.DelivererCode AS [کد تامین کننده],
    p.DelivererTitle AS [نام تامین کننده],
    p.Date AS [تاریخ],
    p.Number AS [شماره],
    p.Fee AS [فی خرید],
    p.Quantity AS [تعداد خرید],
    p.Price AS [مبلغ خرید],
    i.StockTitle AS [انبار],
    COALESCE(p.TracingTitle, s.TracingTitle, 'نا مشخص') AS [عامل ردیابی],
    s.Quantity AS [موجودی],
    fs.Fee AS [فی فروش]
FROM 
    Item i
LEFT JOIN 
    purch p 
    ON i.Code = p.ItemCode 
    AND i.StockTitle = p.StockTitle
LEFT JOIN 
    StockSumery s 
    ON i.Code = s.ItemCode 
    AND i.StockTitle = s.StockTitle 
    AND COALESCE(p.TracingTitle, '') = COALESCE(s.TracingTitle, '')
LEFT JOIN 
    FeeSale fs 
    ON i.Code = fs.ItemCode 
    AND COALESCE(s.TracingTitle, '') = COALESCE(fs.TracingTitle, '')
WHERE 
    s.Quantity IS NOT NULL 
    AND s.Quantity > 0
    AND fs.Fee IS NOT NULL;
        """
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        data = [dict(zip(columns, row)) for row in rows]
        cursor.close()
        conn.close()
        return data
    except Exception as e:
        print("خطا در اتصال به SQL Server:", e)
        return []

# ================= توابع پردازش داده (مشابه اسکریپت AllinOneExcel2.py) =================
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
                "برند": brand if brand else row.get("برند", "نامشخص"),
                "شماره قطعه": last_base_code,
                "نام کالا": row.get("نام کالا", ""),
                "فی فروش": row.get("فی فروش", 0)
            })
        elif last_base_code:
            new_code = replace_partial_code(last_base_code, part)
            last_base_code = new_code
            records.append({
                "برند": brand if brand else row.get("برند", "نامشخص"),
                "شماره قطعه": new_code,
                "نام کالا": row.get("نام کالا", ""),
                "فی فروش": row.get("فی فروش", 0)
            })
    return records

def process_data(raw_data):
    processed_records = []
    df = pd.DataFrame(raw_data)
    if "کد کالا" in df.columns:
        extracted = df["کد کالا"].apply(lambda x: pd.Series(extract_brand_and_part(x)))
        extracted.columns = ["شماره قطعه", "برند"]
        df = pd.concat([df, extracted], axis=1)
    for index, row in df.iterrows():
        records = process_row(row)
        processed_records.extend(records)
    return processed_records

# ================= به‌روزرسانی دوره‌ای کش =================
async def update_cache_periodically():
    global cached_simplified_data, last_cache_update
    while True:
        print("Updating data from the database...")
        raw_data = get_sql_data()
        if raw_data:
            processed = process_data(raw_data)
            cached_simplified_data = processed
            last_cache_update = datetime.now()
            print(f"Data has been updated. Number of records: {len(processed)}")
        else:
            print("Error connecting to SQL Server:", e)
        await asyncio.sleep(settings.get("cache_duration_minutes", 20) * 60)

def get_cached_data():
    return cached_simplified_data

# ================= توابع کمکی =================
def normalize_code(code):
    return re.sub(r'[-_/.,\s]', '', code).upper()

def fix_part_number_display(part_number):
    return f"\u2067{part_number}\u2069"

def is_recently_sent(user_id, product_code, group_id):
    if group_id == NEW_GROUP_ID:
        return False
    now = datetime.now()
    key = f"{user_id}:{product_code}"
    if key in sent_messages and now - sent_messages[key] < timedelta(hours=24):
        return True
    return False

def log_sent_message(user_id, product_code):
    key = f"{user_id}:{product_code}"
    sent_messages[key] = datetime.now()

# به‌روز شده برای نمایش قیمت بدون اعشار:
def format_price(price):
    try:
        return f"{float(price):,.0f}"
    except Exception:
        return str(price)

original_brands = ["MOBIS", "GENUINE"]

def find_similar_products(partial_code, only_original=False):
    data = get_cached_data()
    normalized_partial_code = normalize_code(partial_code)
    brand_products = {}
    for row in data:
        try:
            product_code = row.get("شماره قطعه", "")
            normalized_code = normalize_code(str(product_code))
            brand = row.get("برند", "نامشخص")
            price = row.get("فی فروش", 0)
            if isinstance(price, str):
                price = int(price) if price.isdigit() else 0
        except Exception:
            continue
        if normalized_partial_code == normalized_code:
            if only_original and brand not in original_brands:
                continue
            if brand not in brand_products or price > brand_products[brand]['price']:
                brand_products[brand] = {
                    'product_code': product_code,
                    'brand': brand,
                    'price': price,
                    'name': row.get("نام کالا", "")
                }
    return list(brand_products.values())

# ================= بررسی محدودیت زمانی =================
def is_within_active_hours():
    if not settings["enabled"]:
        return False
    now = datetime.now().time()
    # زمان ناهار
    lunch = settings.get("lunch_break", {"start": "12:00", "end": "13:00"})
    lunch_start = datetime.strptime(lunch["start"], "%H:%M").time()
    lunch_end = datetime.strptime(lunch["end"], "%H:%M").time()
    if lunch_start <= now < lunch_end:
        return False
    # تعطیلی جمعه
    if settings.get("disable_friday", True) and datetime.now().weekday() == 4:
        return False
    # روز پنج‌شنبه
    if datetime.now().weekday() == 3:
        thursday = settings.get("thursday_hours", {"start": "08:00", "end": "14:00"})
        thursday_start = datetime.strptime(thursday["start"], "%H:%M").time()
        thursday_end = datetime.strptime(thursday["end"], "%H:%M").time()
        return thursday_start <= now < thursday_end
    # روزهای عادی
    working = settings.get("working_hours", {"start": "08:00", "end": "18:00"})
    working_start = datetime.strptime(working["start"], "%H:%M").time()
    working_end = datetime.strptime(working["end"], "%H:%M").time()
    return working_start <= now < working_end

# ================= رویدادهای تلگرام =================
client = TelegramClient('session_name', API_ID, API_HASH)

@client.on(events.NewMessage(chats=[MAIN_GROUP_ID, NEW_GROUP_ID]))
async def handle_new_message(event):
    global total_queries
    group_id = event.chat_id
    if group_id == MAIN_GROUP_ID and not is_within_active_hours():
        return
    message_text = event.message.message
    sender = await event.get_sender()
    sender_id = sender.id
    if sender_id in settings["blacklist"]:
        return
    now = datetime.now()
    if sender_id not in user_query_counts:
        user_query_counts[sender_id] = {"count": 0, "start": now}
    else:
        if now - user_query_counts[sender_id]["start"] >= timedelta(hours=24):
            user_query_counts[sender_id] = {"count": 0, "start": now}
    if user_query_counts[sender_id]["count"] >= QUERY_LIMIT:
        return
    pattern = r'(\d{5}(?:[-_/.,\s]+)?[A-Za-z0-9]{5})(?:\s+(asl|asli|\u0627\u0635\u0644|\u0627\u0635\u0644\u06cc))?'
    matches = re.findall(pattern, message_text, re.IGNORECASE)
    processed_codes = set()
    for match in matches:
        code, is_original = match
        normalized_code = normalize_code(code)
        if normalized_code in processed_codes:
            continue
        processed_codes.add(normalized_code)
        if user_query_counts[sender_id]["count"] >= QUERY_LIMIT:
            break
        if is_recently_sent(sender_id, normalized_code, group_id):
            continue
        user_query_counts[sender_id]["count"] += 1
        total_queries += 1
        only_original = bool(is_original)
        products = find_similar_products(normalized_code, only_original=only_original)
        if products:
            for product in products:
                fixed_product_code = fix_part_number_display(product['product_code'])
                current_time = datetime.now().time()
                try:
                    changeover_time = datetime.strptime(settings.get("changeover_hour", "15:00"), "%H:%M").time()
                except Exception:
                    changeover_time = datetime.strptime("15:00", "%H:%M").time()
                if current_time < changeover_time:
                    footer_text = settings.get("delivery_info", {}).get("before_15", "")
                else:
                    footer_text = settings.get("delivery_info", {}).get("after_15", "")
                formatted_price = format_price(product['price'])
                if group_id == MAIN_GROUP_ID and product['brand'] in original_brands:
                    response = (
                        "سلام وقت بخیر\n\n"
                        f"کد: `{fixed_product_code}`\n"
                        f"برند: **{product['brand']}**\n"
                        f"نام کالا: {product['name']}\n"
                        f"قیمت: {formatted_price} ریال\n\n"
                        f"{footer_text}\n"
                    )
                else:
                    response = (
                        "سلام وقت بخیر\n\n"
                        f"کد: `{fixed_product_code}`\n"
                        f"برند: **{product['brand']}**\n"
                        f"نام کالا: {product['name']}\n"
                        f"قیمت: {formatted_price} ریال\n\n"
                        f"{footer_text}\n"
                    )
                await client.send_message(sender_id, response, parse_mode='markdown')
        log_sent_message(sender_id, normalized_code)

@client.on(events.NewMessage(chats=ADMIN_GROUP_ID))
async def handle_admin_commands(event):
    global QUERY_LIMIT
    message_text = event.message.message.strip()
    lower_text = message_text.lower()

    if lower_text == "/disable":
        settings["enabled"] = False
        save_settings()
        await event.reply("⏹️ غیرفعال کردن فعالیت ربات.\n❌ ربات خاموش شد.")
    elif lower_text == "/enable":
        settings["enabled"] = True
        save_settings()
        await event.reply("▶️ فعال کردن مجدد فعالیت ربات.\n✅ ربات روشن شد.")
    elif lower_text.startswith("/blacklist add "):
        try:
            user_id = int(message_text.split()[-1])
            if user_id not in settings["blacklist"]:
                settings["blacklist"].append(user_id)
                save_settings()
                await event.reply(f"🚫 جلوگیری از استفاده کاربر {user_id} از ربات.\nکاربر به لیست سیاه اضافه شد.")
        except ValueError:
            await event.reply("❗️ فرمت وارد شده صحیح نیست.")
    elif lower_text.startswith("/blacklist remove "):
        try:
            user_id = int(message_text.split()[-1])
            if user_id in settings["blacklist"]:
                settings["blacklist"].remove(user_id)
                save_settings()
                await event.reply(f"✅ از لیست سیاه خارج کردن کاربر {user_id} انجام شد.")
        except ValueError:
            await event.reply("❗️ فرمت وارد شده صحیح نیست.")
    elif lower_text == "/blacklist list":
        if settings["blacklist"]:
            blacklist_str = "\n".join([str(uid) for uid in settings["blacklist"]])
            await event.reply(f"📃 کاربران موجود در لیست سیاه:\n{blacklist_str}")
        else:
            await event.reply("✅ لیست سیاه خالی است.")
    elif lower_text.startswith("/set_hours "):
        try:
            parts = message_text.split()
            start_time = parts[1].split("=")[1]
            end_time = parts[2].split("=")[1]
            settings["working_hours"] = {"start": start_time, "end": end_time}
            save_settings()
            await event.reply(f"⏲️ تعریف ساعت فعالیت ربات برای روزهای عادی تغییر کرد: {start_time} تا {end_time}")
        except Exception:
            await event.reply("⚠️ فرمت صحیح: `/set_hours start=08:00 end=18:00`")
    elif lower_text.startswith("/set_thursday "):
        try:
            parts = message_text.split()
            start_time = parts[1].split("=")[1]
            end_time = parts[2].split("=")[1]
            settings["thursday_hours"] = {"start": start_time, "end": end_time}
            save_settings()
            await event.reply(f"📅 تعریف ساعت فعالیت ربات برای روز پنج‌شنبه تغییر کرد: {start_time} تا {end_time}")
        except Exception:
            await event.reply("⚠️ فرمت صحیح: `/set_thursday start=08:00 end=14:00`")
    elif lower_text == "/disable_friday":
        settings["disable_friday"] = True
        save_settings()
        await event.reply("🚫 تعطیل کردن فعالیت ربات در روز جمعه.")
    elif lower_text == "/enable_friday":
        settings["disable_friday"] = False
        save_settings()
        await event.reply("✅ اجازه فعالیت مجدد ربات در روز جمعه.")
    elif lower_text.startswith("/set_lunch_break "):
        try:
            parts = message_text.split()
            start_time = parts[1].split("=")[1]
            end_time = parts[2].split("=")[1]
            settings["lunch_break"] = {"start": start_time, "end": end_time}
            save_settings()
            await event.reply(f"🍽 تعیین بازه زمانی برای استراحت ناهار تغییر کرد: {start_time} تا {end_time}")
        except Exception:
            await event.reply("⚠️ فرمت صحیح: `/set_lunch_break start=12:00 end=13:00`")
    elif lower_text.startswith("/set_query_limit "):
        try:
            parts = message_text.split()
            new_limit = int(parts[1].split("=")[1])
            QUERY_LIMIT = new_limit
            await event.reply(f"🔢 تغییر تعداد دفعات استعلام در 24 ساعت به {new_limit} انجام شد.")
        except Exception:
            await event.reply("⚠️ فرمت صحیح: `/set_query_limit limit=50`")
    elif lower_text.startswith("/set_delivery_info_before "):
        new_text = message_text[len("/set_delivery_info_before "):]
        settings.setdefault("delivery_info", {})["before_15"] = new_text
        save_settings()
        await event.reply("📦 متن اطلاعات تحویل کالا برای قبل از ساعت تغییر یافت.")
    elif lower_text.startswith("/set_delivery_info_after "):
        new_text = message_text[len("/set_delivery_info_after "):]
        settings.setdefault("delivery_info", {})["after_15"] = new_text
        save_settings()
        await event.reply("📦 متن اطلاعات تحویل کالا برای بعد از ساعت تغییر یافت.")
    elif lower_text.startswith("/set_changeover_hour "):
        try:
            parts = message_text.split()
            new_time = parts[1].split("=")[1]
            settings["changeover_hour"] = new_time
            save_settings()
            await event.reply(f"⏰ تنظیم ساعت تغییر متن تحویل کالا به {new_time} انجام شد.")
        except Exception:
            await event.reply("⚠️ فرمت صحیح: `/set_changeover_hour time=15:30`")
    elif lower_text.startswith("/set_main_group "):
        try:
            parts = message_text.split()
            new_id = int(parts[1].split("=")[1])
            settings["main_group_id"] = new_id
            save_settings()
            await event.reply(f"✅ گروه اصلی تنظیم شد: {new_id}")
        except Exception:
            await event.reply("⚠️ فرمت صحیح: `/set_main_group id=-1001234567890`")
    elif lower_text.startswith("/add_secondary_group "):
        try:
            parts = message_text.split()
            new_id = int(parts[1].split("=")[1])
            if new_id not in settings["secondary_group_ids"]:
                settings["secondary_group_ids"].append(new_id)
                save_settings()
                await event.reply(f"✅ گروه فرعی {new_id} اضافه شد.")
            else:
                await event.reply("⚠️ این گروه قبلاً اضافه شده است.")
        except Exception:
            await event.reply("⚠️ فرمت صحیح: `/add_secondary_group id=-1001234567890`")
    elif lower_text.startswith("/remove_secondary_group "):
        try:
            parts = message_text.split()
            rem_id = int(parts[1].split("=")[1])
            if rem_id in settings["secondary_group_ids"]:
                settings["secondary_group_ids"].remove(rem_id)
                save_settings()
                await event.reply(f"✅ گروه فرعی {rem_id} حذف شد.")
            else:
                await event.reply("⚠️ این گروه در لیست گروه‌های فرعی وجود ندارد.")
        except Exception:
            await event.reply("⚠️ فرمت صحیح: `/remove_secondary_group id=-1001234567890`")
    elif lower_text.startswith("/set_admin_group "):
        try:
            parts = message_text.split()
            new_id = int(parts[1].split("=")[1])
            settings["admin_group_ids"] = [new_id]
            save_settings()
            await event.reply(f"✅ گروه مدیریت تنظیم شد: {new_id}")
        except Exception:
            await event.reply("⚠️ فرمت صحیح: `/set_admin_group id=-1001234567890`")
    elif lower_text.startswith("/add_admin_group "):
        try:
            parts = message_text.split()
            new_id = int(parts[1].split("=")[1])
            if new_id not in settings["admin_group_ids"]:
                settings["admin_group_ids"].append(new_id)
                save_settings()
                await event.reply(f"✅ گروه مدیریت {new_id} اضافه شد.")
            else:
                await event.reply("⚠️ این گروه قبلاً اضافه شده است.")
        except Exception:
            await event.reply("⚠️ فرمت صحیح: `/add_admin_group id=-1001234567890`")
    elif lower_text.startswith("/remove_admin_group "):
        try:
            parts = message_text.split()
            rem_id = int(parts[1].split("=")[1])
            if rem_id in settings["admin_group_ids"]:
                settings["admin_group_ids"].remove(rem_id)
                save_settings()
                await event.reply(f"✅ گروه مدیریت {rem_id} حذف شد.")
            else:
                await event.reply("⚠️ این گروه در لیست گروه‌های مدیریت وجود ندارد.")
        except Exception:
            await event.reply("⚠️ فرمت صحیح: `/remove_admin_group id=-1001234567890`")
    elif lower_text == "/list_groups":
        main_group = settings.get("main_group_id")
        secondary = settings.get("secondary_group_ids", [])
        admin = settings.get("admin_group_ids", [])
        msg = f"گروه اصلی: {main_group}\nگروه‌های فرعی: {', '.join(map(str, secondary))}\nگروه‌های مدیریت: {', '.join(map(str, admin))}"
        await event.reply(msg)
    elif lower_text == "/status":
        now = datetime.now()
        cache_age = "داده‌های کش موجود نیست"
        if last_cache_update:
            diff = now - last_cache_update
            cache_age = f"{diff.seconds // 60} دقیقه پیش به‌روز شده"
        status_message = (
            "📊 وضعیت ربات:\n"
            f"وضعیت: {'روشن' if settings['enabled'] else 'خاموش'}\n"
            f"زمان به‌روزرسانی کش: {cache_age}\n"
            f"تعداد کل استعلام‌های پردازش‌شده: {total_queries}\n"
        )
        await event.reply(status_message)

# ================= راه‌اندازی اصلی =================
async def main():
    asyncio.create_task(update_cache_periodically())
    await client.start(phone=PHONE_NUMBER)
    print("Telegram Bot is running...\nDeveloped by Mohammad Baghshomali | Website: mbaghshomali.ir")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
