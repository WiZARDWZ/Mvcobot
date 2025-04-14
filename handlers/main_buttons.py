from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from handlers.inventory import handle_inventory_callback
from keyboard import main_menu_reply

async def handle_main_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if "استعلام" in text:
        await handle_inventory_callback(update, context)
        return ConversationHandler.END

    elif "تماس" in text:
        await update.message.reply_text(
            "📞 تماس با ما:\nبرای ارتباط با پشتیبانی با شماره زیر تماس بگیرید:\n\n۰۹۱۲۱۲۳۴۵۶۷",
            reply_markup=main_menu_reply()
        )
        return ConversationHandler.END

    else:
        await update.message.reply_text(
            "🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.",
            reply_markup=main_menu_reply()
        )
