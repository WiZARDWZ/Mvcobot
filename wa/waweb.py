# -*- coding: utf-8 -*-
# WhatsApp Web automation — پاسخ فقط به «کد»، Unread برای هر «غیرکُد»،
# در صورت «کد + متن اضافه» هم پاسخ می‌دهد هم Unread می‌کند.
import asyncio, os, re, json, time, urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable, Coroutine, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Locator
from playwright.async_api import TimeoutError as PWTimeout

DB_DOWN_MESSAGE = (
    "دسترسی به دیتابیس قطع میباشد , در حال بررسی مشکل هستیم\n"
    "ممنون از شکیبایی شما\n"
    "mbaghshomali.ir"
)

CHATLIST_SEL = "[role='grid'][aria-label*='Chat list' i]"
UNREAD_ITEM_XPATH = ("//div[@role='listitem'][.//span[contains(@aria-label,'unread')]]")

HEADER_CANDIDATES = [
    "[data-testid='conversation-info-header-chat-title']",
    "header [title]", "header h1", "header span[dir='auto']", "header span[title]"
]

# ---- Code detection (کم‌نویز: حداقل یک رقم) ----
P2E = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
RE_SEG = re.compile(r"\b(?=[A-Za-z0-9\-_/\. ]*\d)[A-Za-z0-9]{2,8}(?:[-_/\. ]+[A-Za-z0-9]{2,12})+\b")
RE_NUM = re.compile(r"(?<!\d)(\d{6,12})(?!\d)")
RE_ALN = re.compile(r"(?=.*\d)\b[A-Za-z0-9]{6,20}\b")
def norm_digits(s: str) -> str: return (s or "").translate(P2E)

def extract_codes(t: str) -> List[str]:
    t = norm_digits(t)
    out, seen = [], set()
    for m in RE_SEG.finditer(t): out.append(m.group(0))
    for m in RE_NUM.finditer(t): out.append(m.group(1))
    for m in RE_ALN.finditer(t): out.append(m.group(0))
    r = []
    for c in out:
        if c not in seen: seen.add(c); r.append(c)
    return r

