"""Handler registration for the DM bot."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Optional

from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from ..service import DMConfiguration
from ..storage.base import Storage
from ..utils import RateLimiter

LOGGER = logging.getLogger(__name__)

def register_handlers(
    application,
    storage: Storage,
    config_provider: Callable[[], DMConfiguration],
) -> None:
    channel_throttle = RateLimiter()

    async def _ensure_user(update: Update) -> int:
        user = update.effective_user
        if not user or getattr(user, 'is_bot', False):
            return 0
        storage.upsert_user(
            user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            language=user.language_code,
        )
        return user.id

    async def _notify_channel(
        prefix: str,
        text: str,
        *,
        user_id: Optional[int],
        rate_key: str = "messages",
    ) -> None:
        config = config_provider()
        if not config.channel_id or not application.bot:
            return
        if not channel_throttle.allow(rate_key, config.rate_limit):
            return
        details = text
        if user_id:
            details = f"[user={user_id}] {text}"
        message = f"{prefix} {details}".strip()
        try:
            await application.bot.send_message(chat_id=config.channel_id, text=message)
        except Exception as exc:  # pragma: no cover - network errors
            LOGGER.debug("Failed to push DM log to channel: %s", exc)

    async def _handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE, *, is_command: bool) -> None:
        user_id = await _ensure_user(update)
        if not user_id:
            return
        message = update.effective_message
        if message is None:
            return
        text = message.text or message.caption or ""
        if not text:
            if message.sticker:
                text = "[sticker]"
            elif message.photo:
                text = "[photo]"
            elif message.voice:
                text = "[voice]"
            elif message.video:
                text = "[video]"
            elif message.document:
                text = f"[file:{message.document.file_name or 'document'}]"
            else:
                text = "[unsupported message]"
        storage.log_message(user_id, text, outgoing=False)
        storage.set_conversation(user_id, {"last_message": text, "updated_at": datetime.utcnow().isoformat()})

        config = config_provider()
        now = datetime.utcnow()
        if user_id not in config.whitelist and not config.within_work_hours(now):
            reply = config.off_hours_reply
        elif is_command:
            reply = config.start_reply
        else:
            reply = config.generic_reply

        await message.reply_text(reply)
        storage.log_message(user_id, reply, outgoing=True)
        await _notify_channel("DM", f"IN: {text}\nOUT: {reply}", user_id=user_id)

    async def _start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _handle_reply(update, context, is_command=True)

    async def _text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await _handle_reply(update, context, is_command=False)

    async def _error_handler(update: Optional[Update], context: ContextTypes.DEFAULT_TYPE) -> None:
        error = context.error
        LOGGER.exception("DM bot handler error: %s", error)
        user_id = None
        if update and update.effective_user:
            try:
                user_id = int(update.effective_user.id)
            except Exception:  # pragma: no cover - defensive
                user_id = None
        await _notify_channel("DM-ERR", f"{error}", user_id=user_id, rate_key="errors")

    application.add_handler(CommandHandler("start", _start))
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, _text))
    application.add_error_handler(_error_handler)
