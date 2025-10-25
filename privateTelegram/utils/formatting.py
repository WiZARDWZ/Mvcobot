"""Formatting helpers shared across the private Telegram bot."""

from __future__ import annotations

try:  # pragma: no cover - allow execution when package path is missing
    from utils.code_standardization import (
        normalize_code as _normalize_common,
        standardize_code as _standardize_common,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback for frozen builds
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from utils.code_standardization import (  # type: ignore
        normalize_code as _normalize_common,
        standardize_code as _standardize_common,
    )


def normalize_code(code):
    return _normalize_common(code)


def standardize_code(code):
    return _standardize_common(code)


def fix_part_number_display(part_number):
    # Wrap with Left-to-Right mark so code always displays as LTR in RTL context
    return f"\u200E{part_number}\u200E"


def format_price(price):
    try:
        return f"{float(price):,.0f}"
    except Exception:
        return str(price)


def escape_markdown(text: str, version: int = 1) -> str:
    """
    Escape Telegram Markdown special characters for MarkdownV1.
    Only escapes: backslash, asterisk, underscore, square brackets, backtick.
    """
    if version == 1:
        chars = r"\_*[]`"
    else:
        chars = r"\_*[]`"
    return "".join(f"\\{c}" if c in chars else c for c in text)
