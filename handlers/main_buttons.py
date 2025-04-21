from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from handlers.inventory import handle_inventory_callback

# اصلی‌ترین منو
def get_main_menu():
    keyboard = [
        ["🔍 استعلام قطعه"],
        ["📦 نحوه تحویل", "📝 نحوه ثبت سفارش"],
        ["📞 تماس با ما"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def handle_main_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()

    if "استعلام" in text:
        await handle_inventory_callback(update, context)
        return ConversationHandler.END

    elif "تحویل" in text:
        await update.message.reply_text(
            "🚚 نحوه تحویل:\n"
            "- هر روز ساعت 16:00 در دفتر بازار\n"
            "- پنج‌شنبه‌ها ساعت 12:30\n"
            "- ارسال فوری با پیک نیز امکان‌پذیر است.",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    elif "سفارش" in text:
        await update.message.reply_text(
            "📝 نحوه ثبت سفارش:\n"
            "1. کد قطعه را ارسال کنید.\n"
            "2. قیمت دریافت شده را تأیید نمایید.\n"
            "3. سپس از طریق دکمه پرداخت یا تماس با پشتیبانی ادامه دهید.",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    elif "تماس" in text:
        await update.message.reply_text(
            "📞 تماس با ما:\n"
            "برای ارتباط با پشتیبانی با شماره زیر تماس بگیرید:\n"
            "۰۹۱۲۱۲۳۴۵۶۷",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    # همه‌ی پیام‌های دیگر هم منو را نشان می‌دهند و از مکالمه خارج می‌شوند
    await update.message.reply_text(
        "🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.",
        reply_markup=get_main_menu()
    )
    return ConversationHandler.END
