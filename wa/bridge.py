# wa/bridge.py — پل بین واتساپ و inventory (با fallback بی‌کرش)

from __future__ import annotations
import asyncio
import importlib
import re
from typing import Any, Callable, Iterable, List, Optional

DB_DOWN_MESSAGE = (
    "دسترسی به دیتابیس قطع میباشد , در حال بررسی مشکل هستیم\n"
    "ممنون از شکیبایی شما\n"
    "mbaghshomali.ir"
)

_PERSIAN2EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

def _norm_code(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (raw or "").translate(_PERSIAN2EN)).upper()

def _dedup_keep_order(items: Iterable[str]) -> List[str]:
    seen, out = set(), []
    for s in items:
        if s not in seen:
            seen.add(s); out.append(s)
    return out

def _try_import_inventory():
    for name in ("inventory", "app.inventory", "src.inventory", "modules.inventory"):
        try:
            return importlib.import_module(name)
        except Exception:
            continue
    return None

def _pick_callable(mod, names: List[str]) -> Optional[Callable]:
    if not mod:
        return None
    for n in names:
        f = getattr(mod, n, None)
        if callable(f):
            return f
    return None

def _as_str_list(res: Any) -> Optional[List[str]]:
    if res is None:
        return []
    if isinstance(res, str):
        return [res]
    if isinstance(res, (list, tuple)) and all(isinstance(x, str) for x in res):
        return list(res)
    return None

async def _to_thread(func: Callable, *args, **kwargs):
    return await asyncio.to_thread(func, *args, **kwargs)

_ENTRYPOINTS_STR_MULTI = ["lookup_whatsapp_codes", "lookup_codes"]
_ENTRYPOINTS_STR_PER   = ["lookup_whatsapp", "lookup_wa", "lookup_text_one", "lookup_one", "lookup_code"]
_ENTRYPOINTS_RAW_PER   = ["lookup", "lookup_part", "find_by_code", "search_by_code", "get_by_code"]

async def replies_for_codes(codes: List[str]) -> List[str]:
    """
    خروجی inventory را (رشته/لیست رشته) برمی‌گرداند؛
    در هر خطایی (عدم وجود ماژول/اتصال DB/استثنا) پیام DB_DOWN_MESSAGE می‌دهد تا ربات کرش نکند.
    """
    norm_codes = _dedup_keep_order(_norm_code(c) for c in codes if c)
    if not norm_codes:
        return []

    inv = _try_import_inventory()
    if not inv:
        return [DB_DOWN_MESSAGE]

    # 1) چندکُدی → متن آماده
    try:
        multi = _pick_callable(inv, _ENTRYPOINTS_STR_MULTI)
        if multi:
            out = await _to_thread(multi, norm_codes)
            as_strs = _as_str_list(out)
            if as_strs:
                return as_strs
    except Exception:
        return [DB_DOWN_MESSAGE]

    # 2) تک‌کُدی → متن آماده
    try:
        per = _pick_callable(inv, _ENTRYPOINTS_STR_PER)
        if per:
            replies: List[str] = []
            for c in norm_codes:
                out = await _to_thread(per, c)
                as_strs = _as_str_list(out)
                if as_strs is not None:
                    replies.extend(x for x in as_strs if x and str(x).strip())
            if replies:
                return replies
    except Exception:
        return [DB_DOWN_MESSAGE]

    # 3) دادهٔ خام
    try:
        raw_per = _pick_callable(inv, _ENTRYPOINTS_RAW_PER)
        if raw_per:
            replies: List[str] = []
            for c in norm_codes:
                out = await _to_thread(raw_per, c)
                if isinstance(out, dict) and isinstance(out.get("text"), str):
                    replies.append(out["text"])
                elif isinstance(out, (list, tuple)):
                    texts = [x.get("text") for x in out if isinstance(x, dict) and isinstance(x.get("text"), str)]
                    if texts:
                        replies.extend(texts)
            return replies or [DB_DOWN_MESSAGE]
    except Exception:
        return [DB_DOWN_MESSAGE]

    return [DB_DOWN_MESSAGE]
