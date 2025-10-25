# handlers/wa_sync.py
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from wa.manager import wa_controller

if TYPE_CHECKING:  # pragma: no cover - hints only
    from telegram.ext import Application

# اگر احراز هویت جدا دارید از همون استفاده کن
try:
    from handlers.admin import is_authorized, ADMIN_GROUP_ID  # type: ignore
except Exception:
    ADMIN_GROUP_ID = None
    def is_authorized(chat_id: int) -> bool:  # type: ignore
        return True if ADMIN_GROUP_ID is None else (chat_id == ADMIN_GROUP_ID)

async def _guard(update: Update) -> bool:
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not is_authorized(chat_id):
        if update.message:
            await update.message.reply_text("⛔️ دسترسی ندارید.")
        return False
    return True

# -------- دستورات مدیریت واتساپ ----------
async def wa_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    wa_controller.enable()
    await wa_controller.start()
    await update.message.reply_text("✅ واتساپ فعال شد و شروع به اسکن می‌کند.")

async def wa_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    await wa_controller.stop()
    wa_controller.disable()
    await update.message.reply_text("🟡 واتساپ متوقف و غیرفعال شد.")

async def wa_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    await wa_controller.restart()
    await update.message.reply_text("♻️ واتساپ ری‌استارت شد.")

async def wa_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    await update.message.reply_text(f"📊 وضعیت واتساپ:\n{wa_controller.status_text()}")

async def wa_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    try:
        sec = float(context.args[0])
        wa_controller.set_interval(sec)
        await update.message.reply_text(f"⏲ اینتروال اسکن: {sec:.1f} ثانیه")
    except Exception:
        await update.message.reply_text("فرمت: /wa_scan 10")

# ----- همگام‌سازی تنظیمات ساعتی/تحویل -----
async def sync_set_thursday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    arg = context.args[0] if context.args else ""
    if not arg:
        await update.message.reply_text("فرمت: /set_thursday 08:00-12:30 یا clear")
        return
    if arg.lower() in ("clear", "off", "none"):
        wa_controller.set_thursday(None, None)
    else:
        if "-" not in arg:
            await update.message.reply_text("فرمت: 08:00-12:30")
            return
        a, b = arg.split("-", 1)
        wa_controller.set_thursday(a.strip(), b.strip())
    await update.message.reply_text("✅ پنج‌شنبه به‌روزرسانی شد (برای واتساپ).")

async def sync_disable_friday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    wa_controller.set_friday_enabled(False)
    await update.message.reply_text("✅ جمعه‌ها در واتساپ غیرفعال شد.")

async def sync_enable_friday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    wa_controller.set_friday_enabled(True)
    await update.message.reply_text("✅ جمعه‌ها در واتساپ فعال شد.")

async def sync_set_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    if not context.args or "-" not in context.args[0]:
        await update.message.reply_text("فرمت: /set_hours 08:00-18:00")
        return
    a, b = context.args[0].split("-", 1)
    wa_controller.set_hours(a.strip(), b.strip())
    await update.message.reply_text("✅ ساعات کاری واتساپ تنظیم شد.")

async def sync_set_delivery_before(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    text = (update.message.text or "").partition(" ")[2].strip() if update.message else ""
    if text:
        wa_controller.set_delivery_before(text)
        await update.message.reply_text("✅ متن تحویل (قبل) برای واتساپ تنظیم شد.")

async def sync_set_delivery_after(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    text = (update.message.text or "").partition(" ")[2].strip() if update.message else ""
    if text:
        wa_controller.set_delivery_after(text)
        await update.message.reply_text("✅ متن تحویل (بعد) برای واتساپ تنظیم شد.")

async def sync_set_changeover_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    args = " ".join(context.args)
    hhmm = ""
    if "time=" in args:
        hhmm = args.split("time=", 1)[1].strip()
    elif context.args:
        hhmm = context.args[0].strip()
    if hhmm:
        wa_controller.set_changeover_hour(hhmm)
        await update.message.reply_text("✅ ساعت سوئیچ متن تحویل در واتساپ تنظیم شد.")

def register_wa_sync_handlers(app: "Application"):
    # استارت خودکار واتساپ همزمان با بوت ربات
    async def _start_wa(_):
        await wa_controller.start()
    if app.job_queue:
        app.job_queue.run_once(_start_wa, when=0)

    # دستورات اختصاصی واتساپ
    app.add_handler(CommandHandler("wa_on", wa_on))
    app.add_handler(CommandHandler("wa_off", wa_off))
    app.add_handler(CommandHandler("wa_restart", wa_restart))
    app.add_handler(CommandHandler("wa_status", wa_status))
    app.add_handler(CommandHandler("wa_scan", wa_scan))

    # سینک با فرامین اداری (برای واتساپ هم اعمال شود)
    app.add_handler(CommandHandler("set_hours",            sync_set_hours),           group=2)
    app.add_handler(CommandHandler("set_thursday",         sync_set_thursday),        group=2)
    app.add_handler(CommandHandler("disable_friday",       sync_disable_friday),      group=2)
    app.add_handler(CommandHandler("enable_friday",        sync_enable_friday),       group=2)
    app.add_handler(CommandHandler("set_delivery_before",  sync_set_delivery_before), group=2)
    app.add_handler(CommandHandler("set_delivery_after",   sync_set_delivery_after),  group=2)
    app.add_handler(CommandHandler("set_changeover_hour",  sync_set_changeover_hour), group=2)
