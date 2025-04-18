# handlers/admin.py

from telegram import Update
from telegram.ext import ContextTypes
from database.connector_bot import (
    set_setting, get_setting,
    add_to_blacklist, remove_from_blacklist,
    get_blacklist
)

ADMIN_GROUP_ID = -1002391888673

async def disable_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    set_setting("enabled", "false")
    await update.message.reply_text("⏹️ ربات غیرفعال شد.")

async def enable_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    set_setting("enabled", "true")
    await update.message.reply_text("▶️ ربات فعال شد.")

async def blacklist_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if not context.args:
        await update.message.reply_text("❗️ لطفاً شناسه کاربر را وارد کنید.")
        return
    try:
        user_id = int(context.args[0])
        add_to_blacklist(user_id)
        await update.message.reply_text(f"🚫 کاربر {user_id} به لیست سیاه افزوده شد.")
    except ValueError:
        await update.message.reply_text("❗️ شناسه باید عدد باشد.")

async def blacklist_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    if not context.args:
        await update.message.reply_text("❗️ لطفاً شناسه کاربر را وارد کنید.")
        return
    try:
        user_id = int(context.args[0])
        remove_from_blacklist(user_id)
        await update.message.reply_text(f"✅ کاربر {user_id} از لیست سیاه حذف شد.")
    except ValueError:
        await update.message.reply_text("❗️ شناسه باید عدد باشد.")

async def blacklist_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    users = get_blacklist()
    if not users:
        await update.message.reply_text("✅ لیست سیاه خالی است.")
    else:
        text = "📃 کاربران لیست سیاه:\n" + "\n".join(str(u) for u in users)
        await update.message.reply_text(text)

async def set_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    try:
        parts = {k: v for k, v in (p.split("=") for p in context.args)}
        set_setting("working_start", parts["start"])
        set_setting("working_end", parts["end"])
        await update.message.reply_text(f"⏲️ ساعات کاری تعیین شد: {parts['start']} تا {parts['end']}")
    except Exception:
        await update.message.reply_text("❗️ فرمت: /set_hours start=08:00 end=18:00")

async def set_thursday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    try:
        parts = {k: v for k, v in (p.split("=") for p in context.args)}
        set_setting("thursday_start", parts["start"])
        set_setting("thursday_end", parts["end"])
        await update.message.reply_text(f"📅 ساعات پنج‌شنبه: {parts['start']} تا {parts['end']}")
    except Exception:
        await update.message.reply_text("❗️ فرمت: /set_thursday start=08:00 end=14:00")

async def disable_friday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    set_setting("disable_friday", "true")
    await update.message.reply_text("🚫 ربات در جمعه‌ها غیرفعال شد.")

async def enable_friday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    set_setting("disable_friday", "false")
    await update.message.reply_text("✅ ربات در جمعه‌ها فعال شد.")

async def set_lunch_break(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    try:
        parts = {k: v for k, v in (p.split("=") for p in context.args)}
        set_setting("lunch_start", parts["start"])
        set_setting("lunch_end", parts["end"])
        await update.message.reply_text(f"🍽 استراحت ناهار: {parts['start']} تا {parts['end']}")
    except Exception:
        await update.message.reply_text("❗️ فرمت: /set_lunch_break start=12:00 end=13:00")

async def set_query_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    try:
        limit = int(context.args[0].split("=")[1])
        set_setting("query_limit", str(limit))
        await update.message.reply_text(f"🔢 محدودیت استعلام: {limit} بار در ۲۴ ساعت")
    except Exception:
        await update.message.reply_text("❗️ فرمت: /set_query_limit limit=50")

async def set_delivery_before(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    text = update.message.text.partition(" ")[2]
    set_setting("delivery_before", text)
    await update.message.reply_text("📦 متن تحویل قبل از ساعت تنظیم شد.")

async def set_delivery_after(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    text = update.message.text.partition(" ")[2]
    set_setting("delivery_after", text)
    await update.message.reply_text("📦 متن تحویل بعد از ساعت تنظیم شد.")

async def set_changeover_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    try:
        hour = context.args[0].split("=")[1]
        set_setting("changeover_hour", hour)
        await update.message.reply_text(f"⏰ ساعت تغییر متن: {hour}")
    except Exception:
        await update.message.reply_text("❗️ فرمت: /set_changeover_hour time=15:30")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.id != ADMIN_GROUP_ID:
        return
    enabled = get_setting("enabled") == "true"
    qs = get_setting("query_limit") or "—"
    lunch = f"{get_setting('lunch_start')}-{get_setting('lunch_end')}"
    friday = "غیرفعال" if get_setting("disable_friday")=="true" else "فعال"
    text = (
        f"📊 وضعیت ربات:\n"
        f"وضعیت: {'روشن' if enabled else 'خاموش'}\n"
        f"محدودیت استعلام: {qs}\n"
        f"ناهار: {lunch}\n"
        f"جمعه‌ها: {friday}"
    )
    await update.message.reply_text(text)
