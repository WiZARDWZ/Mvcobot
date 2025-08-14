# main_buttons.py
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database.connector_bot import get_setting
from keyboard import main_menu_reply  # استفاده از منوی اصلی استاندارد

async def handle_main_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("enabled") != "true":
        await update.message.reply_text("⛔️ ربات غیرفعال است. لطفاً بعداً مراجعه کنید.")
        return ConversationHandler.END

    text = update.message.text.strip()

    if "استعلام" in text:
        from handlers.inventory import handle_inventory_callback
        return await handle_inventory_callback(update, context)

    elif "تماس" in text:
        await update.message.reply_text(
            "📞 راه‌های ارتباط با ما 📞\n\n"
            "• واتساپ: 09025029290\n"
            "• تلگرام: @mvcoparts1\n"
            "• تلفن دفتر: 33993328 – 33992833\n\n"
            "ما همواره آماده پاسخگویی به سوالات و نیازهای شما هستیم!",
            reply_markup=main_menu_reply()
        )
        return ConversationHandler.END

    elif "تحویل" in text:
        await update.message.reply_text(
            "🚚 نحوه تحویل کالا 🚚\n\n"
            "1️⃣ تحویل حضوری در دفتر بازار:\n"
            "   • شنبه تا چهارشنبه: ساعت 16:00\n"
            "   • پنج‌شنبه: ساعت 12:30\n\n"
            "2️⃣ ارسال فوری از انبار 🛵:\n"
            "   • زمان تقریبی تحویل: 45 دقیقه در تمام ساعات کاری\n"
            "   • هزینه پیک بر عهده مشتری است\n\n"
            "با آرزوی تجربهٔ خریدی دلپذیر برای شما! ",
            reply_markup=main_menu_reply()
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
            "منتظر خدمت‌رسانی به شما هستیم! ",
            reply_markup=main_menu_reply()
        )
        return ConversationHandler.END

    else:
        await update.message.reply_text(
            "🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.",
            reply_markup=main_menu_reply()
        )
        return ConversationHandler.END


async def show_main_menu_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # حذف پیام اینلاین قبلی (اگه بتونه)
    try:
        await query.message.delete()
    except Exception as e:
        print("❌ Error deleting inline menu message:", e)

    # ارسال پیام منوی اصلی با کیبورد ReplyKeyboardMarkup
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="🏠 به منوی اصلی برگشتید. لطفاً یک گزینه را انتخاب کنید:",
        reply_markup=main_menu_reply()
    )

    return ConversationHandler.END
