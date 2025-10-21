"""Legacy WhatsApp control handlers kept for backward compatibility."""

from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from wa.manager import wa_controller

if TYPE_CHECKING:  # pragma: no cover
    from telegram.ext import Application
try:
    from admin import is_authorized
except Exception:
    def is_authorized(chat_id: int) -> bool:
        return True

async def _guard(update: Update) -> bool:
    chat_id = update.effective_chat.id if update.effective_chat else 0
    if not is_authorized(chat_id):
        if update.message:
            await update.message.reply_text("⛔️ دسترسی ندارید.")
        return False
    return True

# پایه
async def wa_on(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    wa_controller.enable()
    await wa_controller.start()
    await update.message.reply_text("✅ واتساپ فعال شد و اسکن در حال اجراست.")

async def wa_off(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    wa_controller.disable()
    await update.message.reply_text("🟡 واتساپ غیرفعال شد (اسکن انجام نمی‌شود).")

async def wa_restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    await wa_controller.restart()
    await update.message.reply_text("♻️ واتساپ ری‌استارت شد.")

async def wa_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    await update.message.reply_text(f"📊 وضعیت واتساپ:\n{wa_controller.status_text()}")

async def wa_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    if len(context.args) != 1 or "-" not in context.args[0]:
        await update.message.reply_text("فرمت صحیح: /wa_hours 08:30-17:30")
        return
    a, b = context.args[0].split("-")
    try:
        wa_controller.set_hours(a, b)
        await update.message.reply_text(f"🕒 ساعات کاری پیش‌فرض تنظیم شد: {a}–{b}")
    except Exception as e:
        await update.message.reply_text(f"❌ مقدار نامعتبر: {e}")

async def wa_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    try:
        seconds = float(context.args[0])
        wa_controller.set_interval(seconds)
        await update.message.reply_text(f"⏲ اینتروال اسکن: {seconds:.1f}s")
    except Exception:
        await update.message.reply_text("فرمت صحیح: /wa_scan 10")

# === فرامین جدید (مطابق خواسته) ===

# 7) تغییر ساعت کاری پنج‌شنبه
async def set_thursday_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    if len(context.args) != 1 or "-" not in context.args[0]:
        await update.message.reply_text("فرمت صحیح: /set_thursday_hours 08:30-12:30\nبرای حذف override از /clear_thursday_hours استفاده کنید.")
        return
    a, b = context.args[0].split("-")
    try:
        wa_controller.set_thursday_hours(a, b)
        await update.message.reply_text(f"🗓 ساعات پنج‌شنبه تنظیم شد: {a}–{b}")
    except Exception as e:
        await update.message.reply_text(f"❌ مقدار نامعتبر: {e}")

async def clear_thursday_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    wa_controller.clear_thursday_hours()
    await update.message.reply_text("✅ override پنج‌شنبه حذف شد (از ساعات پیش‌فرض استفاده می‌شود).")

# 8) غیرفعال کردن فعالیت ربات در جمعه‌ها
async def disable_friday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    wa_controller.set_friday_enabled(False)
    await update.message.reply_text("🚫 فعالیت واتساپ در روز جمعه غیرفعال شد.")

# 9) فعال کردن مجدد فعالیت ربات در جمعه‌ها
async def enable_friday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    wa_controller.set_friday_enabled(True)
    await update.message.reply_text("✅ فعالیت واتساپ در روز جمعه مجاز شد.")

# 12) تغییر متن اطلاعات تحویل کالا برای قبل از ساعت مشخص
async def set_delivery_info_before(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    text = (update.message.text or "").partition(" ")[2].strip() if update.message else ""
    if not text:
        await update.message.reply_text("فرمت: /set_delivery_info_before [متن]\nمثال:\n/set_delivery_info_before تحویل کالا هر روز ساعت 16 و پنجشنبه‌ها ساعت 12:30 در دفتر بازار")
        return
    wa_controller.set_delivery_before(text)
    await update.message.reply_text("📦 متن تحویل (قبل از ساعت تعیین‌شده) تنظیم شد.")

# 13) تغییر متن اطلاعات تحویل کالا برای بعد از ساعت مشخص
async def set_delivery_info_after(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    text = (update.message.text or "").partition(" ")[2].strip() if update.message else ""
    if not text:
        await update.message.reply_text("فرمت: /set_delivery_info_after [متن]\nمثال:\n/set_delivery_info_after ارسال مستقیم از انبار با زمان تقریبی تحویل 45 دقیقه امکان‌پذیر است.")
        return
    wa_controller.set_delivery_after(text)
    await update.message.reply_text("📦 متن تحویل (بعد از ساعت تعیین‌شده) تنظیم شد.")

# 14) تغییر ساعت تغییر متن اطلاعات تحویل کالا
async def set_changeover_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _guard(update): return
    # ورودی: /set_changeover_hour time=15:30
    args = " ".join(context.args)
    key, eq, val = args.partition("=")
    if key.strip().lower() != "time" or not val:
        await update.message.reply_text("فرمت: /set_changeover_hour time=HH:MM\nمثال: /set_changeover_hour time=15:30")
        return
    try:
        wa_controller.set_changeover_hour(val.strip())
        await update.message.reply_text(f"⏰ زمان تغییر متن تحویل تنظیم شد: {val.strip()}")
    except Exception as e:
        await update.message.reply_text(f"❌ مقدار نامعتبر: {e}")

def register_wa_handlers(app: "Application"):
    # استارت واتساپ در شروع ربات تلگرام
    async def _start_wa_job(_):
        await wa_controller.start()
    app.job_queue.run_once(_start_wa_job, when=0)

    app.add_handler(CommandHandler("wa_on", wa_on))
    app.add_handler(CommandHandler("wa_off", wa_off))
    app.add_handler(CommandHandler("wa_restart", wa_restart))
    app.add_handler(CommandHandler("wa_status", wa_status))
    app.add_handler(CommandHandler("wa_hours", wa_hours))
    app.add_handler(CommandHandler("wa_scan", wa_scan))

    # جدیدها:
    app.add_handler(CommandHandler("set_thursday_hours", set_thursday_hours))
    app.add_handler(CommandHandler("clear_thursday_hours", clear_thursday_hours))
    app.add_handler(CommandHandler("disable_friday", disable_friday))
    app.add_handler(CommandHandler("enable_friday", enable_friday))
    app.add_handler(CommandHandler("set_delivery_info_before", set_delivery_info_before))
    app.add_handler(CommandHandler("set_delivery_info_after", set_delivery_info_after))
    app.add_handler(CommandHandler("set_changeover_hour", set_changeover_hour))
