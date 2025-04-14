import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
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
    update_inventory_cache  # اطمینان از ایمپورت صحیح
)
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # هندلر دستور /start
    app.add_handler(CommandHandler("start", start))

    # مکالمه برای استعلام
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 استعلام قطعه$"), handle_inventory_callback)],
        states={
            AWAITING_PART_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inventory_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)

    # هندل پیام‌های غیرمرتبط
    def unknown_message(update, context):
        update.message.reply_text("🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.")

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message))

    # ایجاد و ثبت Task به کمک asyncio برای به‌روزرسانی کش موجودی
    loop = asyncio.get_event_loop()
    loop.create_task(update_inventory_cache())

    print("🤖 ربات فعال شد...")
    app.run_polling()


if __name__ == "__main__":
    main()
