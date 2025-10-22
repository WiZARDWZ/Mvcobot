"""Utilities for normalising and standardising part codes across platforms."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

__all__ = [
    "StandardizedCode",
    "normalize_code",
    "standardize_code",
    "format_display_code",
]

# Persian digits to Latin digits translation map
_PERSIAN_TO_LATIN = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# Characters that should be stripped entirely (bidirectional marks, zero-width, etc.)
_STRIP_PATTERN = re.compile(r"[\u200c\u200d\u200e\u200f\u202a-\u202e\u2066-\u2069\u206f\ufeff]")

# Dash-like characters that should be replaced with a standard hyphen
_DASH_PATTERN = re.compile(r"[‐‑‒–—―⁃−﹘﹣]")

# Separators that should be normalised to a hyphen before collapsing
_SEPARATOR_PATTERN = re.compile(r"[-_/\\.,\s]+")

# Remove everything except alphanumeric characters and hyphen
_ALLOWED_PATTERN = re.compile(r"[^A-Z0-9-]")


@dataclass(frozen=True)
class StandardizedCode:
    """Container for a cleaned code in different representations."""

    normalized: str  # cleaned alphanumeric string with original length (no separators)
    padded: str      # normalized string coerced to exactly 10 characters (X padded/truncated)
    display: str     # human readable display (5 chars, hyphen, 5 chars)

    def __bool__(self) -> bool:  # pragma: no cover - convenience for truthy checks
        return bool(self.padded)


def _clean_base(raw: str) -> str:
    """Apply common text normalisations prior to alphanumeric filtering."""
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    text = text.translate(_PERSIAN_TO_LATIN)
    text = _STRIP_PATTERN.sub("", text)
    text = _DASH_PATTERN.sub("-", text)
    text = text.replace("\u00a0", " ")
    text = _SEPARATOR_PATTERN.sub("-", text)
    text = text.strip("-")
    text = text.upper()
    text = _ALLOWED_PATTERN.sub("", text)
    return text


def normalize_code(raw: str) -> str:
    """Return the uppercase alphanumeric representation used for lookups."""
    text = _clean_base(raw)
    return text.replace("-", "")


def format_display_code(code: str) -> str:
    """Format a 10-character code as ``12345-67890`` for display."""
    core = (code or "").strip().upper()
    if len(core) < 10:
        core = core + "X" * (10 - len(core))
    else:
        core = core[:10]
    return f"{core[:5]}-{core[5:10]}"


def standardize_code(raw: str) -> Optional[StandardizedCode]:
    """Return a :class:`StandardizedCode` or ``None`` when the input is unusable."""
    normalized = normalize_code(raw)
    if len(normalized) < 7:
        return None
    if len(normalized) >= 10:
        padded = normalized[:10]
    else:
        padded = normalized + ("X" * (10 - len(normalized)))
    display = f"{padded[:5]}-{padded[5:10]}"
    return StandardizedCode(normalized=normalized, padded=padded, display=display)
