import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from wa.waweb import WAConfig, WAWebBot

log = logging.getLogger("WA-MANAGER")

@dataclass
class _State:
    enabled: bool = True
    interval_sec: float = 10.0
    task: Optional[asyncio.Task] = None
    bot: Optional[WAWebBot] = None
    # تنظیمات کاری/تحویل (در صورت نیاز)
    work_start: str = "08:00"
    work_end: str   = "18:00"
    thu_start: Optional[str] = "08:00"
    thu_end: Optional[str]   = "12:30"
    friday_enabled: bool = False
    changeover_hhmm: str = "15:00"
    delivery_before: str = "🚚 تحویل کالا هر روز 16 و پنج‌شنبه‌ها 12:30 در دفتر بازار"
    delivery_after:  str = "🛵 ارسال مستقیم از انبار (حدود 45-60 دقیقه)"

FALLBACK_DB_DOWN = (
    "دسترسی به دیتابیس قطع میباشد , در حال بررسی مشکل هستیم\n"
    "ممنون از شکیبایی شما\n"
    "http://mbaghshomali.ir/"
)

# ===== هلسپر اتصال به لاجیک تلگرام =====
def _try_import_inventory():
    try:
        import handlers.inventory as inv
        return inv
    except Exception as e:
        log.warning("WA: cannot import handlers.inventory (fallback to DB_DOWN). err=%s", e)
        return None

def _normalize_code(inv, code: str) -> str:
    try:
        return inv._normalize(code)  # type: ignore
    except Exception:
        import re
        return re.sub(r'[^A-Za-z0-9]', '', (code or '')).lower()

def _fmt_disp(code_norm: str) -> str:
    c = ''.join(ch for ch in (code_norm or '') if ch.isalnum())
    return f"{c[:5]}-{c[5:]}" if len(c) > 5 else c

def _format_reply_for_item(item: Dict[str, Any], delivery_line: str) -> str:
    raw_code = str(item.get("شماره قطعه", "") or "")
    brand    = str(item.get("برند", "") or "")
    name     = str(item.get("نام کالا", "") or "")
    price    = item.get("فی فروش", 0)
    try:
        pv = int(float(price))
        price_text = f"{pv:,} ریال"
    except Exception:
        price_text = str(price or "")
    iran_txt = str(item.get("Iran Code", "") or "")
    lines = [
        f"کد: {raw_code}" if raw_code else "",
        f"برند: {brand}" if brand else "برند: —",
        f"نام کالا: {name}" if name else "",
        f"قیمت: {price_text}" if price_text else "",
    ]
    if iran_txt:
        lines.append(f"توضیحات: {iran_txt}")
    if delivery_line:
        lines.append(delivery_line)
    lines = [ln for ln in lines if ln.strip()]
    return "\n".join(lines)

def _format_not_found(norm: str) -> str:
    return f"⚠️ {_fmt_disp(norm)} متأسفانه موجود نمی‌باشد."

def _search_full(inv, norm: str) -> List[Dict[str, Any]]:
    try:
        return inv._find_products(norm)  # type: ignore
    except Exception:
        return []

def _search_partial(inv, prefix: str) -> List[Dict[str, Any]]:
    try:
        import bisect
        keys = inv._sorted_keys        # type: ignore
        idx  = inv._inventory_index    # type: ignore
        lo   = bisect.bisect_left(keys, prefix)
        hi   = bisect.bisect_right(keys, prefix + "\uffff")
        return [rec for k in keys[lo:hi] for rec in idx.get(k, [])]
    except Exception:
        return []

