import asyncio
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler,
    ContextTypes
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
from database.connector_bot import log_message, is_blacklisted

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# آیدی گروه ادمین (حتماً منفی باشه!)
ADMIN_GROUP_ID = -1002391888673  # ← جایگزین کن با آیدی گروه واقعی

# فوروارد و لاگ پیام‌های کاربران (فقط برای private chat)
async def forward_and_log(update, context):
    message = update.message
    if not message:
        return

    # فقط در چت خصوصی
    if update.effective_chat.type != "private":
        return

    # اگر پیام از طرف خود ربات بود (پاسخ‌ها)، نادیده بگیر
    if message.from_user and message.from_user.is_bot:
        return

    user = message.from_user
    text = message.text or ""

    # ذخیره در جدول message_log
    try:
        log_message(user_id=user.id, chat_id=message.chat.id, direction="in", text=text)
    except Exception as e:
        print("❌ خطا در log_message:", e)

    # فوروارد به گروه ادمین اگر کاربر در بلک‌لیست نباشد
    try:
        if not is_blacklisted(user.id):
            await context.bot.forward_message(
                chat_id=ADMIN_GROUP_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
    except Exception as e:
        print("❌ خطا در فوروارد پیام به گروه ادمین:", e)


# پیام ناشناس (برای گروه‌ها)
async def unknown_message(update, context):
    if update.effective_chat.type != "private":
        await update.message.reply_text("🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.")

def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    # 🟡 اول لاگ پیام‌ها و فوروارد (فقط در private)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, forward_and_log),
        group=-1
    )

    # 🟢 دستور start
    app.add_handler(CommandHandler("start", start))

    # 🔵 مکالمه استعلام
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 استعلام قطعه$"), handle_inventory_callback)],
        states={
            AWAITING_PART_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inventory_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(conv_handler)

    # 🟣 دکمه بازگشت به منوی اصلی
    app.add_handler(CallbackQueryHandler(show_main_menu_from_callback, pattern="^main_menu$"))

    # 🟠 دکمه‌های دیگر
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_buttons))

    # 🔘 پیام‌های ناشناس (غیر از private)
    app.add_handler(MessageHandler(filters.ALL, unknown_message))

    # 🕒 به‌روزرسانی کش هر ۲۰ دقیقه
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(update_inventory_cache())

    print("🤖 ربات فعال شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
