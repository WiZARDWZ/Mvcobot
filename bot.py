import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler
)
from config import BOT_TOKEN
from handlers.start import start
from handlers.inventory import (
    handle_inventory_callback,
    handle_inventory_input,
    cancel,
    AWAITING_PART_CODE,
    update_inventory_cache
)
from handlers.main_buttons import handle_main_buttons, show_main_menu_from_callback
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def unknown_message(update, context):
    await update.message.reply_text("🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.")

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # /start
    app.add_handler(CommandHandler("start", start))

    # مکالمه استعلام قطعه
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 استعلام قطعه$"), handle_inventory_callback)],
        states={
            AWAITING_PART_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inventory_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)

    # بازگشت به منو اصلی
    app.add_handler(CallbackQueryHandler(show_main_menu_from_callback, pattern="^main_menu$"))

    # مدیریت دکمه‌های اصلی (غیر از استعلام)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_buttons))

    # پیام‌های ناشناس
    app.add_handler(MessageHandler(filters.ALL, unknown_message))

    # اجرای کش
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(update_inventory_cache())

    print("🤖 ربات فعال شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
