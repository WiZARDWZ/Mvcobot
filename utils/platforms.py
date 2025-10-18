"""Utilities for reading platform enablement flags shared by the bots and control panel."""
from __future__ import annotations

import json
import logging
from typing import Dict

from database.connector_bot import get_setting

LOGGER = logging.getLogger(__name__)

PLATFORM_SETTINGS_KEY = "panel_platforms_v1"


def _load_platform_flags() -> Dict[str, bool]:
    raw = get_setting(PLATFORM_SETTINGS_KEY)
    if not raw:
        return {"telegram": True, "whatsapp": True}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            telegram = bool(data.get("telegram", True))
            whatsapp = bool(data.get("whatsapp", True))
            return {"telegram": telegram, "whatsapp": whatsapp}
    except Exception:
        LOGGER.warning("Failed to decode platform settings JSON. Falling back to defaults.")
    return {"telegram": True, "whatsapp": True}


def get_platform_flags() -> Dict[str, bool]:
    """Return a copy of the persisted platform enablement flags."""
    flags = _load_platform_flags()
    return dict(flags)


def is_platform_enabled(name: str, *, include_global: bool = True) -> bool:
    """Check if a specific platform is enabled.

    Args:
        name: Platform identifier (e.g. ``"telegram"`` or ``"whatsapp"``).
        include_global: When True (default) honour the master ``enabled`` switch
            that powers the Telegram bot and also governs the overall service
            availability exposed in the control panel.
    """
    name = (name or "").strip().lower()
    flags = _load_platform_flags()
    platform_enabled = flags.get(name, True)

    if not include_global or name != "telegram":
        return platform_enabled

    global_value = (get_setting("enabled") or "true").strip().lower() == "true"
    return platform_enabled and global_value
