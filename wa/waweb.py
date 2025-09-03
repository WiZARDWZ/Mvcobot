# -*- coding: utf-8 -*-
# WhatsApp Web automation — oldest-unread (>=60s), typing-aware,
# precise non-code detection, WA-friendly replies (no "کد:"),
# safe leave (no opening other chats), skip quoted/forwarded header,
# Chrome-only launch, FA/EN UI support, skip muted chats.
# + Greedy tokenizer for back-to-back codes
# + No per-code "unavailable" messages; only one "**" marker when any are unavailable
# + Deep tokenizer debug logs (WA_DEBUG_TOKENS=1)
# + High-Water Mark per-chat to avoid reprocessing old incoming messages
# + Strong "muted" avoidance (before open + after open) with a muted-title cache
# + Robust "Mark as unread" (hotkey-first; no row-click), with banner dismiss
# + Sticky Unread for پیام‌های غیرکُد
# + Unconditional Cooldown after reply/unread (WA_REOPEN_COOLDOWN_SEC, default 420s)
# + FIX: reliable outgoing-bubble counting (message-out), single-shot "**" send (no variants)

import asyncio, os, re, json, time, urllib.request, sys, random, hashlib, unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable, Coroutine, Tuple, Set
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Locator
from playwright.async_api import TimeoutError as PWTimeout

DB_DOWN_MESSAGE = (
    "دسترسی به دیتابیس قطع میباشد , در حال بررسی مشکل هستیم\n"
    "ممنون از شکیبایی شما\n"
    "http://mbaghshomali.ir/"
)

def _now(): return time.strftime("%H:%M:%S")
def _jitter(a=0.25, b=0.6): return random.uniform(a,b)
_DEBUG_TOKENS = (os.getenv("WA_DEBUG_TOKENS", "1").strip() == "1")
def _tokdbg(msg: str):
    if _DEBUG_TOKENS:
        print(f"[{_now()}] TOKDBG | {msg}", flush=True)

# ===== selectors =====
CHATLIST_SEL = "[role='grid'][aria-label*='Chat list' i]"
UNREAD_ITEM_XPATH = (
    "//div[@role='listitem']"
    "[.//span[contains(@aria-label,'unread') or contains(@aria-label,'خوانده نشده')]]"
)
MUTED_ICON_XPATH = (
    ".//*[@data-icon='muted' or @aria-label='muted' or contains(@aria-label,'muted') "
    "or contains(@aria-label,'بی‌صدا') or contains(@aria-label,'بی‌ صد') "
    "or @data-testid='icon-mute' or @data-testid='muted']"
)
_MUTE_ATTR_RE = re.compile(
    r"(mute|muted|icon-mute|icon-muted|notifications?-?off|bell|bell-slash|silent|silence|بی.?صدا)",
    re.IGNORECASE
)

HEADER_CANDIDATES = [
    "[data-testid='conversation-info-header-chat-title']",
    "header [title]", "header h1", "header span[dir='auto']", "header span[title]",
]
SEARCH_INPUT_CANDIDATES = [
    "[data-testid='chat-list-search']",
    "div[contenteditable='true'][role='textbox'][aria-label*='Search' i]",
    "div[contenteditable='true'][role='textbox'][aria-label*='جستجو' i]",
]

# ===== tokenizer / noise =====
_FULL_ANCH = re.compile(r'^([A-Za-z0-9]{5})(?:[-_/\. ]+)?([A-Za-z0-9]{5})')
_FULL_WITH_SUFFIX_ANCH = re.compile(r'^([A-Za-z0-9]{5})(?:[-_/\. ]+)?([A-Za-z0-9]{5})([A-Za-z]+)')
_PARTIAL_ANCH = re.compile(r'^([A-Za-z0-9]{5})(?:[-_/\. ]+)?([A-Za-z0-9]{2,4})')

QUALIFIER_WHITELIST = {
    "gen","genuine","asli","alsi","oem","original","org","fab","fabric","factory",
    "new","ok","okey","good","cn","kr","ae","me","ko","rh","lh",
    "اصلی","اورجینال","فابریک","فابريك","جنیون","جنیون/اصلی","اصل","اورج",
}
FORCE_NOISE_REGEX = re.compile(
    r"(سلام|salam|hello|hi|"
    r"فاکتور|فاكتور|factor|faktor|invoice|"
    r"ارسال|پیک|پيك|تحویل|"
    r"قیمت|price|چند|چنده|"
    r"می\s?شه|لطفاً|لطفا|please|pls|plz|"
    r"بفرست|بزن|میخوام|می‌خوام|want|"
    r"موجودی|availability|موجودید|"
    r"کی\s?میاد|کِی\s?میاد|کجا|where|when|"
    r"عدد)",
    re.IGNORECASE
)

def _normalize_bidi_digits_dashes(s: str) -> str:
    s = (s or "")
    s = s.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹","0123456789"))
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩","0123456789"))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Cf")
    s = s.replace("\u00AD","").replace("\uFEFF","")
    s = s.replace("\u200D","").replace("\u200C","")
    s = re.sub(r'[‐‒–—⁃−﹘﹣-]', '-', s)
    s = s.replace('\u00A0', ' ').replace("\u202F"," ").replace("\u2007"," ").replace("\u2009"," ")
    return s

def _normalize_key(code: str) -> str:
    cleaned = re.sub(r'[\u202d\u202c\u2068\u2069\u200e\u200f\u200b\u200c\u200d\u2060\uFEFF\u00AD]', '', code or '')
    return re.sub(r'[-_/\.\s]', '', cleaned).upper()

def _has_ascii_digit(s: str) -> bool:
    return bool(re.search(r'\d', s or ""))

_SINGLELINE_EXPORT_RE = re.compile(r'^\s*\[[^\]]+\]\s*[^:]{1,80}:\s*(.+)$')

