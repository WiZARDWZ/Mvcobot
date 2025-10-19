"""Runtime service that hosts the private DM Telegram bot."""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
from typing import Dict, Iterable, List, Optional

from telegram.ext import Application, ApplicationBuilder

from .storage.db_storage import DBStorage

LOGGER = logging.getLogger(__name__)

CONFIG_KEYS: Iterable[str] = (
    "DM_ENABLED",
    "DM_BOT_TOKEN",
    "DM_CHANNEL_ID",
    "WORK_HOURS_START",
    "WORK_HOURS_END",
    "DM_RATE_LIMIT",
    "DM_WHITELIST",
    "DM_REPLY_START",
    "DM_REPLY_OFF_HOURS",
    "DM_REPLY_GENERIC",
    # historical aliases preserved for migration compatibility
    "DM_START_REPLY",
    "DM_OFF_HOURS_REPLY",
    "DM_GENERIC_REPLY",
    "DM_START_MESSAGE",
    "DM_OFF_HOURS_MESSAGE",
    "DM_DEFAULT_REPLY",
    "DM_MESSAGE_DEFAULT",
    "START_REPLY",
    "START_MESSAGE",
    "OFF_HOURS_REPLY",
    "OFF_HOURS_MESSAGE",
    "GENERIC_REPLY",
    "DEFAULT_REPLY",
    "start_reply",
    "start_message",
    "off_hours_reply",
    "off_hours_message",
    "generic_reply",
    "default_reply",
)


