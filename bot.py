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
from handlers.admin import (
    disable_bot, enable_bot, blacklist_add, blacklist_remove,
    blacklist_list, set_hours, set_thursday, disable_friday,
    enable_friday, set_lunch_break, set_query_limit,
    set_delivery_before, set_delivery_after,
    set_changeover_hour, status, log_user
)
from database.connector_bot import log_message, is_blacklisted

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ADMIN_GROUP_ID = -1002391888673  # آیدی گروه مدیریت

# ✅ فوروارد و لاگ پیام کاربران
async def forward_and_log(update, context):
    message = update.message
    if not message or message.from_user is None or message.from_user.is_bot:
        return
    try:
        user = message.from_user
        chat = update.effective_chat
        text = message.text or ""

        if chat.type == "private":
            log_message(user.id, chat.id, "in", text)
            if not is_blacklisted(user.id):
                await context.bot.forward_message(
                    chat_id=ADMIN_GROUP_ID,
                    from_chat_id=chat.id,
                    message_id=message.message_id
                )
    except Exception as e:
        print("❌ خطا در فوروارد یا لاگ پیام:", e)

# 🔹 پیام‌های ناشناس در گروه‌ها
async def unknown_message(update, context):
    if update.effective_chat and update.effective_chat.type != "private":
        await update.message.reply_text("🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_and_log), group=-1)

    app.add_handler(CommandHandler("start", start))

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 استعلام قطعه$"), handle_inventory_callback)],
        states={AWAITING_PART_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inventory_input)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(conv_handler)

    app.add_handler(CallbackQueryHandler(show_main_menu_from_callback, pattern="^main_menu$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_buttons))

    # دستورات مدیریتی
    admin_cmds = [
        ("disable", disable_bot),
        ("enable", enable_bot),
        ("blacklist_add", blacklist_add),
        ("blacklist_remove", blacklist_remove),
        ("blacklist_list", blacklist_list),
        ("set_hours", set_hours),
        ("set_thursday", set_thursday),
        ("disable_friday", disable_friday),
        ("enable_friday", enable_friday),
        ("set_lunch_break", set_lunch_break),
        ("set_query_limit", set_query_limit),
        ("set_delivery_info_before", set_delivery_before),
        ("set_delivery_info_after", set_delivery_after),
        ("set_changeover_hour", set_changeover_hour),
        ("status", status),
        ("log", log_user)
    ]
    for cmd, handler in admin_cmds:
        app.add_handler(CommandHandler(cmd, handler))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(update_inventory_cache())

    print("🤖 ربات فعال شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
