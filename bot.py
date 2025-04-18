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
    set_changeover_hour, status
)
from database.connector_bot import log_message, is_blacklisted

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

ADMIN_GROUP_ID = -1002391888673  # آیدی گروه مدیریت

# ✅ فوروارد و لاگ پیام کاربران به گروه مدیریت
async def forward_and_log(update, context):
    message = update.message
    if not message or message.from_user.is_bot:
        return

    user = message.from_user
    chat = update.effective_chat
    text = message.text or ""

    # فقط پیام‌های چت خصوصی کاربران
    if chat.type == "private":
        try:
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
    if update.effective_chat.type != "private":
        await update.message.reply_text("🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.")

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # 🟡 لاگ و فوروارد پیام‌ها (اولویت بالا)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, forward_and_log),
        group=-1
    )

    # 🟢 فرمان /start
    app.add_handler(CommandHandler("start", start))

    # 🔵 مکالمه استعلام
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 استعلام قطعه$"), handle_inventory_callback)],
        states={AWAITING_PART_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inventory_input)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    app.add_handler(conv_handler)

    # 🟣 بازگشت به منو اصلی
    app.add_handler(CallbackQueryHandler(show_main_menu_from_callback, pattern="^main_menu$"))

    # 🟠 مدیریت دکمه‌های دیگر
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_buttons))

    # ⚙️ دستورات مدیریتی فقط در گروه مدیر
    app.add_handler(CommandHandler("disable", disable_bot))
    app.add_handler(CommandHandler("enable", enable_bot))
    app.add_handler(CommandHandler("blacklist", blacklist_add, filters=filters.Regex("^/blacklist add")))
    app.add_handler(CommandHandler("blacklist", blacklist_remove, filters=filters.Regex("^/blacklist remove")))
    app.add_handler(CommandHandler("blacklist", blacklist_list, filters=filters.Regex("^/blacklist list")))
    app.add_handler(CommandHandler("set_hours", set_hours))
    app.add_handler(CommandHandler("set_thursday", set_thursday))
    app.add_handler(CommandHandler("disable_friday", disable_friday))
    app.add_handler(CommandHandler("enable_friday", enable_friday))
    app.add_handler(CommandHandler("set_lunch_break", set_lunch_break))
    app.add_handler(CommandHandler("set_query_limit", set_query_limit))
    app.add_handler(CommandHandler("set_delivery_info_before", set_delivery_before))
    app.add_handler(CommandHandler("set_delivery_info_after", set_delivery_after))
    app.add_handler(CommandHandler("set_changeover_hour", set_changeover_hour))
    app.add_handler(CommandHandler("status", status))

    # 🕒 به‌روزرسانی کش
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(update_inventory_cache())

    print("🤖 ربات فعال شد...")
    app.run_polling()

if __name__ == "__main__":
    main()
