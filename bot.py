# -*- coding: utf-8 -*-
import asyncio
import logging
import re
import os
import sys
import time
from datetime import datetime

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PicklePersistence,   # ✅ Persistence
    filters,
    ConversationHandler,
    ContextTypes,
)
from telegram.error import BadRequest, NetworkError, TimedOut, RetryAfter, Conflict

# ⚠️ PTB v20+: برای کنترل تایم‌اوت‌های شبکه
try:
    from telegram.request import HTTPXRequest
except Exception:
    HTTPXRequest = None  # اگر نبود، بدون آن ادامه می‌دهیم

from config import BOT_TOKEN
from control_panel import start_control_panel_server
import control_panel.runtime as control_panel_runtime
from control_panel.logic import get_platform_snapshot
from dm_bot import get_dm_service

from handlers.start import start
from handlers.inventory import (
    handle_inventory_callback,
    handle_inventory_input,
    cancel,
    AWAITING_PART_CODE,
    refresh_inventory_cache_once,
)
from handlers.main_buttons import (
    handle_main_buttons,
    show_main_menu_from_callback,
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

# ⬇️ ایمن‌سازی: اگر wa_sync نبود، ربات تلگرام بالا بیاید و فقط هشدار بده
try:
    from handlers.wa_sync import register_wa_sync_handlers
    _HAS_WA_SYNC = True
except Exception as e:
    logging.warning("WA sync not available: %s", e)

    def register_wa_sync_handlers(app):  # fallback no-op
        logging.warning("register_wa_sync_handlers: skipped (wa_sync missing).")

    _HAS_WA_SYNC = False

# ⬇️ برای تضمین استارت واتساپ از post_init
try:
    from wa.manager import wa_controller
    _HAS_WA_MANAGER = True
except Exception as e:
    logging.warning("WA manager not available: %s", e)
    wa_controller = None
    _HAS_WA_MANAGER = False

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

# ⬇️ قابل‌پیکربندی از ENV / config (fallback به مقدار فعلی)
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "-1002391888673"))


