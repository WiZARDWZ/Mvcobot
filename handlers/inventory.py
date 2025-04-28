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
        await update.message.reply_text(
            "⛔️ شما در لیست سیاه هستید. لطفاً برای رفع مشکل با پشتیبانی تماس بگیرید."
        )
        return ConversationHandler.END

    # خواندن تنظیمات ساعات کاری
    wk_start = get_setting("working_start") or "08:00"
    wk_end   = get_setting("working_end")   or "18:00"
    th_start = get_setting("thursday_start") or "08:00"
    th_end   = get_setting("thursday_end")   or "12:30"

    # تشخیص روز هفته و تعیین بازه امروز
    weekday = datetime.now().weekday()  # Mon=0 ... Thu=3
    now_time = datetime.now().time()
    if weekday == 3:  # پنجشنبه
        today_start, today_end = th_start, th_end
    else:
        today_start, today_end = wk_start, wk_end

    # اگر خارج از ساعت کاری باشیم
    if not (datetime.strptime(today_start, "%H:%M").time() <= now_time < datetime.strptime(today_end, "%H:%M").time()):
        await update.message.reply_text(
            f"⏰ ساعات کاری ربات:\n"
            f"  • شنبه تا چهارشنبه: {wk_start} تا {wk_end}\n"
            f"  • پنجشنبه: {th_start} تا {th_end}\n\n"
            "لطفاً در این بازه‌ها برای استعلام تلاش کنید."
        )
        return ConversationHandler.END

    # ارسال پیام اولیه و ذخیره شناسه آن
    sent = await update.message.reply_text("🔍 لطفاً کد قطعه را وارد کنید:")
    context.user_data["last_prompt_id"] = sent.message_id
    return AWAITING_PART_CODE


