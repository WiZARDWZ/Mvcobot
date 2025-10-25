import json
import re
import csv
import tempfile
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from telethon import events


def _ensure_private_package() -> None:
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2].parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


try:
    from privateTelegram.telegram.client import (
        client,
        ADMIN_GROUP_IDS,
        MAIN_GROUP_ID,
        NEW_GROUP_ID,
    )
    from privateTelegram.config.settings import settings, save_settings
    from privateTelegram.utils import state
except ModuleNotFoundError:
    _ensure_private_package()
    from privateTelegram.telegram.client import (
        client,
        ADMIN_GROUP_IDS,
        MAIN_GROUP_ID,
        NEW_GROUP_ID,
    )
    from privateTelegram.config.settings import settings, save_settings
    from privateTelegram.utils import state

TZ = ZoneInfo("Asia/Tehran")

@client.on(events.NewMessage(chats=ADMIN_GROUP_IDS))
async def handle_admin_commands(event):
    message_text = event.message.message.strip()
    lower_text = message_text.lower()

    # غیرفعال/فعال کردن بات
    if lower_text == "/disable":
        settings["enabled"] = False
        save_settings()
        await event.reply("⏹️ ربات غیرفعال شد.")

    elif lower_text == "/enable":
        settings["enabled"] = True
        save_settings()
        await event.reply("▶️ ربات فعال شد.")

    # ───── فعال/غیرفعال کردن پاسخ‌دهی پیام‌های خصوصی ─────
    elif lower_text == "/dm_off":
        settings["dm_enabled"] = False
        save_settings()
        await event.reply("✉️ پاسخ‌دهی پیام‌های خصوصی غیرفعال شد.")

    elif lower_text == "/dm_on":
        settings["dm_enabled"] = True
        save_settings()
        await event.reply("✉️ پاسخ‌دهی پیام‌های خصوصی فعال شد.")

    # مدیریت لیست سیاه
    elif lower_text.startswith("/blacklist add "):
        try:
            user_id = int(message_text.split()[-1])
            bl = settings.setdefault("blacklist", [])
            if user_id not in bl:
                bl.append(user_id)
                save_settings()
                await event.reply(f"🚫 کاربر {user_id} به لیست سیاه افزوده شد.")
            else:
                await event.reply("⚠️ این کاربر قبلاً در لیست سیاه است.")
        except ValueError:
            await event.reply("❗️ فرمت صحیح نیست. استفاده: /blacklist add <user_id>")

    elif lower_text.startswith("/blacklist remove "):
        try:
            user_id = int(message_text.split()[-1])
            bl = settings.get("blacklist", [])
            if user_id in bl:
                bl.remove(user_id)
                save_settings()
                await event.reply(f"✅ کاربر {user_id} از لیست سیاه حذف شد.")
            else:
                await event.reply("⚠️ این کاربر در لیست سیاه نیست.")
        except ValueError:
            await event.reply("❗️ فرمت صحیح نیست. استفاده: /blacklist remove <user_id>")

    elif lower_text == "/blacklist list":
        bl = settings.get("blacklist", [])
        if bl:
            await event.reply("📃 لیست سیاه:\n" + "\n".join(str(u) for u in bl))
        else:
            await event.reply("✅ لیست سیاه خالی است.")

    # تنظیم ساعات کاری
    elif lower_text.startswith("/set_hours "):
        try:
            parts = message_text.split()
            start = parts[1].split("=")[1]
            end   = parts[2].split("=")[1]
            settings["working_hours"] = {"start": start, "end": end}
            save_settings()
            await event.reply(f"⏲️ ساعات کاری شنبه–چهارشنبه: {start} تا {end}")
        except:
            await event.reply("⚠️ فرمت صحیح: /set_hours start=HH:MM end=HH:MM")

    elif lower_text.startswith("/set_thursday "):
        try:
            parts = message_text.split()
            start = parts[1].split("=")[1]
            end   = parts[2].split("=")[1]
            settings["thursday_hours"] = {"start": start, "end": end}
            save_settings()
            await event.reply(f"📅 ساعات کاری پنج‌شنبه: {start} تا {end}")
        except:
            await event.reply("⚠️ فرمت صحیح: /set_thursday start=HH:MM end=HH:MM")

    elif lower_text == "/disable_friday":
        settings["disable_friday"] = True
        save_settings()
        await event.reply("🚫 ربات در روز جمعه غیرفعال شد.")

    elif lower_text == "/enable_friday":
        settings["disable_friday"] = False
        save_settings()
        await event.reply("✅ ربات در روز جمعه فعال شد.")

    # تنظیم ناهار
    elif lower_text.startswith("/set_lunch_break "):
        try:
            parts = message_text.split()
            start = parts[1].split("=")[1]
            end   = parts[2].split("=")[1]
            settings["lunch_break"] = {"start": start, "end": end}
            save_settings()
            await event.reply(f"🍽 ناهار: {start} تا {end}")
        except:
            await event.reply("⚠️ فرمت صحیح: /set_lunch_break start=HH:MM end=HH:MM")

    # محدودیت استعلام
    elif lower_text.startswith("/set_query_limit "):
        try:
            limit = int(message_text.split()[1].split("=")[1])
            settings["query_limit"] = limit
            save_settings()
            await event.reply(f"🔢 محدودیت استعلام به {limit} در ۲۴ ساعت تنظیم شد.")
        except:
            await event.reply("⚠️ فرمت صحیح: /set_query_limit limit=<number>")

    # تغییر متون تحویل
    elif lower_text.startswith("/set_delivery_info_before "):
        txt = message_text[len("/set_delivery_info_before "):]
        settings.setdefault("delivery_info", {})["before_15"] = txt
        save_settings()
        await event.reply("📦 متن تحویل قبل از ساعت جدید شد.")

    elif lower_text.startswith("/set_delivery_info_after "):
        txt = message_text[len("/set_delivery_info_after "):]
        settings.setdefault("delivery_info", {})["after_15"] = txt
        save_settings()
        await event.reply("📦 متن تحویل بعد از ساعت جدید شد.")

    # تغییر ساعت انتقال متن تحویل
    elif lower_text.startswith("/set_changeover_hour "):
        try:
            new_time = message_text.split()[1].split("=")[1]
            settings["changeover_hour"] = new_time
            save_settings()
            await event.reply(f"⏰ زمان انتقال متن تحویل تنظیم شد: {new_time}")
        except:
            await event.reply("⚠️ فرمت صحیح: /set_changeover_hour time=HH:MM")

    # گروه‌ها
    elif lower_text.startswith("/set_main_group "):
        try:
            new_id = int(message_text.split()[1].split("=")[1])
            settings["main_group_id"] = new_id
            save_settings()
            await event.reply(f"✅ گروه اصلی تنظیم شد: {new_id}")
        except:
            await event.reply("⚠️ فرمت صحیح: /set_main_group id=<group_id>")

    elif lower_text.startswith("/add_secondary_group "):
        parts = message_text.split()
        try:
            new_id = int(parts[1].split("=")[1])
            sec = settings.setdefault("secondary_group_ids", [])
            if new_id not in sec:
                sec.append(new_id)
                save_settings()
                await event.reply(f"✅ گروه فرعی {new_id} اضافه شد.")
            else:
                await event.reply("⚠️ این گروه قبلاً اضافه شده است.")
        except:
            await event.reply("⚠️ فرمت صحیح: /add_secondary_group id=<group_id>")

    elif lower_text.startswith("/remove_secondary_group "):
        parts = message_text.split()
        try:
            rem_id = int(parts[1].split("=")[1])
            sec = settings.get("secondary_group_ids", [])
            if rem_id in sec:
                sec.remove(rem_id)
                save_settings()
                await event.reply(f"✅ گروه فرعی {rem_id} حذف شد.")
            else:
                await event.reply("⚠️ این گروه در لیست گروه‌های فرعی نیست.")
        except:
            await event.reply("⚠️ فرمت صحیح: /remove_secondary_group id=<group_id>")

    elif lower_text.startswith("/set_admin_group "):
        try:
            new_id = int(message_text.split()[1].split("=")[1])
            settings["admin_group_ids"] = [new_id]
            save_settings()
            await event.reply(f"✅ گروه مدیریت تنظیم شد: {new_id}")
        except:
            await event.reply("⚠️ فرمت صحیح: /set_admin_group id=<group_id>")

    elif lower_text.startswith("/add_admin_group "):
        parts = message_text.split()
        try:
            new_id = int(parts[1].split("=")[1])
            adm = settings.setdefault("admin_group_ids", [])
            if new_id not in adm:
                adm.append(new_id)
                save_settings()
                await event.reply(f"✅ گروه مدیریت {new_id} اضافه شد.")
            else:
                await event.reply("⚠️ این گروه قبلاً اضافه شده است.")
        except:
            await event.reply("⚠️ فرمت صحیح: /add_admin_group id=<group_id>")

    elif lower_text.startswith("/remove_admin_group "):
        parts = message_text.split()
        try:
            rem_id = int(parts[1].split("=")[1])
            adm = settings.get("admin_group_ids", [])
            if rem_id in adm:
                adm.remove(rem_id)
                save_settings()
                await event.reply(f"✅ گروه مدیریت {rem_id} حذف شد.")
            else:
                await event.reply("⚠️ این گروه در لیست مدیریت نیست.")
        except:
            await event.reply("⚠️ فرمت صحیح: /remove_admin_group id=<group_id>")

    elif lower_text == "/list_groups":
        main = settings.get("main_group_id")
        sec  = settings.get("secondary_group_ids", [])
        adm  = settings.get("admin_group_ids", [])
        await event.reply(
            f"گروه اصلی: {main}\n"
            f"گروه‌های فرعی: {', '.join(map(str, sec)) or '—'}\n"
            f"گروه‌های مدیریت: {', '.join(map(str, adm)) or '—'}"
        )

    # ───────────── /export ... ─────────────
    elif lower_text.startswith("/export "):
        # ... (بخش اکسپورت همان است که خودت گذاشتی؛ عیناً نگه داشته‌ام)
        def fa2en(s: str) -> str:
            return s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).strip()

        def normalize_for_count(token: str) -> str:
            cleaned = re.sub(r"[-_/\.,\s]", "", token or "").upper()
            if len(cleaned) < 10:
                cleaned += "X" * (10 - len(cleaned))
            elif len(cleaned) > 10:
                cleaned = cleaned[:10]
            return cleaned

        def display_code(code10: str) -> str:
            code10 = code10.upper()
            return f"{code10[:5]}-{code10[5:10]}"

        text_norm = fa2en(message_text)
        m = re.match(r"^/export\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})\s*$", text_norm, flags=re.IGNORECASE)
        if not m:
            await event.reply("⚠️ فرمت صحیح: `/export YYYY-MM-DD to YYYY-MM-DD`", parse_mode="markdown")
            return

        start_s, end_s = m.group(1), m.group(2)
        try:
            start_dt_local = datetime.strptime(start_s, "%Y-%m-%d").replace(tzinfo=TZ)
            end_dt_local   = datetime.strptime(end_s, "%Y-%m-%d").replace(tzinfo=TZ) + timedelta(days=1) - timedelta(seconds=1)
        except ValueError:
            await event.reply("⚠️ تاریخ نامعتبر است. مثال: `/export 2025-07-22 to 2025-08-22`", parse_mode="markdown")
            return

        start_utc = start_dt_local.astimezone(timezone.utc)
        end_utc   = end_dt_local.astimezone(timezone.utc)
        TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]{5}[-_/\. ]?[A-Za-z0-9]{1,5}")
        counts = {}

        async def scan_chat(chat_id: int):
            async for msg in client.iter_messages(chat_id, offset_date=end_utc):
                if not msg or not getattr(msg, "message", None):
                    continue
                dt = msg.date
                if dt < start_utc:
                    break
                text = msg.message
                raw_tokens = TOKEN_PATTERN.findall(text)
                tokens = [t for t in raw_tokens if re.search(r"\d", t)]
                for t in tokens:
                    norm10 = normalize_for_count(t)
                    disp = display_code(norm10)
                    counts[disp] = counts.get(disp, 0) + 1

        try:
            await scan_chat(MAIN_GROUP_ID)
        except Exception:
            pass
        try:
            await scan_chat(NEW_GROUP_ID)
        except Exception:
            pass

        if not counts:
            await event.reply("ℹ️ در بازه‌ی درخواستی هیچ موردی یافت نشد.")
            return

        fname = f"demand_{start_s}_to_{end_s}.csv"
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8", newline="") as tmp:
            writer = csv.writer(tmp)
            writer.writerow(["کد", "تعداد"])
            for code, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                writer.writerow([code, cnt])
            tmp_path = tmp.name

        try:
            await event.reply(f"📤 گزارش تقاضا (کد/تعداد) برای بازه {start_s} تا {end_s}:", file=tmp_path)
        finally:
            try:
                os.remove(tmp_path)
            except:
                pass

    # دستور وضعیت
    elif lower_text == "/status":
        now = datetime.now(TZ)
        if state.last_cache_update:
            minutes = int((now - state.last_cache_update).total_seconds() // 60)
            cache_info = f"{minutes} دقیقه پیش به‌روز شده"
        else:
            cache_info = "داده‌های کش موجود نیست"
        total = state.total_queries
        await event.reply(
            "📊 وضعیت ربات:\n"
            f"وضعیت: {'روشن' if settings.get('enabled', True) else 'خاموش'}\n"
            f"زمان بروزرسانی کش: {cache_info}\n"
            f"کل استعلام‌ها: {total}"
        )