def _state_file() -> str:
    """Cross-platform path for conversation & user_data persistence."""
    if os.name == "nt":  # Windows
        base_root = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA") or "."
    elif sys.platform == "darwin":  # macOS
        base_root = os.path.expanduser("~/Library/Application Support")
    else:  # Linux/Unix
        base_root = os.getenv("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    base = os.path.join(base_root, "mvcobot")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "bot_state.pkl")


async def forward_and_log(update, context: ContextTypes.DEFAULT_TYPE):
    """Forward selected private messages to admin group + log them (با تحمل خطاهای شبکه)."""
    try:
        message = getattr(update, "message", None)
        if not message or getattr(message.from_user, "is_bot", True):
            return

        chat = update.effective_chat
        if not chat or chat.type != "private":
            return

        text = message.text or ""
        user = message.from_user

        # Log short text (avoid huge payloads)
        short_text = text[:1000]
        try:
            log_message(user.id, chat.id, "in", short_text)
        except Exception as db_err:
            logging.warning("DB log failed: %s", db_err)

        if is_blacklisted(user.id):
            return

        # فقط پیام‌های مهم را فوروارد کن: فرمان‌ها یا چیزی که شبیه کد قطعه است
        is_command = bool(text and text.strip().startswith("/"))
        looks_like_code = bool(re.search(r"\b[A-Za-z0-9]{5}(?:[-_/\. ]+)?[A-Za-z0-9]{5}\b", text or ""))
        if is_command or looks_like_code:
            try:
                await context.bot.forward_message(
                    chat_id=ADMIN_GROUP_ID,
                    from_chat_id=chat.id,
                    message_id=message.message_id,
                )
            except (NetworkError, TimedOut, RetryAfter) as net_err:
                # در قطعی اینترنت، این بخش را نادیده بگیر و اجازه بده ربات به کارش ادامه دهد
                logging.warning("forward_message network issue (ignored): %s", net_err)
            except Exception as e:
                logging.error("forward_and_log->forward_message failed: %s", e)
    except Exception as e:
        logging.error("forward_and_log failed: %s", e)


async def unknown_message(update, context: ContextTypes.DEFAULT_TYPE):
    # اگر در گروه/سوپرگروه بود و پیام بی‌ربط بود
    try:
        if update.effective_chat and update.effective_chat.type != "private":
            await update.message.reply_text("🔸 لطفاً یکی از گزینه‌های منو را انتخاب کنید.")
    except (NetworkError, TimedOut, RetryAfter) as net_err:
        logging.warning("unknown_message send failed (ignored): %s", net_err)


# ✅ Error Handler جهانی: نذار Exception خام ربات را متوقف کند
async def _global_error_handler(update, context: ContextTypes.DEFAULT_TYPE):
    err = context.error
    try:
        msg = (str(err) or "").lower()

        # خطای رایج کلیک روی دکمه قدیمی:
        if isinstance(err, BadRequest) and (
            "query is too old" in msg
            or "query id is invalid" in msg
            or "query_id_invalid" in msg
        ):
            logging.warning("Ignoring old/invalid callback query.")
            return

        if isinstance(err, RetryAfter):
            # ریت‌لیمیت از سمت تلگرام
            sleep_for = getattr(err, "retry_after", 5) or 5
            logging.warning("Rate limited. Sleeping for %ss", sleep_for)
            await asyncio.sleep(sleep_for)
            return

        if isinstance(err, (TimedOut, NetworkError)):
            # فقط لاگ کن؛ حلقهٔ run_polling خود را ریکاور می‌کند یا توسط حلقهٔ بیرونی ری‌استارت می‌شود
            logging.warning("Transient network error: %s", err)
            return

        if isinstance(err, Conflict):
            # Bot در جای دیگری هم در حال اجراست
            logging.error("Another instance is running (Conflict). Stop this one.")
            # اجازه بده بالادستی تصمیم بگیرد؛ اینجا فقط لاگ
            return

        # لاگ با استک‌تریس کامل برای سایر خطاها
        logging.error("Unhandled error in update handler", exc_info=err)
    except Exception:
        logging.exception("Error while handling an error!")


async def _post_init(application):
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{start_time}] MVCO BOT starting up...")

    try:
        loop = asyncio.get_running_loop()
        control_panel_runtime.register_event_loop(loop)
    except Exception as exc:
        logging.debug("Failed to register control panel runtime loop: %s", exc, exc_info=True)

    active = True
    platforms = {"telegram": True, "whatsapp": True}
    try:
        active, platforms = get_platform_snapshot()
        control_panel_runtime.apply_platform_states(platforms, active=active)
    except Exception as exc:
        logging.debug("Failed to apply initial platform states: %s", exc, exc_info=True)

    # --- ریفرش اولیه کش انبار
    try:
        await refresh_inventory_cache_once()
        print("[CACHE] initial refresh done.")
    except Exception as e:
        print(f"[{start_time}] WARNING: Initial cache refresh failed: {e}")

    # --- ریفرش دوره‌ای کش
    if application.job_queue:
        async def _tick_refresh(context: ContextTypes.DEFAULT_TYPE):
            try:
                await refresh_inventory_cache_once()
                logging.info("[CACHE] periodic refresh OK")
            except Exception as e:
                logging.exception("Periodic cache refresh failed:", exc_info=e)

        application.job_queue.run_repeating(
            _tick_refresh, interval=20 * 60, first=20 * 60, name="inventory_cache_refresh"
        )

        # --- پایش سلامت شبکه (هر 60 ثانیه یک درخواست سبک)
        async def _net_health(_ctx: ContextTypes.DEFAULT_TYPE):
            try:
                await application.bot.get_me()
                logging.debug("[NET] get_me OK")
            except (TimedOut, NetworkError, RetryAfter) as net_err:
                logging.warning("[NET] health check issue: %s", net_err)

        application.job_queue.run_repeating(
            _net_health, interval=60, first=30, name="network_health_check"
        )
    else:
        print("WARN: JobQueue not available; using background loop for cache refresh & health.")

        async def _bg_loop():
            while True:
                try:
                    await refresh_inventory_cache_once()
                    logging.info("[CACHE] background refresh OK")
                except Exception as e:
                    logging.exception("Cache refresh background loop error:", exc_info=e)
                await asyncio.sleep(20 * 60)

        application.create_task(_bg_loop())

        async def _bg_net():
            while True:
                try:
                    await application.bot.get_me()
                except (TimedOut, NetworkError, RetryAfter) as net_err:
                    logging.warning("[NET] bg health issue: %s", net_err)
                await asyncio.sleep(60)

        application.create_task(_bg_net())

    # --- تضمین استارت واتساپ همین‌جا (حتی اگر Job اولیه miss شود)
    if _HAS_WA_MANAGER and wa_controller is not None:
        if active and platforms.get("whatsapp", True):
            print("[WA] start requested (runtime sync)")
        else:
            print("[WA] skipped start (disabled by settings)")