async def handle_inventory_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    uid = update.effective_user.id
    if is_blacklisted(uid):
        await update.message.reply_text("⛔️ شما در لیست سیاه هستید.")
        return ConversationHandler.END

    # بررسی روز و ساعات کاری (شنبه–چهارشنبه + پنج‌شنبه، و جمعه غیرفعال)
    wk_start = get_setting("working_start") or "08:00"
    wk_end   = get_setting("working_end")   or "18:00"
    th_start = get_setting("thursday_start") or "08:00"
    th_end   = get_setting("thursday_end")   or "12:30"
    weekday  = datetime.now().weekday()  # 0=Mon ... 4=Fri
    now_time = datetime.now().time()

    is_workday = (
        (weekday in (0,1,2) and datetime.strptime(wk_start, "%H:%M").time() <= now_time < datetime.strptime(wk_end, "%H:%M").time())
        or
        (weekday == 3 and datetime.strptime(th_start, "%H:%M").time() <= now_time < datetime.strptime(th_end, "%H:%M").time())
    )
    if weekday == 4 or not is_workday:
        await update.message.reply_text(
            f"⏰ ساعات کاری ربات:\n"
            f"  • شنبه تا چهارشنبه: {wk_start} تا {wk_end}\n"
            f"  • پنجشنبه: {th_start} تا {th_end}\n\n"
            "لطفاً در این بازه‌ها برای استعلام تلاش کنید."
        )
        return ConversationHandler.END

    # آماده‌سازی متن تحویل
    before         = get_setting("delivery_before") or "🚚 تحویل کالا هر روز ساعت 16 و پنجشنبه‌ها 12:30"
    after          = get_setting("delivery_after")  or "🛵 ارسال مستقیم از انبار (حدود 60 دقیقه)"
    changeover_str = get_setting("changeover_hour") or "15:00"
    changeover     = datetime.strptime(changeover_str, "%H:%M").time()
    delivery_info  = before if now_time < changeover else after

    # تبدیل اعداد فارسی به انگلیسی و پاکسازی کنترل‌ها
    raw_text = update.message.text.strip()
    raw_text = raw_text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    raw_text = re.sub(r'[\u200E\u200F\u202A-\u202E\u2066-\u2069\u200B]', '', raw_text)

    lines  = [ln.strip() for ln in re.split(r'[\r\n]+', raw_text) if ln.strip()]
    pattern = r'^[A-Za-z0-9]{5}[-_/\. ]?[A-Za-z0-9]{2,5}$'
    valid   = [ln for ln in lines if re.fullmatch(pattern, ln)]
    invalid = [ln for ln in lines if not re.fullmatch(pattern, ln)]

    seen = set()
    for ln in valid:
        norm = re.sub(r'[-_/\. ]', '', ln).upper()
        if norm in seen:
            continue
        seen.add(norm)

        products = _find_products(norm)
        if not products:
            # آماده‌سازی disp فقط با '-'
            clean = re.sub(r'[\s_/\.]', '', ln)
            disp  = clean if '-' in clean else clean[:5] + "-" + clean[5:]

            # پیام خطای plain text بدون LRM/escape
            await update.message.reply_text(f"⚠️ `{disp}` متأسفانه موجود نمی‌باشد.", parse_mode="Markdown")

            # پیشنهاد تکمیل اگر حداقل 7 کاراکتر باشد
            if len(norm) >= 7:
                candidates = [
                    it for it in _cached_inventory_data
                    if _normalize(it["شماره قطعه"]).startswith(norm)
                ]
                if candidates:
                    iran_code = candidates[0].get("Iran Code")
                    sug = next((it for it in candidates if it.get("Iran Code") == iran_code), candidates[0])

                    # پیام پیشنهاد کامل با Markdown
                    raw_code = sug["شماره قطعه"]
                    ltr_code = "\u200E" + raw_code + "\u200E"
                    code_md  = escape_markdown(ltr_code, version=1)
                    brand_md = escape_markdown(sug["برند"], version=1)
                    name_md  = escape_markdown(sug["نام کالا"], version=1)
                    try:
                        price_val = int(float(sug.get("فی فروش", 0)))
                        price_str = f"{price_val:,} ریال"
                    except:
                        price_str = str(sug.get("فی فروش", 0))
                    price_md    = escape_markdown(price_str, version=1)
                    iran_txt    = sug.get("Iran Code") or ""
                    iran_line   = f"توضیحات: {escape_markdown(iran_txt, version=1)}\n" if iran_txt else ""
                    delivery_md = escape_markdown(delivery_info, version=1)

                    await update.message.reply_text("🔍 آیا منظور شما این کالا است؟")
                    await update.message.reply_text(
                        f"*کد:* `{code_md}`\n"
                        f"*برند:* {brand_md}\n"
                        f"نام کالا: {name_md}\n"
                        f"*قیمت:* {price_md}\n"
                        f"{iran_line}"
                        f"\n{delivery_md}",
                        parse_mode="Markdown"
                    )
                    continue
        else:
            # نمایش کالاهای پیدا شده
            for item in products:
                raw_code = item["شماره قطعه"]
                ltr_code = "\u200E" + raw_code + "\u200E"
                code_md  = escape_markdown(ltr_code, version=1)
                brand_md = escape_markdown(item["برند"], version=1)
                name_md  = escape_markdown(item["نام کالا"], version=1)
                try:
                    price_val = int(float(item.get("فی فروش", 0)))
                    price_str = f"{price_val:,} ریال"
                except:
                    price_str = str(item.get("فی فروش", 0))
                price_md    = escape_markdown(price_str, version=1)
                iran_txt    = item.get("Iran Code") or ""
                iran_line   = f"توضیحات: {escape_markdown(iran_txt, version=1)}\n" if iran_txt else ""
                delivery_md = escape_markdown(delivery_info, version=1)

                await update.message.reply_text(
                    f"*کد:* `{code_md}`\n"
                    f"*برند:* {brand_md}\n"
                    f"نام کالا: {name_md}\n"
                    f"*قیمت:* {price_md}\n"
                    f"{iran_line}"
                    f"\n{delivery_md}",
                    parse_mode="Markdown"
                )

    # پیام فرمت نامعتبر
    if invalid:
        esc_invalid = [escape_markdown(x, version=1) for x in invalid]
        bad = ", ".join(f"`{x}`" for x in esc_invalid)
        await update.message.reply_text(
            "⛔️ فرمت یک یا چند کد نامعتبر است:\n"
            f"{bad}\n\n"
            "لطفاً فقط یکی از فرمت‌های زیر را وارد کنید:\n"
            "- `12345-12345`\n"
            "- `12345_12345`\n"
            "- `1234512345`\n"
            "- `12345/12345`\n"
            "- `12345 12345`\n"
            "- `12345.12345`\n\n"
            " ‼️*نیازی به وارد کردن کد رنگ نیست*",
            parse_mode="Markdown"
        )

    # حذف پیام راهنما و نمایش دکمه منوی جدید
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
