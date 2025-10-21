"""Shared cache access helpers for the private Telegram bot."""

from __future__ import annotations

from typing import List, Dict, Any


def _ensure_private_package() -> None:
    """Ensure the project root is available on ``sys.path`` when frozen."""
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1].parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


try:
    from privateTelegram.utils import state
except ModuleNotFoundError:  # pragma: no cover - support standalone execution
    _ensure_private_package()
    from privateTelegram.utils import state  # type: ignore


def get_cached_data() -> List[Dict[str, Any]]:
    """Return the current processed cache snapshot."""
    return state.cached_simplified_data


__all__ = ["get_cached_data"]
