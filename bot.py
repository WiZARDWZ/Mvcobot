import asyncio
import logging
import re
import os
from datetime import datetime
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PicklePersistence,   # ✅ Persistence
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
    refresh_inventory_cache_once
)
from handlers.main_buttons import (
    handle_main_buttons,
    show_main_menu_from_callback
)
from handlers.admin import (
    disable_bot, enable_bot, blacklist_add, blacklist_remove,
    blacklist_list, set_hours, set_thursday, disable_friday,
    enable_friday, set_query_limit,
    set_delivery_before, set_delivery_after,
    set_changeover_hour, status, log_user,
    refresh_cache_command,
)
from database.connector_bot import log_message, is_blacklisted

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

ADMIN_GROUP_ID = -1002391888673  # admin group chat id


def _state_file() -> str:
    """Persistent file path for conversation & user_data state."""
    base = os.path.join(os.getenv("LOCALAPPDATA", "."), "mvcobot")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "bot_state.pkl")


async def forward_and_log(update, context: ContextTypes.DEFAULT_TYPE):
    """Forward selected private messages to admin group + log them."""
    message = update.message
    if not message or message.from_user.is_bot:
        return
    user = message.from_user
    chat = update.effective_chat
    text = message.text or ""
    if chat.type == "private":
        try:
            short_text = (text or "")[:1000]
            log_message(user.id, chat.id, "in", short_text)
            if not is_blacklisted(user.id):
                is_command = bool(text and text.strip().startswith("/"))
                looks_like_code = bool(re.search(r"\b[A-Za-z0-9]{5}(?:[-_/\. ]+)?[A-Za-z0-9]{5}\b", text or ""))
                if is_command or looks_like_code:
                    await context.bot.forward_message(
                        chat_id=ADMIN_GROUP_ID,
                        from_chat_id=chat.id,
                        message_id=message.message_id
                    )
        except Exception as e:
            print("ERROR: forward/log failed:", e)


async def unknown_message(update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        await update.message.reply_text("🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.")


def main():
    async def _post_init(application):
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{start_time}] MVCO BOT starting up...")

        try:
            await refresh_inventory_cache_once()
        except Exception as e:
            print(f"[{start_time}] WARNING: Initial cache refresh failed: {e}")

        if application.job_queue:
            async def _tick_refresh(context: ContextTypes.DEFAULT_TYPE):
                await refresh_inventory_cache_once()
            application.job_queue.run_repeating(_tick_refresh, interval=20 * 60, first=20 * 60)
        else:
            print("WARN: JobQueue not available; using background loop for cache refresh.")
            async def _bg_loop():
                while True:
                    try:
                        await refresh_inventory_cache_once()
                    except Exception as e:
                        logging.exception("Cache refresh background loop error:", exc_info=e)
                    await asyncio.sleep(20 * 60)
            application.create_task(_bg_loop())

    # ✅ Persistence: keep conversations & user_data across restarts
    persistence = PicklePersistence(filepath=_state_file(), update_interval=30)

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .persistence(persistence)   # ✅ enable persistence
        .post_init(_post_init)
        .build()
    )

    # core handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_and_log), group=-1)
    app.add_handler(CommandHandler("start", start))

    # ✅ Make conversation persistent (with a name)
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 استعلام قطعه$"), handle_inventory_callback)],
        states={
            AWAITING_PART_CODE: [
                CallbackQueryHandler(show_main_menu_from_callback, pattern="^main_menu$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inventory_input),
                CommandHandler("cancel", cancel),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
        name="inventory_conv",     # ✅ required for persistence
        persistent=True            # ✅ required for persistence
    )
    app.add_handler(conv_handler)

    # Global handler so inline "back to main" works anywhere
    app.add_handler(CallbackQueryHandler(show_main_menu_from_callback, pattern="^main_menu$"), group=1)

    # main text buttons
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_buttons))

    # admin commands
    app.add_handler(CommandHandler("disable_bot", disable_bot))
    app.add_handler(CommandHandler("enable_bot", enable_bot))
    app.add_handler(CommandHandler("blacklist_add", blacklist_add))
    app.add_handler(CommandHandler("blacklist_remove", blacklist_remove))
    app.add_handler(CommandHandler("blacklist_list", blacklist_list))
    app.add_handler(CommandHandler("set_hours", set_hours))
    app.add_handler(CommandHandler("set_thursday", set_thursday))
    app.add_handler(CommandHandler("disable_friday", disable_friday))
    app.add_handler(CommandHandler("enable_friday", enable_friday))
    app.add_handler(CommandHandler("set_query_limit", set_query_limit))
    app.add_handler(CommandHandler("set_delivery_before", set_delivery_before))
    app.add_handler(CommandHandler("set_delivery_after", set_delivery_after))
    app.add_handler(CommandHandler("set_changeover_hour", set_changeover_hour))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("log", log_user))
    app.add_handler(CommandHandler("refresh_cache", refresh_cache_command))

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] MVCO BOT STARTED")
    app.run_polling()  # اگر خواستی: drop_pending_updates=False
    # app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
