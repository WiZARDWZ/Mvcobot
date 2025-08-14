# -*- coding: utf-8 -*-
"""
Probe WhatsApp Web UI — extract reliable selectors/ids/labels from the *current* UI.
Outputs:
  - wa_ui_probe.json (structured selectors, counts, samples)
  - wa_ui_probe.txt  (human-readable log)
  - wa_ui_probe.png  (screenshot with highlighted candidates)

Usage (Windows/PyCharm example):
  python -m wa.probe_whatsapp_ui --user-data-dir ./.wa-user-data --headless false --slowmo 100

Tip:
  - اول یک چت *واقعی* رو دستی انتخاب کن تا پنل گفتگو باز باشه، بعد اسکریپت رو اجرا کن.
  - اگر لاگین نیست، اسکریپت منتظر QR و سپس آماده‌شدن UI می‌مونه.
"""

import asyncio
import argparse
import json
import os
import time
from typing import Dict, List, Tuple, Any

from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

OUT_JSON = "wa_ui_probe.json"
OUT_TXT  = "wa_ui_probe.txt"
OUT_PNG  = "wa_ui_probe.png"

# ---- Helpers ----------------------------------------------------------------
def now() -> str:
    return time.strftime("%H:%M:%S")

async def wait_any_selector(page: Page, selectors: List[str], timeout_ms: int = 60_000) -> str:
    last_err = None
    for sel in selectors:
        try:
            await page.wait_for_selector(sel, timeout=timeout_ms, state="visible")
            return sel
        except Exception as e:
            last_err = e
    raise PWTimeout(f"wait_any_selector timeout; tried: {selectors}") from last_err

async def count_sample(page: Page, selector: str, is_xpath: bool = False) -> Tuple[int, Dict[str, Any]]:
    loc = page.locator(f"xpath={selector}" if is_xpath else selector)
    try:
        cnt = await loc.count()
    except Exception:
        return 0, {}
    sample = {}
    if cnt > 0:
        h = loc.first
        try:
            txt = (await h.inner_text()) or ""
            sample["text"] = txt.strip()
        except Exception:
            pass
        for attr in ("data-testid", "aria-label", "role", "title", "placeholder", "aria-placeholder"):
            try:
                val = await h.get_attribute(attr)
                if val:
                    sample[attr] = val
            except Exception:
                pass
    return cnt, sample

async def probe_candidates(page: Page, name: str, css_list: List[str], xpath_list: List[str]) -> Dict[str, Any]:
    results = {"name": name, "matches": []}
    for sel in css_list:
        cnt, sample = await count_sample(page, sel, is_xpath=False)
        results["matches"].append({"type": "css", "selector": sel, "count": cnt, "sample": sample})
    for sel in xpath_list:
        cnt, sample = await count_sample(page, sel, is_xpath=True)
        results["matches"].append({"type": "xpath", "selector": sel, "count": cnt, "sample": sample})
    return results

async def dump_datatestid_keywords(page: Page, keywords: List[str], limit: int = 5000) -> Dict[str, Any]:
    out = {"keywords": keywords, "data_testid": {}}
    try:
        nodes = page.locator("xpath=//*[@data-testid]")
        n = min(await nodes.count(), limit)
        for i in range(n):
            h = nodes.nth(i)
            try:
                v = await h.get_attribute("data-testid")
            except Exception:
                v = None
            if not v:
                continue
            for kw in keywords:
                if kw.lower() in v.lower():
                    arr = out["data_testid"].setdefault(kw, [])
                    if v not in arr:
                        arr.append(v)
    except Exception:
        pass
    return out

async def dump_aria_keywords(page: Page, keywords: List[str], limit: int = 5000) -> Dict[str, Any]:
    out = {"keywords": keywords, "aria_label_samples": {}}
    try:
        nodes = page.locator("xpath=//*[@aria-label]")
        n = min(await nodes.count(), limit)
        for i in range(n):
            h = nodes.nth(i)
            try:
                v = await h.get_attribute("aria-label")
            except Exception:
                v = None
            if not v:
                continue
            for kw in keywords:
                if kw.lower() in v.lower():
                    arr = out["aria_label_samples"].setdefault(kw, [])
                    s = v.strip()
                    if s not in arr:
                        arr.append(s)
    except Exception:
        pass
    return out

async def outline(page: Page, selector: str, color: str) -> None:
    """Add red/green/blue outline to visualize matched nodes."""
    js = """
    (sel, color) => {
      try {
        const els = document.querySelectorAll(sel);
        for (const el of els) {
          el.style.outline = `2px solid ${color}`;
          el.style.outlineOffset = '0px';
        }
      } catch (e) {}
    }
    """
    try:
        await page.evaluate(js, selector, color)
    except Exception:
        pass

