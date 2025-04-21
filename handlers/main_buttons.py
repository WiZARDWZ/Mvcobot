from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

def get_main_menu():
    keyboard = [
        ["🔍 استعلام قطعه"],
        ["📝 نحوه ثبت سفارش", "🚚 نحوه تحویل"],
        ["📞 تماس با ما"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def handle_main_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "استعلام" in text:
        from handlers.inventory import handle_inventory_callback
        return await handle_inventory_callback(update, context)

    elif "تماس" in text:
        await update.message.reply_text(
            "📞 راه‌های ارتباط با ما 📞\n\n"
            "• واتساپ و تلگرام: 09025029290\n"
            "• تلفن دفتر: 33993328 – 33992833\n\n"
            "ما همواره آماده پاسخگویی به سوالات و نیازهای شما هستیم! 🤝",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    elif "تحویل" in text:
        await update.message.reply_text(
            "🚚 نحوه تحویل کالا 🚚\n\n"
            "️⃣ تحویل حضوری در دفتر بازار:\n"
            "   • شنبه تا چهارشنبه: ساعت ۱۶:۰۰\n"
            "   • پنج‌شنبه: ساعت ۱۲:۳۰\n\n"
            "️⃣ ارسال فوری از انبار 🛵:\n"
            "   • زمان تقریبی تحویل: ۶۰ دقیقه در تمام ساعات کاری\n"
            "   • هزینه پیک بر عهده مشتری است\n\n"
            "با آرزوی تجربهٔ خریدی دلپذیر برای شما! 🤝",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    elif "ثبت سفارش" in text:
        await update.message.reply_text(
            "🛒 ثبت سفارش قطعات 🛒\n\n"
            "1️⃣ ابتدا از بخش 🔍 «استعلام قطعه»، نام یا کد قطعهٔ مورد نظرتان را جست‌وجو کنید.\n"
            "2️⃣ پس از مشاهده قیمت، برند و موجودی، با تیم پشتیبانی جهت صدور فاکتور هماهنگ شوید.\n\n"
            "📞 راه‌های ارتباط با ما:\n"
            "• واتساپ و تلگرام: 09025029290\n"
            "• تلفن دفتر: 33993328 – 33992833\n\n"
            "منتظر خدمت‌رسانی به شما هستیم! 🤝",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    else:
        await update.message.reply_text(
            "🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

async def show_main_menu_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # حذف پیام قبلی (اگر پیام از نوع دکمه اینلاین بود)
    try:
        await query.message.delete()
    except Exception as e:
        print("❌ خطا در حذف پیام دکمه منو:", e)

    # ارسال پیام منوی اصلی
    await query.message.chat.send_message(
        "🏠 به منوی اصلی برگشتید. لطفاً یک گزینه را انتخاب کنید:",
        reply_markup=get_main_menu()
    )

    return ConversationHandler.END
