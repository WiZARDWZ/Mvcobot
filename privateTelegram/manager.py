"""Runtime controller for the private Telegram bot (Telethon-based)."""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from privateTelegram.cache.updater import update_cache_periodically
from privateTelegram.config.settings import save_settings, settings
from privateTelegram.telegram.client import client

# Ensure handlers are registered when the controller is imported
from privateTelegram.telegram.handlers import admin as _admin_handlers  # noqa: F401
from privateTelegram.telegram.handlers import messages as _message_handlers  # noqa: F401
from privateTelegram.utils import state as private_state

LOGGER = logging.getLogger("private-telegram")


class PrivateTelegramController:
    """Manage lifecycle of the Telethon client inside the shared asyncio loop."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._task: Optional[asyncio.Future] = None
        self._cache_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._pending_state: Optional[bool] = bool(settings.get("enabled", True))
        self._desired_state: bool = bool(settings.get("enabled", True))

    # ------------------------------------------------------------------
    # Loop wiring
    # ------------------------------------------------------------------
    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        if self._pending_state is not None:
            state = self._pending_state
            self._pending_state = None
            self.set_enabled(state)

    def set_enabled(self, enabled: bool) -> None:
        self._desired_state = bool(enabled)
        if self._loop is None or self._loop.is_closed():
            self._pending_state = self._desired_state
            self._apply_enabled_flag(enabled)
            return

        self._pending_state = None
        try:
            asyncio.run_coroutine_threadsafe(
                self._ensure_state(enabled), self._loop
            )
        except RuntimeError:
            LOGGER.debug("Event loop not ready; deferring private Telegram state change.")
            self._pending_state = bool(enabled)
            self._apply_enabled_flag(enabled)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def set_dm_enabled(self, enabled: bool) -> None:
        settings["dm_enabled"] = bool(enabled)
        self._persist_settings()

    def update_setting(self, key: str, value) -> None:
        settings[key] = value
        self._persist_settings()

    def update_settings(self, **kwargs) -> None:
        settings.update(kwargs)
        self._persist_settings()

    # ------------------------------------------------------------------
    async def _ensure_state(self, enabled: bool) -> None:
        async with self._lock:
            if enabled:
                await self._start()
            else:
                await self._stop()

    async def _start(self) -> None:
        if self._task and not self._task.done():
            self._apply_enabled_flag(True)
            return

        loop = self._loop
        if loop is None:
            LOGGER.warning("Event loop not attached; cannot start private Telegram client.")
            return

        self._apply_enabled_flag(True)
        if self._cache_task is None or self._cache_task.done():
            self._cache_task = loop.create_task(self._run_cache_loop(), name="private-tg-cache")

        try:
            await client.connect()
            if not await client.is_user_authorized():
                LOGGER.warning("Private Telegram client is not authorised. Please complete login manually.")
            await client.start(phone=settings.get("phone_number"))
        except Exception as exc:
            LOGGER.exception("Failed to start private Telegram client: %s", exc)
            self._apply_enabled_flag(False)
            if self._cache_task:
                self._cache_task.cancel()
                self._cache_task = None
            return

        self._task = loop.create_task(client.run_until_disconnected(), name="private-tg-main")

    async def _stop(self) -> None:
        self._apply_enabled_flag(False)

        if self._cache_task:
            self._cache_task.cancel()
            try:
                await self._cache_task
            except asyncio.CancelledError:
                pass
            except Exception:
                LOGGER.debug("Cache loop ended with error", exc_info=True)
            self._cache_task = None

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception:
                LOGGER.debug("Private Telegram task ended with error", exc_info=True)
            self._task = None

        try:
            if client.is_connected():
                await client.disconnect()
        except Exception:
            LOGGER.debug("Error while disconnecting Telethon client", exc_info=True)

    async def _run_cache_loop(self) -> None:
        try:
            await update_cache_periodically()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOGGER.exception("Private Telegram cache loop crashed: %s", exc)

    def _apply_enabled_flag(self, enabled: bool) -> None:
        settings["enabled"] = bool(enabled)
        self._persist_settings()

    @staticmethod
    def _persist_settings() -> None:
        try:
            save_settings()
        except Exception:
            LOGGER.debug("Failed to persist private Telegram settings", exc_info=True)


def get_runtime_snapshot() -> dict:
    last_update = private_state.last_cache_update
    return {
        "enabled": bool(settings.get("enabled", True)),
        "dmEnabled": bool(settings.get("dm_enabled", True)),
        "dataSource": settings.get("data_source", "sql"),
        "cache": {
            "lastUpdatedISO": last_update.isoformat() if last_update else None,
            "records": len(private_state.cached_simplified_data),
        },
        "totalQueries": int(private_state.total_queries),
    }


private_controller = PrivateTelegramController()

__all__ = ["private_controller", "get_runtime_snapshot"]