@dataclass
class DMConfiguration:
    enabled: bool
    token: str
    channel_id: Optional[str]
    work_hours_start: Optional[dt_time]
    work_hours_end: Optional[dt_time]
    whitelist: List[int]
    rate_limit: Optional[str]
    start_reply: str
    off_hours_reply: str
    generic_reply: str

    @classmethod
    def from_settings(cls, settings: Dict[str, Optional[str]]) -> "DMConfiguration":
        def _parse_time(value: Optional[str]) -> Optional[dt_time]:
            if not value:
                return None
            try:
                hour, minute = value.split(":", 1)
                return dt_time(int(hour), int(minute))
            except Exception:
                LOGGER.warning("Invalid work hours value: %s", value)
                return None

        def _parse_whitelist(value: Optional[str]) -> List[int]:
            if not value:
                return []
            result: List[int] = []
            for chunk in value.split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                try:
                    result.append(int(chunk))
                except ValueError:
                    LOGGER.warning("Ignore invalid whitelist entry: %s", chunk)
            return result

        def _resolve_text(keys: Iterable[str], default: str) -> str:
            for key in keys:
                value = settings.get(key)
                if value:
                    return str(value)
            return default

        enabled = str(settings.get("DM_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}
        token = (settings.get("DM_BOT_TOKEN") or "").strip()
        channel_id = (settings.get("DM_CHANNEL_ID") or "").strip() or None
        rate_limit = (settings.get("DM_RATE_LIMIT") or "").strip() or None
        start_reply = _resolve_text(
            (
                "DM_REPLY_START",
                "DM_START_REPLY",
                "DM_START_MESSAGE",
                "START_REPLY",
                "START_MESSAGE",
                "start_reply",
                "start_message",
            ),
            "سلام! پیام شما دریافت شد و به زودی پاسخ داده می‌شود.",
        )
        off_hours_reply = _resolve_text(
            (
                "DM_REPLY_OFF_HOURS",
                "DM_OFF_HOURS_REPLY",
                "DM_OFF_HOURS_MESSAGE",
                "OFF_HOURS_REPLY",
                "OFF_HOURS_MESSAGE",
                "off_hours_reply",
                "off_hours_message",
            ),
            "⏰ خارج از ساعات کاری هستیم؛ به محض حضور همکاران پاسخ خواهیم داد.",
        )
        generic_reply = _resolve_text(
            (
                "DM_REPLY_GENERIC",
                "DM_GENERIC_REPLY",
                "DM_DEFAULT_REPLY",
                "DM_MESSAGE_DEFAULT",
                "GENERIC_REPLY",
                "DEFAULT_REPLY",
                "generic_reply",
                "default_reply",
            ),
            "پیام شما ثبت شد.",
        )
        return cls(
            enabled=enabled,
            token=token,
            channel_id=channel_id,
            work_hours_start=_parse_time(settings.get("WORK_HOURS_START")),
            work_hours_end=_parse_time(settings.get("WORK_HOURS_END")),
            whitelist=_parse_whitelist(settings.get("DM_WHITELIST")),
            rate_limit=rate_limit,
            start_reply=start_reply,
            off_hours_reply=off_hours_reply,
            generic_reply=generic_reply,
        )

    def within_work_hours(self, now: Optional[datetime] = None) -> bool:
        if now is None:
            now = datetime.utcnow()
        if self.work_hours_start and self.work_hours_end:
            start = datetime.combine(now.date(), self.work_hours_start)
            end = datetime.combine(now.date(), self.work_hours_end)
            if end <= start:
                end += timedelta(days=1)
            return start <= now <= end
        return True


class DMBotService:
    """Host lifecycle for the DM bot application."""

    _INSTANCE: Optional["DMBotService"] = None

    def __init__(self) -> None:
        self.storage = DBStorage()
        self._config = DMConfiguration.from_settings(
            self.storage.get_settings(list(dict.fromkeys(CONFIG_KEYS)))
        )
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._reload = threading.Event()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._application: Optional[Application] = None
        self._status: str = "stopped"

    # region lifecycle helpers
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_thread, name="dm-bot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._reload.set()
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._shutdown_app(), self._loop)
        if self._thread:
            self._thread.join(timeout=10)
        self._thread = None
        self._status = "stopped"

    def reload(self) -> None:
        self._reload.set()

    def status(self) -> str:
        return self._status

    # endregion

    # region configuration
    def refresh_configuration(self) -> DMConfiguration:
        self._config = DMConfiguration.from_settings(
            self.storage.get_settings(list(dict.fromkeys(CONFIG_KEYS)))
        )
        return self._config

    @property
    def configuration(self) -> DMConfiguration:
        return self._config

    # endregion

    def send_test_message(self, text: str = 'پیام تست DM Bot') -> bool:
        config = self.refresh_configuration()
        if not self._application or not config.channel_id:
            return False
        if not self._loop or not self._loop.is_running():
            return False
        try:
            fut = asyncio.run_coroutine_threadsafe(
                self._application.bot.send_message(chat_id=config.channel_id, text=text),
                self._loop,
            )
            fut.result(timeout=10)
            return True
        except Exception as exc:  # pragma: no cover - network
            LOGGER.warning('Failed to send DM test message: %s', exc)
            return False

    # region thread
    def _run_thread(self) -> None:
        asyncio.run(self._async_main())

    async def _async_main(self) -> None:
        self._loop = asyncio.get_running_loop()
        backoff = 5
        while not self._stop.is_set():
            config = self.refresh_configuration()
            if not config.enabled or not config.token:
                self._status = "disabled"
                await self._wait_for_reload()
                continue
            try:
                await self._run_application(config)
            except Exception as exc:  # pragma: no cover - defensive
                LOGGER.exception("DM bot crashed: %s", exc)
                self._status = f"error: {exc}"[:120]
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)
            else:
                backoff = 5

    async def _wait_for_reload(self) -> None:
        while not self._stop.is_set():
            if self._reload.wait(1.0):
                self._reload.clear()
                return
            await asyncio.sleep(0)

    async def _run_application(self, config: DMConfiguration) -> None:
        builder = ApplicationBuilder().token(config.token)
        application = builder.build()
        self._application = application
        from .handlers import register_handlers  # import lazily

        register_handlers(application, self.storage, lambda: self._config)
        self._status = "running"
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        try:
            await self._wait_for_reload()
        finally:
            await application.updater.stop()
            await self._shutdown_app()
            self._application = None

    async def _shutdown_app(self) -> None:
        if not self._application:
            return
        await self._application.stop()
        await self._application.shutdown()

    # endregion


def get_dm_service() -> DMBotService:
    if DMBotService._INSTANCE is None:
        DMBotService._INSTANCE = DMBotService()
    return DMBotService._INSTANCE