# ---- Main probe --------------------------------------------------------------
async def probe_whatsapp_ui(user_data_dir: str, headless: bool, slowmo: int) -> None:
    READY_CANDIDATES = [
        "[data-testid='chat-list']",
        "[data-testid='pane-side']",
        "[aria-label*='Chat list' i]",
        "[data-testid='conversation-panel-messages']",
        "div[role='grid']",
    ]
    QR_CANDIDATES = [
        "[data-testid='qrcode']",
        "[data-testid='wa-qr-code']",
        "canvas[aria-label*='Scan']",
    ]

    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            slow_mo=slowmo,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            print(f"[{now()}] PROBE | goto web.whatsapp.com", flush=True)
            await page.goto("https://web.whatsapp.com/", wait_until="domcontentloaded")
            try:
                await page.wait_for_load_state("networkidle", timeout=60_000)
            except PWTimeout:
                pass

            # Ready / QR
            try:
                sel = await wait_any_selector(page, READY_CANDIDATES, 60_000)
                print(f"[{now()}] PROBE | UI ready via {sel}", flush=True)
            except PWTimeout:
                print(f"[{now()}] PROBE | waiting for QR/login…", flush=True)
                try:
                    await wait_any_selector(page, QR_CANDIDATES, 120_000)
                except PWTimeout:
                    pass
                sel = await wait_any_selector(page, READY_CANDIDATES, 180_000)
                print(f"[{now()}] PROBE | UI ready after QR via {sel}", flush=True)

            results: Dict[str, Any] = {"ts": int(time.time()), "sections": []}

            # 1) Chat list & items
            results["sections"].append(await probe_candidates(
                page, "chat_list",
                css_list=[
                    "[data-testid='pane-side']",
                    "[data-testid='chat-list']",
                    "[role='grid']",
                    "[aria-label*='Chat list' i]",
                    "[aria-label*='Chats' i]",
                ],
                xpath_list=[
                    "//div[@data-testid='pane-side']",
                    "//div[@data-testid='chat-list']",
                    "//div[@role='grid']",
                ],
            ))

            results["sections"].append(await probe_candidates(
                page, "chat_list_item",
                css_list=[
                    "div[role='listitem']",
                    "[data-testid='cell-frame-container']",
                ],
                xpath_list=[
                    "//div[@role='listitem']",
                    "//div[@data-testid='cell-frame-container']",
                ],
            ))

            # 2) Unread badges/labels
            results["sections"].append(await probe_candidates(
                page, "unread_badge",
                css_list=[
                    "[data-testid*='unread']",
                    "span[aria-label*='unread' i]",
                    "span[aria-label*='خوانده' i]",
                    "span[aria-label*='خوانده نشده' i]",
                    "[data-icon*='unread' i]",
                ],
                xpath_list=[
                    "//span[contains(@aria-label,'unread')]",
                    "//span[contains(@aria-label,'خوانده')]",
                    "//div//*[@data-testid='unread-count' or @data-testid='icon-unread-count']",
                ],
            ))

            # 3) Conversation panel / messages
            results["sections"].append(await probe_candidates(
                page, "conversation_panel",
                css_list=[
                    "[data-testid='conversation-panel-messages']",
                    "[data-testid='conversation-panel-wrapper']",
                    "main[role='main']",
                ],
                xpath_list=[
                    "//*[@data-testid='conversation-panel-messages']",
                    "//*[@data-testid='conversation-panel-wrapper']",
                ],
            ))

            results["sections"].append(await probe_candidates(
                page, "message_nodes",
                css_list=[
                    "div.message-in",
                    "div.message-out",
                    "[data-testid='msg-container']",
                    "[data-testid='msg-container-in']",
                    "[data-testid='msg-container-out']",
                ],
                xpath_list=[
                    "//div[contains(@class,'message-in') or contains(@class,'message-out')]",
                    "//*[@data-testid='msg-container' or @data-testid='msg-container-in' or @data-testid='msg-container-out']",
                ],
            ))

            # 4) Header title
            results["sections"].append(await probe_candidates(
                page, "header_title",
                css_list=[
                    "[data-testid='conversation-info-header-chat-title']",
                    "header :is(h1,span[title])",
                    "header :is(h1,span)[dir='auto']",
                ],
                xpath_list=[
                    "//*[@data-testid='conversation-info-header-chat-title']",
                    "//header//*[self::h1 or self::span][normalize-space()!='']",
                ],
            ))

            # 5) Composer (textbox) & send button
            results["sections"].append(await probe_candidates(
                page, "composer_textbox",
                css_list=[
                    "[data-testid='conversation-compose-box-input'] div[contenteditable='true'][role='textbox']",
                    "footer [data-testid='conversation-compose-box-input'] div[contenteditable='true'][role='textbox']",
                    "footer div[contenteditable='true'][role='textbox'][aria-label*='message' i]",
                    "footer div[contenteditable='true'][role='textbox'][aria-placeholder*='message' i]",
                    "footer [contenteditable='true'][role='textbox'][data-lexical-editor='true']",
                ],
                xpath_list=[
                    "//*[@data-testid='conversation-compose-box-input']//div[@contenteditable='true' and @role='textbox']",
                    "//footer//div[@contenteditable='true' and @role='textbox']",
                ],
            ))

            results["sections"].append(await probe_candidates(
                page, "send_button",
                css_list=[
                    "[data-testid='compose-btn-send']",
                    "button[aria-label*='send' i]",
                    "footer [aria-label*='send' i]",
                ],
                xpath_list=[
                    "//*[@data-testid='compose-btn-send']",
                    "//button[contains(translate(@aria-label,'SEND','send'),'send')]",
                ],
            ))

            # 6) Chat list search box
            results["sections"].append(await probe_candidates(
                page, "chatlist_search",
                css_list=[
                    "[data-testid='chat-list-search']",
                    "[data-testid='chatlist-search']",
                    "input[aria-label*='Search' i]",
                ],
                xpath_list=[
                    "//*[@data-testid='chat-list-search' or @data-testid='chatlist-search']",
                ],
            ))

            # 7) Context menu items (try right-click on first list item)
            try:
                first_item = page.locator("div[role='listitem']").first
                await first_item.click(button="right", timeout=3000)
                await page.wait_for_selector("[role='menu']", timeout=2000)
            except Exception:
                pass
            results["sections"].append(await probe_candidates(
                page, "context_menu_items",
                css_list=[
                    "[role='menu'] [role='menuitem']",
                    "[data-testid*='menu'] [role='menuitem']",
                ],
                xpath_list=[
                    "//*[@role='menu']//*[@role='menuitem']",
                ],
            ))

            # 8) Data-testid & aria-label vocab (keywords)
            keywords = [
                "unread", "compose", "send", "search", "pane", "chat",
                "conversation", "header", "menu", "msg", "message",
            ]
            fa_keywords = ["خوانده", "ارسال", "جستجو", "گفتگو", "پیام", "منو"]
            results["data_testid_index"] = await dump_datatestid_keywords(page, keywords + fa_keywords)
            results["aria_index"] = await dump_aria_keywords(page, keywords + fa_keywords)

            # ---- Visualize highlights and screenshot
            highlight_sets = [
                ("[data-testid='pane-side']",             "red"),
                ("div[role='listitem']",                  "red"),
                ("[data-testid*='unread']",               "magenta"),
                ("span[aria-label*='unread' i]",          "magenta"),
                ("[data-testid='conversation-panel-messages']", "blue"),
                ("div.message-in",                        "green"),
                ("div.message-out",                       "orange"),
                ("[data-testid='msg-container-in']",      "green"),
                ("[data-testid='msg-container-out']",     "orange"),
                ("[data-testid='conversation-info-header-chat-title']", "cyan"),
                ("[data-testid='conversation-compose-box-input'] div[contenteditable='true'][role='textbox']", "yellow"),
                ("[data-testid='compose-btn-send']",      "yellow"),
            ]
            for sel, color in highlight_sets:
                await outline(page, sel, color)

            await page.screenshot(path=OUT_PNG, full_page=True)

            # ---- Save outputs
            with open(OUT_JSON, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            # Human-readable txt
            def add_line(lines, s): lines.append(s)

            lines: List[str] = []
            add_line(lines, f"[{now()}] PROBE SUMMARY")
            for sec in results["sections"]:
                add_line(lines, f"\n== {sec['name']} ==")
                for m in sec["matches"]:
                    smp = m.get("sample") or {}
                    smp_txt = smp.get("text") or ""
                    smp_lbl = smp.get("aria-label") or smp.get("title") or ""
                    add_line(lines, f"- ({m['type']}) {m['selector']}  -> count={m['count']}  "
                                    f"{'text='+smp_txt[:60] if smp_txt else ''}  "
                                    f"{'label='+smp_lbl[:60] if smp_lbl else ''}")
            add_line(lines, "\n== data-testid keywords ==")
            for kw, vals in (results.get("data_testid_index", {}).get("data_testid", {})).items():
                add_line(lines, f"- {kw}: {', '.join(vals[:20])}")
            add_line(lines, "\n== aria-label samples ==")
            for kw, vals in (results.get("aria_index", {}).get("aria_label_samples", {})).items():
                add_line(lines, f"- {kw}: {', '.join(vals[:10])}")

            with open(OUT_TXT, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            print(f"[{now()}] PROBE | saved {OUT_JSON}, {OUT_TXT}, {OUT_PNG}", flush=True)

        finally:
            await ctx.close()

# ---- CLI --------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Probe WhatsApp Web UI to extract selectors.")
    ap.add_argument("--user-data-dir", default="./.wa-user-data", help="Chromium user data dir (persisted login).")
    ap.add_argument("--headless", default="false", help="true/false")
    ap.add_argument("--slowmo", default="80", help="Playwright slowMo in ms (e.g., 80/120).")
    args = ap.parse_args()
    headless = str(args.headless).lower() == "true"
    slowmo = int(args.slowmo)
    asyncio.run(probe_whatsapp_ui(args.user_data_dir, headless, slowmo))

if __name__ == "__main__":
    main()
