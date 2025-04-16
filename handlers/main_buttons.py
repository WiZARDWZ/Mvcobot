from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from handlers.inventory import handle_inventory_callback
from handlers.start import start

async def handle_main_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "استعلام" in text:
        await handle_inventory_callback(update, context)
        return ConversationHandler.END

    elif "تماس" in text:
        await update.message.reply_text(
            "📞 تماس با ما:\nبرای ارتباط با پشتیبانی با شماره زیر تماس بگیرید:\n\n۰۹۱۲۱۲۳۴۵۶۷",
            reply_markup=get_main_menu()
        )
        return ConversationHandler.END

    else:
        await update.message.reply_text(
            "🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.",
            reply_markup=get_main_menu()
        )

async def show_main_menu_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()

        reply_markup = get_main_menu()
        await update.callback_query.message.reply_text(
            "🏠 به منوی اصلی برگشتید. لطفاً یک گزینه را انتخاب کنید:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END


def get_main_menu():
    keyboard = [
        ["🔍 استعلام قطعه"],
        ["🧾 فاکتور", "💳 پرداخت"],
        ["🛒 سبد خرید", "📊 موجودی حساب"],
        ["📝 ثبت‌نام"],
        ["📞 تماس با ما"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
