# utils/formatting.py
import re

def normalize_code(code):
    return re.sub(r"[-_/\.,\s]", "", str(code)).upper()

def fix_part_number_display(part_number):
    # Wrap with Left-to-Right mark so code always displays as LTR in RTL context
    return f"\u200E{part_number}\u200E"

def format_price(price):
    try:
        return f"{float(price):,.0f}"
    except:
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
    return ''.join(f'\\{c}' if c in chars else c for c in text)