def msg_has_non_code(text: str, codes_in_msg: List[str]) -> bool:
    """
    اگر بعد از حذف کدها هنوز کاراکتر حرفی (فارسی/لاتین) باقی بماند → غیرکُد دارد.
    """
    s = norm_digits(text or "")
    for c in set(codes_in_msg or []):
        s = re.sub(re.escape(c), " ", s, flags=re.IGNORECASE)
    s = re.sub(r"[-_/\.|:,;()\[\]{}<>~+=*\\]", " ", s)
    s = re.sub(r"\d+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return bool(re.search(r"[^\W\d_]", s, flags=re.UNICODE))

# ---- Telegram notify ----
def _tg_env(): return os.getenv("TG_BOT_TOKEN"), os.getenv("TG_ADMIN_CHAT_ID")
def notify_admin(text: str) -> None:
    tok, cid = _tg_env()
    if not tok or not cid: return
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    data = json.dumps({"chat_id": cid, "text": text, "parse_mode": "HTML"}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()
    except Exception:
        pass

def _now(): return time.strftime("%H:%M:%S")

@dataclass
class WAConfig:
    user_data_dir: str = "./.wa-user-data"
    headless: bool = False
    slow_mo_ms: int = 100
    idle_scan_interval_sec: float = 10.0
    start_url: str = "https://web.whatsapp.com/"
    max_messages_scan: int = 500
    ensure_header_on_send: bool = True
    debug_send_dot_if_no_reply: bool = False   # نقطه خاموش
    debug_tag: str = "WADEBUG"

class WAWebBot:
    def __init__(
        self,
        config: WAConfig,
        on_codes: Optional[Callable[[List[str], Dict[str, Any]], Coroutine[Any, Any, List[str]]]] = None,
        on_non_code: Optional[Callable[[List[str], Dict[str, Any]], Coroutine[Any, Any, None]]] = None,
        logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.cfg = config
        self.on_codes = on_codes
        self.on_non_code = on_non_code
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self.log = logger or (lambda m: print(m, flush=True))

    def dlog(self, msg: str): self.log(f"[{_now()}] {self.cfg.debug_tag} | {msg}")

    # ---------- lifecycle ----------
    async def start(self) -> None:
        pw = await async_playwright().start()
        self._browser = await pw.chromium.launch_persistent_context(
            user_data_dir=self.cfg.user_data_dir,
            headless=self.cfg.headless,
            slow_mo=self.cfg.slow_mo_ms,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser  # type: ignore
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        self.dlog("goto web.whatsapp.com")
        await self._page.goto(self.cfg.start_url, wait_until="domcontentloaded")
        try:
            await self._page.wait_for_load_state("networkidle", timeout=60_000)
        except PWTimeout:
            pass
        await self._ensure_ready()
        self.dlog("READY")

    async def _ensure_ready(self) -> None:
        page = self._page; assert page
        try:
            await page.wait_for_selector(CHATLIST_SEL, timeout=120_000, state="visible")
        except PWTimeout:
            await page.wait_for_selector("[data-testid='qrcode'], canvas[aria-label*='Scan' i]", timeout=180_000)
            await page.wait_for_selector(CHATLIST_SEL, timeout=180_000, state="visible")

    async def run_forever(self) -> None:
        while True:
            try:
                await self.process_unread_chats_once()
            except Exception as e:
                self.dlog(f"loop error: {e!r}")
            await asyncio.sleep(self.cfg.idle_scan_interval_sec)

    # ---------- core loop ----------
    async def process_unread_chats_once(self) -> None:
        page = self._page; assert page
        items = await self._find_unread_items()
        self.dlog(f"unread items found: {len(items)}")
        if not items:
            self.log("… no unread chats"); return

        item = items[0]
        title_guess = await self._guess_item_title(item)
        self.dlog(f"opening chat item, title guess: {title_guess or '—'}")
        if not await self._open_chat_item(item):
            self.dlog("open chat failed"); return

        header_title = await self._get_header_title()
        self.dlog(f"active header: {header_title or '—'}")

        last_out_idx = await self._get_last_outgoing_index()
        self.dlog(f"last outgoing index: {last_out_idx}")

        msgs = await self._collect_messages_after(last_out_idx)
        self.dlog(f"new messages after last outgoing: {len(msgs)}")
        if not msgs:
            await self._leave_to_sidebar()
            return

        # --- استخراج کُد و تشخیص «غیرکُد» دقیق (حتی داخل همان پیام) ---
        codes: List[str] = []
        had_non_code: bool = False
        for m in msgs:
            found = extract_codes(m)
            if found:
                codes.extend(found)
                if msg_has_non_code(m, found):
                    had_non_code = True
            else:
                had_non_code = True

        # dedup codes
        seen=set(); codes=[c for c in codes if (c not in seen and not seen.add(c))]
        self.dlog(f"codes: {codes} | had_non_code={had_non_code}")

        if not codes:
            self.dlog("no codes → mark unread & notify & leave")
            await self._mark_current_chat_unread(header_title)
            preview = (msgs[-1] if msgs else "")[:200].replace("<","‹").replace(">","›")
            notify_admin(
                f"🔔 <b>پیام غیرکُد</b> در چت «<code>{header_title or 'بدون‌عنوان'}</code>»\n"
                f"آخرین پیام: <i>{preview}</i>"
            )
            await self._leave_to_sidebar()
            return

        # پاسخ فقط برای کُدها
        replies: List[str] = []
        if self.on_codes:
            try:
                replies = await self.on_codes(codes, {"title": header_title}) or []
                self.dlog(f"on_codes replies: {len(replies)}")
            except Exception as e:
                self.dlog(f"on_codes raised: {e!r}")
                replies = [DB_DOWN_MESSAGE]

        if not replies:
            replies = [f"کد {c} موجود نمی‌باشد" for c in codes]

        for i, r in enumerate(replies, 1):
            ok = await self._send_message_safe(r, expected_header_title=header_title)
            self.dlog(f"send reply {i}/{len(replies)} -> {'OK' if ok else 'FAIL'}")
            await asyncio.sleep(0.2)

        if had_non_code:
            self.dlog("extra non-code detected → mark unread & notify")
            await self._mark_current_chat_unread(header_title)
            preview = (msgs[-1] if msgs else "")[:200].replace("<","‹").replace(">","›")
            notify_admin(
                f"🔔 <b>نیاز به پیگیری کارشناس</b> در چت «<code>{header_title or 'بدون‌عنوان'}</code>»\n"
                f"آخرین پیام: <i>{preview}</i>"
            )

        await self._leave_to_sidebar()

    # ---------- unread / open ----------
    async def _find_unread_items(self) -> List[Locator]:
        page = self._page; assert page
        items = page.locator(f"xpath={UNREAD_ITEM_XPATH}")
        cnt = await items.count()
        return [items.nth(i) for i in range(cnt)]

    async def _guess_item_title(self, item: Locator) -> str:
        try:
            cap = item.locator(".//span[@dir='auto' or @title][normalize-space()!='']")
            if await cap.count():
                return (await cap.first.inner_text()).strip()
        except Exception:
            pass
        return ""

    async def _get_header_title(self) -> str:
        page = self._page; assert page
        for sel in HEADER_CANDIDATES:
            try:
                loc = page.locator(sel)
                if await loc.count():
                    txt = (await loc.first.inner_text()) or ""
                    txt = txt.strip()
                    if txt:
                        return txt
            except Exception:
                continue
        return ""

    async def _open_chat_item(self, item: Locator) -> bool:
        page = self._page; assert page
        async def opened_ok() -> bool:
            try:
                n = await page.locator("[data-pre-plain-text]").count()
                if n > 0: return True
            except Exception: pass
            tb, _ = await self._find_composer_candidate()
            return (await tb.count()) > 0

        for attempt in range(6):
            try:
                await item.scroll_into_view_if_needed()
                if attempt in (0,1):
                    await item.click(force=(attempt==1))
                elif attempt==2:
                    await item.dblclick()
                elif attempt==3:
                    box = await item.bounding_box()
                    if box:
                        await page.mouse.click(box["x"]+box["width"]/2, box["y"]+box["height"]/2)
                    else:
                        await item.click()
                else:
                    await item.focus(); await page.keyboard.press("Enter")
                ok = await opened_ok()
                self.dlog(f"open attempt {attempt} -> {'OK' if ok else 'NO'}")
                if ok: return True
            except Exception as e:
                self.dlog(f"open attempt {attempt} exception: {e!r}")
        return False

    # ---------- messages ----------
    async def _msg_nodes(self) -> List[Locator]:
        page = self._page; assert page
        loc = page.locator("[data-pre-plain-text]")
        cnt = await loc.count()
        self.dlog(f"msg nodes (data-pre-plain-text): {cnt}")
        return [loc.nth(i) for i in range(min(cnt, self.cfg.max_messages_scan))]

    async def _is_outgoing(self, node: Locator) -> bool:
        try:
            anc = node.locator("xpath=ancestor::*[@data-testid='msg-container-out' or contains(@class,'message-out')]")
            return (await anc.count()) > 0
        except Exception:
            return False

    async def _extract_text(self, node: Locator) -> str:
        try:
            t = await node.inner_text()
            return (t or "").strip()
        except Exception:
            return ""

    async def _get_last_outgoing_index(self) -> int:
        nodes = await self._msg_nodes()
        last = -1
        for i, n in enumerate(nodes):
            if await self._is_outgoing(n): last = i
        return last

    async def _collect_messages_after(self, last_index: int) -> List[str]:
        nodes = await self._msg_nodes()
        texts: List[str] = []
        for i, n in enumerate(nodes):
            if i <= last_index: continue
            if await self._is_outgoing(n): continue
            t = await self._extract_text(n)
            if t: texts.append(t)
        self.dlog(f"_collect_messages_after -> {len(texts)} texts")
        return texts

    # ---------- composer / send ----------
    async def _find_composer_candidate(self) -> Tuple[Locator, str]:
        page = self._page; assert page
        candidates = [
            "div[contenteditable='true'][role='textbox']:not([aria-label*='Search' i])",
            "div[contenteditable='true'][data-lexical-editor='true']:not([aria-label*='Search' i])",
            "div[aria-label*='Type a message' i]",
            "div[aria-placeholder*='Type a message' i]",
        ]
        best = None; best_sel = ""; best_y = -1.0
        for sel in candidates:
            loc = page.locator(sel)
            c = await loc.count()
            if not c: continue
            for i in range(min(c, 4)):
                h = loc.nth(i)
                box = await h.bounding_box()
                if not box: continue
                if box["y"] > best_y:
                    best, best_sel, best_y = h, sel, box["y"]
        if best is not None:
            return best, best_sel
        try:
            vw = page.viewport_size or {"width": 1200, "height": 800}
            await page.mouse.click(vw["width"]*0.72, vw["height"]*0.92)
        except Exception:
            pass
        loc = page.locator("div[contenteditable='true'][role='textbox']")
        return loc.first, "fallback: any [contenteditable][role=textbox]"

    async def _count_outgoing_bubbles(self) -> int:
        page = self._page; assert page
        try:
            return await page.locator(
                "//*[@data-testid='msg-container-out'] | //div[contains(@class,'message-out')]"
            ).count()
        except Exception:
            return 0

    async def _click_send_button(self) -> bool:
        page = self._page
        try:
            btn = page.locator(
                "[data-testid='compose-btn-send'],"
                "[data-testid='send'],"
                "button[aria-label*='send' i],"
                "[role='button'][aria-label*='send' i],"
                "span[data-icon='send']"
            )
            if await btn.count():
                await btn.first.click()
                self.dlog("clicked SEND button")
                return True
            self.dlog("SEND button not found")
        except Exception as e:
            self.dlog(f"click SEND exception: {e!r}")
        return False

    async def _send_message_safe(self, body: str, expected_header_title: str) -> bool:
        if not body.strip():
            self.dlog("empty body"); return False
        page = self._page; assert page

        tb, sel_used = await self._find_composer_candidate()
        if not await tb.count():
            self.dlog("composer not found"); return False
        await tb.click()

        try:
            await page.keyboard.down("Control"); await page.keyboard.press("KeyA"); await page.keyboard.up("Control")
        except Exception:
            try:
                await page.keyboard.down("Meta"); await page.keyboard.press("KeyA"); await page.keyboard.up("Meta")
            except Exception: pass
        await page.keyboard.press("Backspace")
        self.dlog(f"composer ready via: {sel_used}")

        before = await self._count_outgoing_bubbles()

        typed = False
        try:
            await tb.fill(body)
            self.dlog(f"filled({len(body)} chars)")
            typed = True
        except Exception as e:
            self.dlog(f"fill failed: {e!r}")
        if not typed:
            try:
                await tb.type(body, delay=10)
                self.dlog(f"tb.type({len(body)} chars)")
                typed = True
            except Exception as e:
                self.dlog(f"tb.type failed: {e!r}")
        if not typed:
            try:
                await page.keyboard.type(body, delay=10)
                self.dlog(f"keyboard.type({len(body)} chars)")
                typed = True
            except Exception as e:
                self.dlog(f"keyboard.type failed: {e!r}")
                return False

        try:
            await tb.press("Enter")
            self.dlog("tb.press Enter")
        except Exception as e:
            self.dlog(f"tb.press Enter failed: {e!r}")
            try:
                await page.keyboard.press("Enter")
                self.dlog("page.keyboard Enter")
            except Exception as e2:
                self.dlog(f"page Enter failed: {e2!r}")

        for _ in range(12):
            await asyncio.sleep(0.25)
            after = await self._count_outgoing_bubbles()
            if after > before:
                self.dlog(f"sent bubble confirmed {before}->{after}")
                return True

        clicked = await self._click_send_button()
        if clicked:
            for _ in range(10):
                await asyncio.sleep(0.25)
                after = await self._count_outgoing_bubbles()
                if after > before:
                    self.dlog(f"sent bubble confirmed after click {before}->{after}")
                    return True

        self.dlog("send NOT confirmed")
        return False

    # ---------- mark unread ----------
    async def _sidebar_item_for_title(self, title: str) -> Locator:
        page = self._page; assert page
        if title:
            loc = page.locator("//div[@role='listitem'][.//span[normalize-space()!='']]", has_text=title)
            if await loc.count(): return loc.first
        return page.locator("//div[@role='listitem']").first

    async def _mark_current_chat_unread(self, header_title: str) -> None:
        page = self._page; assert page
        try:
            item = await self._sidebar_item_for_title(header_title)
            menu_btn = item.locator("xpath=.//*[@aria-label='Open chat context menu' or @aria-label='Open the chat context menu']")
            if await menu_btn.count():
                await menu_btn.first.click()
            else:
                await item.click(button="right")
            mi = page.locator("text=/^Mark as unread$/i")
            if await mi.count():
                await mi.first.click()
                self.dlog("Mark as unread clicked")
                await asyncio.sleep(0.2)
                return
        except Exception as e:
            self.dlog(f"mark unread via menu failed: {e!r}")
        try:
            await page.keyboard.down("Control"); await page.keyboard.down("Shift")
            await page.keyboard.press("KeyU")
        finally:
            try: await page.keyboard.up("Shift"); await page.keyboard.up("Control")
            except Exception: pass
        self.dlog("mark unread via Ctrl+Shift+U")

    # ---------- leave ----------
    async def _leave_to_sidebar(self) -> None:
        page = self._page; assert page
        try:
            lst = page.locator(CHATLIST_SEL)
            if await lst.count():
                await lst.first.click()
                self.dlog("left -> clicked chat list")
                return
        except Exception: pass
        try:
            await page.keyboard.press("Escape")
            self.dlog("left -> pressed Escape")
        except Exception: pass