def _build_application() -> "Application":
    """Application با تایم‌اوت‌های معقول شبکه ساخته می‌شود تا گیر نکند."""
    # ✅ Persistence: keep conversations & user_data across restarts
    persistence = PicklePersistence(filepath=_state_file(), update_interval=30)

    builder = ApplicationBuilder().token(BOT_TOKEN).persistence(persistence).post_init(_post_init)

    # اگر HTTPXRequest موجود بود، تایم‌اوت‌ها را تنظیم کن (برای قطعی‌های ایران کمک می‌کند)
    if HTTPXRequest is not None:
        try:
            request = HTTPXRequest(
                read_timeout=60.0,     # حداکثر ۶۰ ثانیه برای پاسخ
                connect_timeout=30.0,  # اتصال‌های کند پشت فیلتر
                pool_timeout=30.0,     # انتظار برای گرفتن کانکشن از پول
            )
            builder = builder.request(request)
        except Exception as e:
            logging.warning("HTTPXRequest setup failed (continue with defaults): %s", e)

    app = builder.build()

    # ⬅️ ثبت Error Handler جهانی
    app.add_error_handler(_global_error_handler)

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
        persistent=True,           # ✅ required for persistence
    )
    app.add_handler(conv_handler)

    # Global handler so inline "back to main" works anywhere
    app.add_handler(CallbackQueryHandler(show_main_menu_from_callback, pattern="^main_menu$"), group=1)

    # main text buttons
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_buttons))

    # (اختیاری) Unknowns در گروه‌ها
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, unknown_message), group=2)

    # admin commands (موجود)
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

    # ✅ واتساپ را کنار تلگرام راه‌اندازی و دستورات WA را رجیستر کن
    register_wa_sync_handlers(app)

    return app


def _run_polling_resilient(app):
    """
    اجرای مقاوم در برابر قطعی اینترنت:
    - اگر run_polling به خطای شبکه/تایم‌اوت برخورد کرد، با backoff نمایی ری‌استارت می‌شود.
    """
    backoff = 5  # ثانیه
    max_backoff = 300  # سقف 5 دقیقه
    attempt = 0

    while True:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] MVCO BOT STARTED")
            # ⬅️ مهم: آپدیت‌های معوقه (قدیمی) را در استارت دور بریز
            app.run_polling(drop_pending_updates=True, allowed_updates=None)
            # اگر به صورت طبیعی خارج شد، از حلقه بیرون برو (مثلاً SIGTERM)
            print("run_polling finished gracefully.")
            break
        except RetryAfter as ra:
            wait_s = getattr(ra, "retry_after", backoff) or backoff
            logging.warning("RetryAfter from Telegram. Sleeping for %ss", wait_s)
            time.sleep(wait_s)
            backoff = min(max_backoff, max(5, backoff * 2))
            attempt += 1
            continue
        except (TimedOut, NetworkError) as ne:
            logging.warning("Network issue in run_polling: %s", ne)
            logging.info("Reconnecting in %ss (attempt %s)...", backoff, attempt + 1)
            time.sleep(backoff)
            backoff = min(max_backoff, backoff * 2)  # backoff نمایی تا سقف
            attempt += 1
            continue
        except Conflict as c:
            # Bot جای دیگری در حال اجراست — بهتر است به صورت امن خارج شویم
            logging.error("Conflict: another instance is running. Exiting. %s", c)
            break
        except Exception as e:
            # سایر خطاهای غیرمنتظره: کمی صبر کن و دوباره
            logging.exception("Unexpected error in run_polling (will retry): %s", e)
            time.sleep(min(max_backoff, backoff))
            backoff = min(max_backoff, backoff * 2)
            attempt += 1
            continue


def main():
    port = int(os.getenv("CONTROL_PANEL_PORT", "8080"))
    server = start_control_panel_server(port=port)
    if server:
        print(f"[WebControl] Control panel serving on port {port}")
    else:
        print("[WebControl] Control panel server failed to start.")

    dm_service = get_dm_service()
    dm_service.start()

    app = _build_application()
    try:
        _run_polling_resilient(app)
    finally:
        dm_service.stop()
        if server:
            try:
                server.shutdown()
            except Exception:
                pass


if __name__ == "__main__":
    main()
