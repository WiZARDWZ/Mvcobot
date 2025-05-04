# utils/formatter.py
from datetime import datetime
from zoneinfo import ZoneInfo

# منطقهٔ زمانی تهران
_TEHRAN = ZoneInfo("Asia/Tehran")


def format_price(price):
    try:
        return f"{int(float(price)):,} ریال"
    except:
        return "نامشخص"


def get_delivery_info():
    now = datetime.now(_TEHRAN).time()
    changeover_time = datetime.strptime("15:00", "%H:%M").time()

    if now < changeover_time:
        return "تحویل کالا هر روز ساعت 16 و پنجشنبه‌ها ساعت 12:30 در دفتر بازار"
    else:
        return "‼️ ارسال مستقیم از انبار با زمان تقریبی تحویل 45 دقیقه امکان‌پذیر است (هزینه پیک دارد)"


def format_inventory_response(items):
    if not items:
        return "⚠️ موردی یافت نشد"

    response = "🔍 نتایج استعلام موجودی:\n\n"
    for item in items:
        response += (
            f"📌 کد کالا: {item['کد کالا']}\n"
            f"🏷️ نام کالا: {item['نام کالا']}\n"
            f"🏭 برند: {item.get('نام تامین کننده', 'نامشخص')}\n"
            f"📦 موجودی: {item['موجودی']}\n"
            f"💰 قیمت: {format_price(item['فی فروش'])}\n"
            f"🏠 انبار: {item['انبار']}\n"
            "------------------------\n"
        )

    response += f"\n⏰ {get_delivery_info()}"
    return response


def format_invoices_message(invoices: list) -> str:
    lines = []
    for inv in invoices:
        line = (
            f"<b>شماره فاکتور:</b> {inv.get('Number')}\n"
            f"<b>تاریخ:</b> {inv.get('Date')}\n"
            f"<b>مبلغ کل:</b> {inv.get('Price')}\n"
            "-----------------------"
        )
        lines.append(line)
    return "\n".join(lines)