def _strip_quote_block(text: str) -> str:
    raw_in = text or ""
    text = _normalize_bidi_digits_dashes(raw_in)
    parts = [ln for ln in text.splitlines()]
    if not parts:
        return text
    if len(parts) >= 2 and (parts[0].endswith(":") or parts[0].endswith("…") or len(parts[0].strip()) <= 3):
        parts = parts[1:]
    if len(parts) == 1:
        m = _SINGLELINE_EXPORT_RE.match(parts[0])
        if m:
            _tokdbg(f"single-line export header trimmed: '{parts[0]}' -> '{m.group(1)}'")
            parts[0] = m.group(1)
    while parts and not parts[0].strip():
        parts = parts[1:]
    return "\n".join([p for p in parts if p.strip()]).strip()

def _greedy_scan_tokens(raw: str) -> Tuple[List[dict], List[Tuple[int,int]]]:
    tokens: List[dict] = []
    spans: List[Tuple[int,int]] = []
    i = 0
    n = len(raw)
    while i < n:
        seg = raw[i:]
        cands: List[Tuple[str, re.Match]] = []
        m2 = _FULL_WITH_SUFFIX_ANCH.match(seg)
        if m2: cands.append(("full_suf", m2))
        m1 = _FULL_ANCH.match(seg)
        if m1: cands.append(("full", m1))
        m3 = _PARTIAL_ANCH.match(seg)
        if m3: cands.append(("partial", m3))
        if not cands:
            i += 1
            continue
        cands.sort(key=lambda x: (x[1].end(), {"full_suf":2,"full":1,"partial":0}[x[0]]), reverse=True)
        typ, m = cands[0]
        s, e = i + m.start(), i + m.end()
        text_match = raw[s:e]
        if typ == "full_suf":
            g1, g2 = m.group(1), m.group(2)
            disp = f"{g1}-{g2}"
            norm = _normalize_key(g1+g2)
            is_full = True
        elif typ == "full":
            disp = text_match
            norm = _normalize_key(text_match)
            is_full = True
        else:
            g1, g2 = m.group(1), m.group(2)
            disp = f"{g1}-{g2}"
            norm = _normalize_key(g1+g2)
            is_full = False
        if _has_ascii_digit(norm):
            tokens.append({"norm": norm, "display": disp, "is_full": is_full})
            spans.append((s, e))
            _tokdbg(f"scan match @{s}..{e} typ={typ} text={repr(text_match)} -> disp={repr(disp)}")
            i = e
        else:
            i += 1
    seen: Set[Tuple[str,bool]] = set()
    dedup: List[dict] = []
    for t in tokens:
        key = (t["norm"], t["is_full"])
        if key not in seen:
            seen.add(key)
            dedup.append(t)
    return dedup, spans

def _extract_tokens_and_noise(text: str) -> Tuple[List[dict], bool]:
    _tokdbg(f"input: {repr(text)}")
    try:
        import importlib
        inv = importlib.import_module("inventory")
        for fname in ("extract_tokens_and_noise", "extract_tokens", "parse_codes", "parse_tokens"):
            fx = getattr(inv, fname, None)
            if callable(fx):
                res = fx(text)
                if isinstance(res, tuple) and len(res) == 2:
                    toks, noise = res
                    if toks and isinstance(toks[0], str):
                        toks = [{"norm": _normalize_key(t), "display": t, "is_full": (len(_normalize_key(t))>=10)} for t in toks]
                    _tokdbg(f"inventory extractor used -> tokens={toks} noise={noise}")
                    return toks, bool(noise)
                elif isinstance(res, list):
                    toks = [{"norm": _normalize_key(t), "display": t, "is_full": (len(_normalize_key(t))>=10)} for t in res]
                    _tokdbg(f"inventory extractor used -> tokens={toks} noise=False")
                    return toks, False
                break
    except Exception as e:
        _tokdbg(f"inventory extractor not used: {e!r}")

    raw = _normalize_bidi_digits_dashes(text)
    _tokdbg(f"normalized: {repr(raw)}")
    if not _has_ascii_digit(raw):
        _tokdbg("no ascii digit -> noise=True")
        return [], True
    tokens, spans = _greedy_scan_tokens(raw)
    _tokdbg(f"tokens(dedup): {tokens}")
    if not tokens:
        _tokdbg("no tokens -> noise=True")
        return [], True
    chars = list(raw)
    for s,e in spans:
        for k in range(s,e):
            chars[k] = ' '
    leftover = ''.join(chars)
    force = FORCE_NOISE_REGEX.search(leftover) is not None
    words = [w for w in re.split(r"[^\w\u0600-\u06FF]+", leftover) if w]
    norm_words = [w for w in (w.strip().lower() for w in words) if len(w) > 1]
    bad_words, ok_words = [], []
    for w in norm_words:
        if w.isdigit(): continue
        if (w in QUALIFIER_WHITELIST) or w.endswith("oem") or w.startswith("oem"):
            ok_words.append(w)
        else:
            bad_words.append(w)
    _tokdbg(f"leftover: {repr(leftover)} | words={norm_words} | ok={ok_words} | bad={bad_words} | force_noise={force}")
    if force or bad_words:
        _tokdbg("result: noise=True")
        return tokens, True
    _tokdbg("result: noise=False")
    return tokens, False

# ===== reply massaging =====
_DELIVERY_LINE = re.compile(r"(تحویل|ارسال|دقیقه|انبار|دفتر|پنج.?شنبه)", re.I)
_EMO_DELIVERY  = re.compile(r"[🚚🛵]")
_CODE_LINE_MD = re.compile(r"^\s*(?:\*+)?\s*کد\s*[:：]\s*(?:\*+)?`?([^\n`]+?)`?\s*(?:\*+)?\s*$")

def _strip_delivery_lines(txt: str) -> str:
    lines = []
    for ln in (txt or "").splitlines():
        if _EMO_DELIVERY.search(ln) or _DELIVERY_LINE.search(ln):
            continue
        lines.append(ln)
    return "\n".join(lines).strip()