class WAController:
    def __init__(self):
        self._state = _State()

    # ---- دستورات کنترل ----
    def enable(self):  self._state.enabled = True
    def disable(self): self._state.enabled = False
    def set_interval(self, sec: float): self._state.interval_sec = max(2.0, float(sec))
    def set_hours(self, a: str, b: str): self._state.work_start, self._state.work_end = a, b
    def set_thursday(self, a: Optional[str], b: Optional[str]): self._state.thu_start, self._state.thu_end = a, b
    def set_friday_enabled(self, enabled: bool): self._state.friday_enabled = bool(enabled)
    def set_changeover_hour(self, hhmm: str): self._state.changeover_hhmm = hhmm
    def set_delivery_before(self, text: str): self._state.delivery_before = text
    def set_delivery_after(self, text: str): self._state.delivery_after = text
    def refresh_working_hours(self):
        bot = self._state.bot
        if bot and hasattr(bot, "refresh_working_hours"):
            try:
                bot.refresh_working_hours()
            except Exception as exc:
                log.warning("WA: refresh_working_hours failed: %s", exc)

    def status_text(self) -> str:
        s = self._state
        running = self._state.task is not None and not self._state.task.done()
        return (
            f"وضعیت: {'ON' if s.enabled else 'OFF'}\n"
            f"Loop: {'RUNNING' if running else 'STOPPED'}\n"
            f"Interval: {s.interval_sec:.1f}s\n"
            f"Hours: {s.work_start}-{s.work_end}\n"
            f"Thu: {s.thu_start or '—'}-{s.thu_end or '—'} | Fri: {'فعال' if s.friday_enabled else 'غیرفعال'}\n"
            f"Changeover: {s.changeover_hhmm}\n"
        )

    def _delivery_text(self) -> str:
        # تلاش برای خواندن از DB settings؛ اگر نشد، از state خودش
        before = self._state.delivery_before
        after  = self._state.delivery_after
        chg    = self._state.changeover_hhmm
        try:
            from database.connector_bot import get_setting
            before = get_setting("delivery_info_before") or before
            after  = get_setting("delivery_info_after") or after
            chg    = get_setting("changeover_hour") or chg
        except Exception:
            pass
        from datetime import datetime
        try:
            now_hm = datetime.now().strftime("%H:%M")
            if now_hm < chg and before:
                return before
            if now_hm >= chg and after:
                return after
        except Exception:
            pass
        return ""

    # ---- اتصال لاجیک تلگرام برای پاسخ کدها ----
    async def _on_codes(self, codes: List[str], ctx: Dict[str, Any]) -> List[str]:
        inv = _try_import_inventory()
        if not inv:
            return [FALLBACK_DB_DOWN]

        # اطمینان از آماده بودن کش/ایندکس
        try:
            if not getattr(inv, "_inventory_index", None) or not getattr(inv, "_sorted_keys", None):
                await inv.refresh_inventory_cache_once()
        except Exception as e:
            log.warning("WA: inventory refresh failed: %s", e)
            return [FALLBACK_DB_DOWN]

        delivery = self._delivery_text()
        replies: List[str] = []

        # حذف تکراری‌ها
        seen = set()
        for raw in codes:
            if raw in seen:
                continue
            seen.add(raw)
            try:
                norm = _normalize_code(inv, raw)
                L = len(norm)
                if L >= 10:
                    items = _search_full(inv, norm)
                    if items:
                        replies.append(_format_reply_for_item(items[0], delivery))
                    else:
                        replies.append(_format_not_found(norm))
                elif 7 <= L < 10:
                    cands = _search_partial(inv, norm)
                    if cands:
                        replies.append(_format_reply_for_item(cands[0], delivery))
                    else:
                        replies.append(_format_not_found(norm))
                else:
                    replies.append(_format_not_found(norm))
            except Exception as e:
                log.warning("WA: on_codes item failed: %s", e)
                replies.append(FALLBACK_DB_DOWN)

        return replies or [FALLBACK_DB_DOWN]

    async def _on_non_code(self, ctx: Dict[str, Any]) -> None:
        # هیچ پیام خودکاری ارسال نشود؛ Unread توسط waweb انجام می‌شود
        return

    # ---- چرخه واتساپ ----
    async def start(self, user_data_dir: Optional[str] = None,
                    headless: Optional[bool] = None, slow_mo_ms: Optional[int] = None):
        if not self._state.enabled:
            log.info("WA: start skipped (disabled).")
            return
        if self._state.task and not self._state.task.done():
            log.info("WA: loop already running.")
            return

        if not user_data_dir:
            base = os.path.join(os.getenv("LOCALAPPDATA", "."), "mvcobot")
            os.makedirs(base, exist_ok=True)
            user_data_dir = os.path.join(base, ".wa-user-data")

        cfg = WAConfig(
            user_data_dir=user_data_dir,
            headless=False if headless is None else bool(headless),
            slow_mo_ms=slow_mo_ms or int(os.getenv("SLOW_MO_MS", "0")),
        )

        bot = WAWebBot(cfg, on_codes=self._on_codes, on_non_code=self._on_non_code)
        self._state.bot = bot

        # اگر متدی برای ست‌کردن اینتروال داشت، اعمال کن (نسخه‌سازگار)
        applied = False
        for name in ("set_interval", "set_scan_interval"):
            if hasattr(bot, name):
                try:
                    getattr(bot, name)(self._state.interval_sec); applied = True; break
                except Exception as e:
                    log.warning("WA: %s failed: %s", name, e)
        if not applied and hasattr(bot, "scan_interval"):
            try:
                setattr(bot, "scan_interval", self._state.interval_sec); applied = True
            except Exception as e:
                log.warning("WA: set scan_interval attr failed: %s", e)
        log.info("WA: scan interval applied? %s", applied)

        async def _runner():
            try:
                log.info("WA: starting bot.start() ...")
                await bot.start()
                log.info("WA: entered scan loop.")
                while self._state.enabled:
                    try:
                        await bot.process_unread_chats_once()
                    except Exception as e:
                        log.warning("WA: scan error: %s", e)
                    await asyncio.sleep(self._state.interval_sec)
                log.info("WA: scan loop ended (disabled).")
            except asyncio.CancelledError:
                log.info("WA: runner cancelled.")
            except Exception as e:
                log.exception("WA runner crashed: %s", e)
            finally:
                try:
                    await bot.stop()
                except Exception:
                    pass
                self._state.bot = None
                log.info("WA: bot stopped/cleaned.")

        self._state.task = asyncio.create_task(_runner(), name="WA-Runner")
        log.info("WA: loop task created.")

    async def stop(self):
        self._state.enabled = False
        if self._state.task and not self._state.task.done():
            self._state.task.cancel()
            try:
                await self._state.task
            except Exception:
                pass
        self._state.task = None
        if self._state.bot:
            try:
                await self._state.bot.stop()
            except Exception:
                pass
            self._state.bot = None
        log.info("WA: loop stopped.")

    async def restart(self):
        await self.stop()
        await self.start()

# singleton
wa_controller = WAController()
