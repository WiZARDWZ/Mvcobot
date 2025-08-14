import pandas as pd
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
from telegram import Update, InputFile
from telegram.ext import ContextTypes

from database.connector_bot import (
    set_setting, get_setting,
    add_to_blacklist, remove_from_blacklist,
    get_blacklist, fetch_logs
)
from handlers.inventory import refresh_inventory_cache_once

# Admin group chat id
ADMIN_GROUP_ID = -1002391888673
_TEHRAN = ZoneInfo("Asia/Tehran")

# authorization
def is_authorized(chat_id):
    return chat_id == ADMIN_GROUP_ID


# 1. disable bot
async def disable_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    set_setting("enabled", "false")
    await update.message.reply_text("⏹️ ربات غیرفعال شد.")


# 2. enable bot
async def enable_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    set_setting("enabled", "true")
    await update.message.reply_text("▶️ ربات فعال شد.")


# 3. add to blacklist
async def blacklist_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
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


# 4. remove from blacklist
async def blacklist_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
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


# 5. list blacklist
async def blacklist_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    users = get_blacklist()
    if not users:
        await update.message.reply_text("✅ لیست سیاه خالی است.")
    else:
        text = "📃 کاربران لیست سیاه:\n" + "\n".join(str(u) for u in users)
        await update.message.reply_text(text)


# 6. set working hours
async def set_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    try:
        parts = {k: v for k, v in (p.split("=") for p in context.args)}
        set_setting("working_start", parts["start"])
        set_setting("working_end", parts["end"])
        await update.message.reply_text(f"⏲️ ساعات کاری: {parts['start']} تا {parts['end']}")
    except Exception:
        # English error text to avoid garbling
        await update.message.reply_text("Format: /set_hours start=08:00 end=18:00")


# 7. set thursday hours
async def set_thursday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    try:
        parts = {k: v for k, v in (p.split("=") for p in context.args)}
        set_setting("thursday_start", parts["start"])
        set_setting("thursday_end", parts["end"])
        await update.message.reply_text(f"📅 پنج‌شنبه: {parts['start']} تا {parts['end']}")
    except Exception:
        await update.message.reply_text("Format: /set_thursday start=08:00 end=14:00")


# 8. disable friday
async def disable_friday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    set_setting("disable_friday", "true")
    await update.message.reply_text("🚫 ربات در جمعه‌ها غیرفعال شد.")


# 9. enable friday
async def enable_friday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    set_setting("disable_friday", "false")
    await update.message.reply_text("✅ ربات در جمعه‌ها فعال شد.")


# 11. set query limit
async def set_query_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    try:
        limit = int(context.args[0].split("=")[1])
        set_setting("query_limit", str(limit))
        await update.message.reply_text(f"🔢 محدودیت استعلام: {limit} بار در روز")
    except Exception:
        await update.message.reply_text("Format: /set_query_limit limit=50")


# 12. delivery text (before)
async def set_delivery_before(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    text = update.message.text.partition(" ")[2]
    set_setting("delivery_before", text)
    await update.message.reply_text("📦 متن تحویل قبل از ساعت تنظیم شد.")


# 13. delivery text (after)
async def set_delivery_after(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    text = update.message.text.partition(" ")[2]
    set_setting("delivery_after", text)
    await update.message.reply_text("📦 متن تحویل بعد از ساعت تنظیم شد.")


# 14. changeover time
async def set_changeover_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    try:
        hour = context.args[0].split("=")[1]
        set_setting("changeover_hour", hour)
        await update.message.reply_text(f"⏰ ساعت تغییر متن: {hour}")
    except Exception:
        await update.message.reply_text("Format: /set_changeover_hour time=15:30")


# 15. status info
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    enabled = get_setting("enabled") == "true"
    qs = get_setting("query_limit") or "—"
    lunch = f"{get_setting('lunch_start')}-{get_setting('lunch_end')}"
    friday = "غیرفعال" if get_setting("disable_friday") == "true" else "فعال"
    text = (
        f"📊 وضعیت ربات:\n"
        f"وضعیت: {'روشن' if enabled else 'خاموش'}\n"
        f"محدودیت استعلام: {qs}\n"
        f"ناهار: {lunch}\n"
        f"جمعه‌ها: {friday}"
    )
    await update.message.reply_text(text)


# 16. export user logs to Excel
async def log_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    if not context.args:
        await update.message.reply_text("Please pass a user id. Example: /log 123456789")
        return
    try:
        user_id = int(context.args[0])
        logs = fetch_logs(user_id)
        if not logs:
            await update.message.reply_text("No logs for this user.")
            return

        df = pd.DataFrame(logs)
        bio = BytesIO()
        df.to_excel(bio, index=False)
        bio.seek(0)
        await update.message.reply_document(
            InputFile(bio, filename=f"user_{user_id}_log.xlsx")
        )
    except Exception as e:
        await update.message.reply_text(f"ERROR: failed to export logs: {e}")


# 17. manual inventory cache refresh (English errors/logs)
async def refresh_cache_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_chat.id):
        return
    now_str = datetime.now(_TEHRAN).strftime("%Y-%m-%d %H:%M:%S")
    try:
        await refresh_inventory_cache_once()
        await update.message.reply_text(f"✅ Inventory cache refreshed at {now_str}.")
    except Exception as e:
        await update.message.reply_text(f"ERROR: cache refresh failed: {e}")
