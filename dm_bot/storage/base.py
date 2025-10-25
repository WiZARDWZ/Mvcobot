"""Storage protocol for DM bot persistence."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class Storage(Protocol):
    """Abstract storage backend used by the DM bot."""

    # settings
    def get_setting(self, key: str) -> Optional[str]:
        """Return a single setting value or ``None`` when absent."""

    def set_setting(self, key: str, value: str) -> None:
        """Persist a setting value (idempotent upsert)."""

    def get_settings(self, keys: List[str]) -> Dict[str, Optional[str]]:
        """Fetch multiple settings in one round-trip."""

    # users/messages
    def upsert_user(self, user_id: int, **attrs: Any) -> None:
        """Create or update a DM user row."""

    def log_message(self, user_id: int, text: str, outgoing: bool) -> None:
        """Persist message payload for observability."""

    # conversation state
    def get_conversation(self, user_id: int) -> Dict[str, Any]:
        """Return conversation state for a user (empty dict when none)."""

    def set_conversation(self, user_id: int, state: Dict[str, Any]) -> None:
        """Persist conversation state for a user."""