def _massage_reply_for_wa(txt: str) -> str:
    t = (txt or "").replace("\u200f","").replace("\u200e","")
    t = _strip_delivery_lines(t)
    t = t.replace("*کد:*", "کد:").replace("*برند:*", "برند:").replace("*قیمت:*", "قیمت:")
    t = t.replace("*", "").replace("`", "").strip()
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    if not lines: return ""
    new_lines: List[str] = []
    code_line = ""
    for ln in lines:
        m = _CODE_LINE_MD.match(ln) or (ln.strip().startsWith("کد:") and re.match(r"^\s*کد\s*[:：]\s*(.+)$", ln))
        if m:
            code_line = (m.group(1) if hasattr(m, "group") else re.sub(r"^\s*کد\s*[:：]\s*", "", ln)).strip()
            continue
        new_lines.append(ln)
    out: List[str] = []
    if code_line: out.append(code_line)
    out.extend(new_lines)
    return "\n".join(out).strip()

# ===== Telegram notify =====
def _tg_env(): return os.getenv("TG_BOT_TOKEN"), os.getenv("TG_ADMIN_CHAT_ID")
def notify_admin(text: str) -> None:
    tok, cid = _tg_env()
    if not tok or not cid: return
    try:
        url = f"https://api.telegram.org/bot{tok}/sendMessage"
        data = json.dumps({"chat_id": cid, "text": text, "parse_mode": "HTML"}).encode("utf-8")
        urllib.request.urlopen(urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"}), timeout=10)
    except Exception:
        pass

@dataclass
class WAConfig:
    user_data_dir: str = "./.wa-user-data"
    headless: bool = False
    slow_mo_ms: int = 100
    idle_scan_interval_sec: float = 10.0
    min_unread_age_sec: int = 60
    start_url: str = "https://web.whatsapp.com/"
    max_messages_scan: int = 500
    ensure_header_on_send: bool = True
    debug_send_dot_if_no_reply: bool = False
    debug_tag: str = "WADEBUG"
    browser_channel: Optional[str] = None
    executable_path: Optional[str] = None
    prefer_chrome_only: bool = True

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
        self._pw = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self.log = logger or (lambda m: print(m, flush=True))
        self._first_seen_unread: Dict[str, float] = {}
        self._processing: Set[str] = set()
        self._last_incoming_marker_by_chat: Dict[str, str] = {}
        self._muted_titles_cache: Set[str] = set()
        self._sticky_unread_titles: Dict[str, float] = {}
        self._cooldown_until: Dict[str, float] = {}
        try:
            self._reopen_cooldown_sec = float(os.getenv("WA_REOPEN_COOLDOWN_SEC", "420") or "420")
        except Exception:
            self._reopen_cooldown_sec = 420.0

    def dlog(self, msg: str): self.log(f"[{_now()}] {self.cfg.debug_tag} | {msg}")
    def set_interval(self, sec: float):
        try: self.cfg.idle_scan_interval_sec = max(2.0, float(sec))
        except Exception: pass

    # ---------- lifecycle ----------
    async def start(self) -> None:
        self._pw = await async_playwright().start()
        launch_kwargs = dict(
            user_data_dir=self.cfg.user_data_dir,
            headless=self.cfg.headless,
            slow_mo=self.cfg.slow_mo_ms,
            args=["--disable-blink-features=AutomationControlled","--disable-dev-shm-usage","--no-sandbox"],
        )
        attempts: List[Tuple[str,str]] = []
        env_ch  = (os.getenv("WA_BROWSER_CHANNEL") or "").strip().lower()
        env_exe = os.getenv("WA_BROWSER_EXE") or os.getenv("CHROME_PATH")

        if self.cfg.browser_channel:
            if self.cfg.browser_channel.lower() == "chrome":
                attempts.append(("channel", "chrome"))
        elif env_ch == "chrome":
            attempts.append(("channel", "chrome"))
        if self.cfg.executable_path:
            attempts.append(("exe", self.cfg.executable_path))
        elif env_exe:
            attempts.append(("exe", env_exe))
        if sys.platform.startswith("win"):
            attempts += [("channel","chrome")]
            attempts += [("exe", p) for p in (
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            )]
        else:
            attempts += [("exe", p) for p in (
                "/usr/bin/google-chrome",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            )]
            attempts += [("channel","chrome")]

        last_error: Optional[Exception] = None
        for kind,val in attempts:
            try:
                if kind=="channel":
                    self._browser = await self._pw.chromium.launch_persistent_context(channel=val, **launch_kwargs)
                else:
                    if not os.path.exists(val):
                        self.dlog(f"launch attempt exe={val} skipped (not found)")
                        continue
                    self._browser = await self._pw.chromium.launch_persistent_context(executable_path=val, **launch_kwargs)
                self.dlog(f"launched via {kind}={val}")
                break
            except Exception as e:
                last_error=e; self.dlog(f"launch attempt {kind}={val} failed: {e!r}")
        if not self._browser:
            raise last_error or RuntimeError("No suitable Chrome found.")
        self._context = self._browser  # type: ignore
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
        self.dlog("goto web.whatsapp.com")
        await self._page.goto(self.cfg.start_url, wait_until="domcontentloaded")
        try: await self._page.wait_for_load_state("networkidle", timeout=60_000)
        except PWTimeout: pass
        await self._ensure_ready()
        self.dlog("READY")

    async def stop(self):
        try:
            if self._context: await self._context.close()
        except Exception: pass
        try:
            if self._pw: await self._pw.stop()
        except Exception: pass
        self._context = None; self._page = None; self._browser = None; self._pw = None

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

    # ---------- helpers ----------
    async def _is_typing(self, item: Locator) -> bool:
        try:
            if await item.locator("xpath=.//span[contains(@aria-label,'typing') or contains(., 'typing')]").count():
                return True
            if await item.get_by_text(re.compile(r"در حال تایپ|typing", re.I)).count():
                return True
        except Exception:
            pass
        return False

    async def _is_muted(self, item: Locator) -> bool:
        try:
            if (await item.locator(f"xpath={MUTED_ICON_XPATH}").count()) > 0:
                self.dlog("row mute detected: xpath=MUTED_ICON_XPATH")
                return True
        except Exception:
            pass
        try:
            ar = (await item.get_attribute("aria-label")) or ""
            if _MUTE_ATTR_RE.search(ar or ""):
                self.dlog(f"row mute detected: aria-label={ar!r}")
                return True
        except Exception:
            pass
        try:
            found = await item.evaluate("""(el) => {
                const attrText = (n) => (
                  (n.getAttribute('data-icon')||'')+' '+
                  (n.getAttribute('aria-label')||'')+' '+
                  (n.getAttribute('data-testid')||'')+' '+
                  (n.getAttribute('title')||'')
                ).toLowerCase();
                const nodes = el.querySelectorAll('[data-icon],[aria-label],[data-testid],[title],svg]');
                let hit = '';
                const re = /(mute|muted|icon-mute|icon-muted|notifications?-?off|bell|bell-slash|silent|silence|بی.?صدا)/i;
                let cnt = 0;
                for (const n of nodes) {
                    cnt++;
                    if (cnt > 150) break;
                    const t = (n.tagName.toLowerCase()==='svg')
                        ? ((n.getAttribute('aria-label')||'') + ' ' + (n.getAttribute('data-testid')||'')).toLowerCase()
                        : attrText(n);
                    if (re.test(t)) { hit = t; break; }
                }
                return hit || null;
            }""")
            if found:
                self.dlog(f"row mute detected: attr-scan hit={found!r}")
                return True
        except Exception:
            pass
        try:
            if await item.get_by_role("img", name=_MUTE_ATTR_RE).count():
                self.dlog("row mute detected: role img name")
                return True
        except Exception:
            pass
        return False

    async def _is_current_chat_muted(self) -> bool:
        page = self._page; assert page
        try:
            hdr = page.locator("header")
            if await hdr.locator("xpath=.//*[@data-icon='muted' or @aria-label='muted' or contains(@aria-label,'muted') or contains(., 'بی‌صدا') or contains(., 'muted')]").count():
                return True
            if await hdr.get_by_role("img", name=_MUTE_ATTR_RE).count():
                return True
            if await hdr.locator("[data-testid*='mute' i]").count():
                return True
        except Exception:
            pass
        return False

    async def _chat_item_key(self, item: Locator) -> str:
        try:
            title = await self._guess_item_title(item)
        except Exception:
            title = ""
        snippet = ""
        try:
            snippet = (await item.inner_text()) or ""
        except Exception:
            pass
        snippet = re.sub(r"(در حال تایپ|typing|recording|در حال ضبط|voice message|پیام صوتی)", "", snippet, flags=re.I)
        snippet = _normalize_bidi_digits_dashes(snippet)[:200]
        raw = (title + "||" + snippet).strip()
        digest = hashlib.sha1(raw.encode("utf-8","ignore")).hexdigest()
        return f"{title}::{digest[:10]}"

    async def _is_in_chat(self) -> bool:
        page = self._page; assert page
        try:
            if await page.locator("[role='dialog'], [data-testid='drawer-right']").count():
                return False
        except Exception:
            pass
        try:
            tb, _ = await self._find_composer_candidate()
            return (await tb.count()) > 0 and await tb.is_visible()
        except Exception:
            return False

    async def _node_marker(self, node: Locator) -> str:
        try:
            pre = (await node.get_attribute("data-pre-plain-text")) or ""
        except Exception:
            pre = ""
        body = await self._extract_text(node)
        h = hashlib.sha1((pre + "||" + body).encode("utf-8","ignore")).hexdigest()[:10]
        return f"{pre}|{h}"

    async def _msg_nodes(self) -> List[Locator]:
        page = self._page; assert page
        loc = page.locator("[data-pre-plain-text]")
        cnt = await loc.count()
        self.dlog(f"msg nodes (data-pre-plain-text): {cnt}")
        return [loc.nth(i) for i in range(min(cnt, self.cfg.max_messages_scan))]

    async def _is_outgoing(self, node: Locator) -> bool:
        try:
            pre = await node.get_attribute("data-pre-plain-text")
            if pre and ("You:" in pre or "You\u200f:" in pre or "You :" in pre):
                return True
        except Exception:
            pass
        try:
            anc = node.locator("xpath=ancestor::div[contains(@class,'message-out')]")
            return await anc.count() > 0
        except Exception:
            return False

    async def _extract_text(self, node: Locator) -> str:
        try:
            txt = await node.evaluate("""(el) => {
                const els = el.querySelectorAll('.selectable-text.copyable-text');
                if (els && els.length) {
                    let out = '';
                    els.forEach(e => { out += (e.innerText || e.textContent || ''); });
                    return out.trim();
                }
                return (el.innerText || el.textContent || '')?.trim() || '';
            }""")
            if txt:
                return txt
        except Exception:
            pass
        try:
            leafs = node.locator(".selectable-text.copyable-text")
            if await leafs.count():
                texts = []
                for i in range(await leafs.count()):
                    t = await leafs.nth(i).inner_text()
                    if t: texts.append(t)
                if texts:
                    return " ".join(texts).strip()
        except Exception:
            pass
        try:
            t = await node.inner_text()
            return (t or "").strip()
        except Exception:
            return ""

    async def _get_last_outgoing_index(self) -> int:
        nodes = await self._msg_nodes()
        last = -1
        for i,n in enumerate(nodes):
            if await self._is_outgoing(n): last = i
        return last

    async def _collect_incoming_info_after(self, last_outgoing_index: int) -> List[Tuple[str,str]]:
        nodes = await self._msg_nodes()
        infos: List[Tuple[str,str]] = []
        for i,n in enumerate(nodes):
            if i <= last_outgoing_index: continue
            if await self._is_outgoing(n): continue
            marker = await self._node_marker(n)
            text = await self._extract_text(n)
            if text:
                infos.append((marker, text))
        self.dlog(f"_collect_incoming_info_after -> {len(infos)} items")
        return infos

    # ---------- unread badge info ----------
    async def _unread_badge_info(self, item: Locator) -> Dict[str, Any]:
        try:
            info = await item.evaluate("""
            (el) => {
                const mapDigits = (s) => {
                    const fa='۰۱۲۳۴۵۶۷۸۹', ar='٠١٢٣٤٥٦٧٨٩';
                    let out=''; for (const ch of (s||'')) {
                        const i1=fa.indexOf(ch); if (i1>=0){out+=String(i1);continue;}
                        const i2=ar.indexOf(ch); if (i2>=0){out+=String(i2);continue;}
                        out+=ch;
                    } return out;
                };
                const res={count:0,dot:false,mention:false};
                const nodes=el.querySelectorAll("[aria-label],[title],[data-testid],[data-icon],svg");
                for (const n of nodes){
                    const label=((n.getAttribute('aria-label')||'')+' '+(n.getAttribute('title')||'')+' '+
                                 (n.getAttribute('data-testid')||'')+' '+(n.getAttribute('data-icon')||'')).toLowerCase();
                    const txt=(n.innerText||n.textContent||'').trim();
                    const snap=mapDigits(label+' '+txt);
                    const m=snap.match(/(^|\\s)(\\d{1,4})(?=\\s|$)/);
                    if (m){ const v=parseInt(m[2],10); if (!isNaN(v)) res.count=Math.max(res.count,v); }
                    if (label.includes('mention')) res.mention=true;
                }
                if (res.count===0){
                    const dotNode=el.querySelector("[data-icon='notification'],[data-testid='notification'],[data-testid*='unread'] svg");
                    if (dotNode) res.dot=true;
                }
                return res;
            }
            """)
            return {
                "count": int(info.get("count", 0) or 0),
                "dot": bool(info.get("dot", False)),
                "mention": bool(info.get("mention", False)),
            }
        except Exception as e:
            self.dlog(f"_unread_badge_info error: {e!r}")
            return {"count": 0, "dot": False, "mention": False}

    # ---------- core ----------
    async def process_unread_chats_once(self) -> None:
        page = self._page; assert page
        # GC cooldowns
        now_ts = time.time()
        for t, until in list(self._cooldown_until.items()):
            if until <= now_ts:
                self._cooldown_until.pop(t, None)

        items = await self._find_unread_items()
        self.dlog(f"unread items found: {len(items)}")

        # Build unread titles (for sticky/cooldown GC)
        unread_titles: Set[str] = set()
        for it in items:
            try:
                t = await self._guess_item_title(it)
                if t: unread_titles.add(t)
            except Exception: pass

        # GC first_seen_unread for vanished rows
        try:
            current_keys = set()
            for it in items:
                k = await self._chat_item_key(it)
                current_keys.add(k)
            for k in [k for k in list(self._first_seen_unread.keys()) if k not in current_keys]:
                self._first_seen_unread.pop(k, None)
        except Exception: pass

        # GC sticky cache
        try:
            for title, ts in list(self._sticky_unread_titles.items()):
                if (title not in unread_titles) or (now_ts - ts > 72 * 3600):
                    self._sticky_unread_titles.pop(title, None)
        except Exception: pass

        if not items:
            self.log("… no unread chats"); return

        candidates: List[Tuple[Locator, str, float, float, str]] = []
        now_ts = time.time()
        for it in items:
            try:
                title_guess = await self._guess_item_title(it)
            except Exception:
                title_guess = ""

            # cooldown skip
            if title_guess and (self._cooldown_until.get(title_guess, 0) > now_ts):
                left = int(self._cooldown_until[title_guess] - now_ts)
                self.dlog(f"skip by cooldown ({left}s) row: {title_guess}")
                continue

            # muted skip
            if title_guess and title_guess in self._muted_titles_cache:
                self.dlog(f"skip (muted cache) row: {title_guess}")
                continue
            try:
                if await self._is_muted(it):
                    self.dlog("skip muted chat row (icon/attr/role)")
                    if title_guess: self._muted_titles_cache.add(title_guess)
                    continue
            except Exception: pass

            # open only if it has a numeric unread badge (skip dot-only)
            try:
                badge = await self._unread_badge_info(it)
                if badge.get("count", 0) <= 0:
                    self.dlog(f"skip unread (dot-only) row: {title_guess or '—'}")
                    continue
            except Exception as e:
                self.dlog(f"badge check failed: {e!r}")

            key = await self._chat_item_key(it)
            if await self._is_typing(it): continue
            if key not in self._first_seen_unread:
                self._first_seen_unread[key] = now_ts
            seen_ts = self._first_seen_unread.get(key, now_ts)
            try:
                box = await it.bounding_box(); y = box["y"] if box else 0.0
            except Exception:
                y = 0.0
            if key in self._processing: continue
            candidates.append((it, key, seen_ts, y, title_guess))

        eligible = [(it,k,seen,y,t) for (it,k,seen,y,t) in candidates if (now_ts - seen) >= self.cfg.min_unread_age_sec]
        if not eligible:
            if candidates:
                rem = min(max(0, self.cfg.min_unread_age_sec - (now_ts - c[2])) for c in candidates)
                self.dlog(f"… unread exists but waiting for {int(rem)}s age (min={self.cfg.min_unread_age_sec}s)")
            else:
                self.dlog("… unread exists but (typing/in-progress or muted)")
            return

        eligible.sort(key=lambda x: (x[2], x[3]))
        item, key, _, _, row_title_guess = eligible[0]

        if key in self._processing: return
        self._processing.add(key)
        try:
            self.dlog(f"opening chat item, title guess: {row_title_guess or '—'}")
            if not await self._open_chat_item(item):
                self.dlog("open chat failed"); return

            header_title = await self._get_header_title()
            self.dlog(f"active header: {header_title or '—'}")
            chat_id_key = header_title or row_title_guess or key

            # after-open muted check
            if await self._is_current_chat_muted():
                self.dlog("current chat is muted -> skip responding & leave")
                if header_title: self._muted_titles_cache.add(header_title)
                await asyncio.sleep(_jitter(0.4, 0.7))
                await self._leave_to_sidebar(force_hard=True)
                try: self._first_seen_unread.pop(key, None)
                except Exception: pass
                return

            sticky_preopen = bool(header_title and (header_title in self._sticky_unread_titles or row_title_guess in self._sticky_unread_titles))

            last_out_idx = await self._get_last_outgoing_index()
            self.dlog(f"last outgoing index: {last_out_idx}")

            infos = await self._collect_incoming_info_after(last_outgoing_index=last_out_idx)
            await asyncio.sleep(3.0)
            infos2 = await self._collect_incoming_info_after(last_outgoing_index=last_out_idx)
            if len(infos2) > len(infos): infos = infos2
            self.dlog(f"new incoming after last outgoing: {len(infos)}")

            if not infos:
                await self._leave_to_sidebar(force_hard=True)
                return

            last_marker = self._last_incoming_marker_by_chat.get(chat_id_key, "")
            start_idx = 0
            if last_marker:
                for i,(m,_) in enumerate(infos):
                    if m == last_marker:
                        start_idx = i + 1
                        break
            fresh_infos = infos[start_idx:]
            msgs = [t for (_,t) in fresh_infos]
            self.dlog(f"fresh messages after HWM: {len(msgs)} (start_idx={start_idx})")
            if not msgs:
                await self._leave_to_sidebar(force_hard=True)
                return

            tokens_all: List[dict] = []
            had_noise_any = False
            for m in msgs:
                original = m
                m = _strip_quote_block(m)
                _tokdbg(f"message-line: {repr(original)} -> stripped: {repr(m)}")
                toks, noise = _extract_tokens_and_noise(m)
                tokens_all.extend(toks); had_noise_any = had_noise_any or noise
            self.dlog(f"tokens: {[(t['display'], t['is_full']) for t in tokens_all]} | noise={had_noise_any}")

            sent_any = False
            attempted_reply = False
            had_unavail = False
            did_query = False

            if tokens_all and self.on_codes:
                did_query = True
                codes_for_query = [t["display"] for t in tokens_all]
                try:
                    raw_replies = await self.on_codes(codes_for_query, {"title": header_title}) or []
                except Exception as e:
                    self.dlog(f"on_codes raised: {e!r}")
                    raw_replies = [DB_DOWN_MESSAGE]

                def _is_available(txt: str) -> bool:
                    t = (txt or "").replace("\u200f","").strip()
                    return ("قیمت" in t) or ("ریال" in t)

                def _is_unavailable(txt: str) -> bool:
                    t = (txt or "").replace("\u200f","").strip()
                    return ("موجود" in t and "نمی‌باشد" in t) or t.strip() == "ناموجود" or t.strip() == "**"

                avail_blocks: List[str] = []
                for t in raw_replies:
                    if _is_available(t):
                        msg = _massage_reply_for_wa(t)
                        if msg: avail_blocks.append(msg)
                    elif _is_unavailable(t):
                        had_unavail = True

                if avail_blocks or had_unavail:
                    attempted_reply = True

                for b in avail_blocks:
                    ok = await self._send_message_safe(b, expected_header_title=header_title)
                    self.dlog(f"send available -> {'OK' if ok else 'FAIL'}")
                    sent_any |= ok
                    await asyncio.sleep(_jitter())

                if had_unavail and did_query:
                    ok2 = await self._send_unavail_marker(expected_header_title=header_title)
                    self.dlog(f"send unavailable marker -> {'OK' if ok2 else 'FAIL'}")
                    sent_any |= ok2

            # نویزِ بدون کُد → Unread + تلگرام + cooldown
            if not tokens_all and had_noise_any:
                self.dlog("non-code present -> mark unread & notify")
                _ = await self._mark_current_chat_unread(header_title)
                if header_title:
                    self._cooldown_until[header_title] = time.time() + self._reopen_cooldown_sec
                    self.dlog(f"cooldown set for '{header_title}' ({int(self._reopen_cooldown_sec)}s)")
                preview = (msgs[-1] if msgs else "")[:200].replace("<","‹").replace(">","›")
                notify_admin("🔔 <b>پیام غیرکُد</b> در چت «<code>{}</code>»\nآخرین پیام: <i>{}</i>".format(
                    header_title or "بدون‌عنوان", preview
                ))
                await self._post_unread_hard_leave()
                return

            # اگر پاسخی دادیم (یا تلاش کردیم)، بلافاصله Unread + cooldown + خروج سفت
            if attempted_reply and header_title:
                await asyncio.sleep(_jitter(0.25, 0.45))
                ok_unread = await self._mark_current_chat_unread(header_title)
                self.dlog(f"force re-Mark as unread after reply attempt -> {'OK' if ok_unread else 'FAIL'}")
                self._cooldown_until[header_title] = time.time() + self._reopen_cooldown_sec
                self.dlog(f"cooldown set for '{header_title}' ({int(self._reopen_cooldown_sec)}s)")
                await self._post_unread_hard_leave()
                return

            # سازگاری با sticky قدیمی
            if sent_any and sticky_preopen and header_title and not attempted_reply:
                self.dlog("re-applying unread because sticky was active and bot replied")
                await self._mark_current_chat_unread(header_title)

            if self.cfg.debug_send_dot_if_no_reply and did_query and not sent_any:
                ok = await self._send_message_safe(".", expected_header_title=header_title)
                self.dlog(f"send debug dot -> {'OK' if ok else 'FAIL'}")

            try: self._last_incoming_marker_by_chat[chat_id_key] = infos[-1][0]
            except Exception: pass
            try: self._first_seen_unread.pop(key, None)
            except Exception: pass

            await asyncio.sleep(_jitter(0.8, 1.2))
            await self._leave_to_sidebar(force_hard=True)
        finally:
            self._processing.discard(key)

    # ---------- unread / open ----------
    async def _find_unread_items(self) -> List[Locator]:
        page = self._page; assert page
        items = page.locator(f"xpath={UNREAD_ITEM_XPATH}")
        cnt = await items.count()
        return [items.nth(i) for i in range(cnt)]

    async def _guess_item_title(self, item: Locator) -> str:
        try:
            cap = item.locator("xpath=.//span[@dir='auto' or @title][normalize-space()!='']")
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
                    if txt: return txt
            except Exception:
                continue
        return ""

    async def _dismiss_top_banner_if_present(self) -> bool:
        page = self._page; assert page
        try:
            cand_text = page.get_by_text(re.compile(r"reach new customer|reach new customers", re.I))
            close_btn = page.locator("button[aria-label*='Close' i], [data-testid*='dismiss' i], [data-icon='x']")
            banner = page.locator("[data-testid*='banner' i], [role='complementary'], [data-animate-modal-body='true']")
            hit = False
            if await close_btn.count():
                await close_btn.first.click(); hit = True
            elif await cand_text.count():
                par = cand_text.first.locator("xpath=ancestor::*[1]//button")
                if await par.count():
                    await par.first.click(); hit = True
            elif await banner.count():
                await self._page.keyboard.press("Escape"); hit = True
            if hit:
                self.dlog("banner dismissed (if present)")
                await asyncio.sleep(0.15)
                return True
        except Exception as e:
            self.dlog(f"banner dismiss failed: {e!r}")
        return False

    async def _open_chat_item(self, item: Locator) -> bool:
        page = self._page; assert page
        async def opened_ok() -> bool:
            try:
                n = await page.locator("[data-pre-plain-text]").count()
                if n > 0: return True
            except Exception: pass
            tb,_ = await self._find_composer_candidate()
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
    async def _collect_messages_after(self, last_outgoing_index: int) -> List[str]:
        nodes = await self._msg_nodes()
        texts: List[str] = []
        for i,n in enumerate(nodes):
            if i <= last_outgoing_index: continue
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
        best=None; best_sel=""; best_y=-1.0
        for sel in candidates:
            loc = page.locator(sel); c = await loc.count()
            if not c: continue
            for i in range(min(c,4)):
                h = loc.nth(i); box = await h.bounding_box()
                if not box: continue
                if box["y"] > best_y: best, best_sel, best_y = h, sel, box["y"]
        if best is not None: return best, best_sel
        try:
            vw = page.viewport_size or {"width":1200,"height":800}
            await page.mouse.click(vw["width"]*0.72, vw["height"]*0.92)
        except Exception: pass
        loc = page.locator("div[contenteditable='true'][role='textbox']")
        return loc.first, "fallback: any [contenteditable][role=textbox]"

    async def _count_outgoing_bubbles(self) -> int:
        page = self._page; assert page
        try:
            cnt = await page.locator("div.message-out").count()
            if cnt > 0:
                return cnt
            return await page.locator("div.message-out [data-pre-plain-text]").count()
        except Exception:
            return 0

    async def _composer_empty(self, tb: Locator) -> bool:
        try:
            txt = await tb.evaluate("(el)=> (el.innerText||el.textContent||'').trim()")
            return len(txt or "") == 0
        except Exception:
            return False

    async def _send_message_safe(self, body: str, expected_header_title: str) -> bool:
        if not body.strip():
            self.dlog("empty body"); return False
        page = self._page; assert page

        if self.cfg.ensure_header_on_send and expected_header_title:
            try:
                cur = await self._get_header_title()
                if (cur or "").strip() != (expected_header_title or "").strip():
                    self.dlog(f"header changed; expected={expected_header_title!r} got={cur!r}")
                    return False
            except Exception: pass

        tb, sel_used = await self._find_composer_candidate()
        if not await tb.count(): self.dlog("composer not found"); return False
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
        typed=False
        try:
            await tb.fill(body); self.dlog(f"filled({len(body)} chars)"); typed=True
        except Exception as e:
            self.dlog(f"fill failed: {e!r}")
        if not typed:
            try: await tb.type(body, delay=10); self.dlog(f"tb.type({len(body)} chars)"); typed=True
            except Exception as e: self.dlog(f"tb.type failed: {e!r}")
        if not typed:
            try: await page.keyboard.type(body, delay=10); self.dlog(f"keyboard.type({len(body)} chars)"); typed=True
            except Exception as e: self.dlog(f"keyboard.type failed: {e!r}"); return False

        try:
            await page.keyboard.press("Enter"); self.dlog("pressed Enter")
        except Exception as e:
            self.dlog(f"press Enter failed: {e!r}")

        for _ in range(12):
            await asyncio.sleep(0.25)
            after = await self._count_outgoing_bubbles()
            if after > before:
                self.dlog(f"sent bubble confirmed {before}->{after}")
                return True

        if body.strip() == "**":
            try:
                if await self._composer_empty(tb):
                    self.dlog("composer empty after '**' -> treating as sent")
                    return True
            except Exception:
                pass
            self.dlog("send NOT confirmed for '**'")
            return False

        try:
            btn = page.locator("[data-testid='compose-btn-send'], button[aria-label*='send' i]")
            if await btn.count():
                await btn.first.click(); self.dlog("clicked SEND button")
                for _ in range(10):
                    await asyncio.sleep(0.25)
                    after = await self._count_outgoing_bubbles()
                    if after > before:
                        self.dlog(f"sent bubble confirmed after click {before}->{after}")
                        return True
            else: self.dlog("SEND button not found")
        except Exception as e:
            self.dlog(f"click SEND failed: {e!r}")
        self.dlog("send NOT confirmed"); return False

    async def _send_unavail_marker(self, expected_header_title: str) -> bool:
        return await self._send_message_safe("**", expected_header_title=expected_header_title)

    # ---------- mark unread ----------
    async def _sidebar_item_for_title(self, title: str) -> Locator:
        page = self._page; assert page
        if title:
            loc = page.locator("xpath=//div[@role='listitem'][.//span[normalize-space()!='']]", has_text=title)
            if await loc.count(): return loc.first
        return page.locator("xpath=//div[@role='listitem']").first

    async def _row_has_unread(self, item: Locator) -> bool:
        try:
            if await item.locator("xpath=.//span[contains(@aria-label,'unread') or contains(@aria-label,'خوانده نشده')]").count():
                return True
            if await item.locator("xpath=.//span[@data-icon='notification' or contains(@class,'_unread_') or contains(@aria-label,'پیام خوانده نشده')]").count():
                return True
        except Exception: pass
        return False

    async def _mark_current_chat_unread(self, header_title: str) -> bool:
        page = self._page; assert page
        await self._dismiss_top_banner_if_present()

        # 1) Hotkey روی چتِ فعلی
        try:
            await page.keyboard.down("Control"); await page.keyboard.down("Shift"); await page.keyboard.press("KeyU")
        finally:
            try: await page.keyboard.up("Shift"); await page.keyboard.up("Control")
            except Exception: pass
        await asyncio.sleep(0.25)
        try:
            row = await self._sidebar_item_for_title(header_title)
            if await self._row_has_unread(row):
                self.dlog("unread badge confirmed (hotkey-first)")
                return True
        except Exception as e:
            self.dlog(f"unread check after hotkey failed: {e!r}")

        # 2) فقط دکمه‌ی منو در ردیف (نه کلیک روی خود ردیف)
        try:
            item = await self._sidebar_item_for_title(header_title)
            await item.scroll_into_view_if_needed()
            menu_btn = item.locator(
                "xpath=.//*[@aria-label='Open chat context menu' or @aria-label='Open the chat context menu' or @data-testid='menu']"
            )
            if await menu_btn.count():
                await menu_btn.first.click()
                await asyncio.sleep(0.12)
                mi = page.locator("text=/^Mark as unread$/i")
                mi_fa = page.get_by_text(re.compile(r"خوانده.?نشده|علامت.?گذاری.*خوانده.?نشده", re.I))
                if await mi.count():
                    await mi.first.click()
                    self.dlog("Mark as unread clicked (menu button EN)")
                elif await mi_fa.count():
                    await mi_fa.first.click()
                    self.dlog("Mark as unread clicked (menu button FA)")
                await asyncio.sleep(0.25)
                if await self._row_has_unread(item):
                    self.dlog("unread badge confirmed (menu button)")
                    return True
        except Exception as e:
            self.dlog(f"mark unread via menu button failed: {e!r}")

        # 3) راست‌کلیک
        try:
            item = await self._sidebar_item_for_title(header_title)
            title_span = item.locator("xpath=.//span[@dir='auto' or @title][normalize-space()!='']")
            target = title_span.first if await title_span.count() else item
            try:
                await target.click(button="right")
            except Exception:
                await target.click()
                await asyncio.sleep(0.05)
                await page.keyboard.press("Shift+F10")
            await asyncio.sleep(0.12)
            mi = page.locator("text=/^Mark as unread$/i")
            mi_fa = page.get_by_text(re.compile(r"خوانده.?نشده|علامت.?گذاری.*خوانده.?نشده", re.I))
            if await mi.count():
                await mi.first.click(); self.dlog("Mark as unread clicked (context EN)")
            elif await mi_fa.count():
                await mi_fa.first.click(); self.dlog("Mark as unread clicked (context FA)")
            await asyncio.sleep(0.25)
            if await self._row_has_unread(item):
                self.dlog("unread badge confirmed (context menu)")
                return True
            else:
                self.dlog("unread not visible after menu click")
        except Exception as e:
            self.dlog(f"mark unread via context menu failed: {e!r}")

        self.dlog("unread could not be confirmed")
        return False

    # ---------- leave (strict, no reload) ----------
    async def _focus_search_box(self) -> bool:
        page = self._page; assert page
        try:
            for sel in SEARCH_INPUT_CANDIDATES:
                box = page.locator(sel)
                if await box.count():
                    await box.first.click()
                    await asyncio.sleep(0.15)
                    ok = await page.evaluate("""
                        (sel) => {
                            const ae = document.activeElement;
                            if (!ae) return false;
                            return ae.matches(sel) || (ae.closest && ae.closest(sel));
                        }
                    """, sel)
                    if ok:
                        self.dlog("left -> focused search box (confirmed)")
                        return True
        except Exception as e:
            self.dlog(f"leave via search focus failed: {e!r}")
        return False

    async def _open_new_chat_drawer(self) -> bool:
        page = self._page; assert page
        try:
            btn = page.locator("[data-testid='chat-new-button']")
            if await btn.count():
                await btn.first.click()
                await asyncio.sleep(0.2)
                self.dlog("left -> opened new-chat drawer")
                return True
        except Exception as e:
            self.dlog(f"open new-chat drawer failed: {e!r}")
        return False

    async def _post_unread_hard_leave(self) -> None:
        """
        خروجِ تضمینی بعد از Mark-as-Unread — بدون ریلود.
        """
        page = self._page; assert page
        try:
            for _ in range(2):
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.08)
        except Exception: pass
        await self._focus_search_box()
        opened = await self._open_new_chat_drawer()
        if opened:
            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
        self.dlog("left -> post-unread (no reload)")

    async def _leave_to_sidebar(self, force_hard: bool = False) -> None:
        """
        خروج به سایدبار — بدون ریلود حتی در حالت «hard».
        """
        page = self._page; assert page
        try:
            if not await self._is_in_chat():
                self.dlog("left -> already out of a chat context")
                return
        except Exception: pass
        try:
            for _ in range(3):
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.12)
            self.dlog("left -> pressed Escape")
        except Exception: pass
        _ = await self._focus_search_box()
        if force_hard:
            opened = await self._open_new_chat_drawer()
            if opened:
                try:
                    await page.keyboard.press("Escape")
                except Exception:
                    pass
            self.dlog("left -> hard exit (no reload)")
