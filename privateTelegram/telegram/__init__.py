"""Telegram layer for the private Telegram bot."""

from .client import client, MAIN_GROUP_ID, NEW_GROUP_ID, ADMIN_GROUP_IDS  # noqa: F401

__all__ = ["client", "MAIN_GROUP_ID", "NEW_GROUP_ID", "ADMIN_GROUP_IDS"]
