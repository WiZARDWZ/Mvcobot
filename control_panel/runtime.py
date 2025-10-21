"""Runtime helpers bridging control panel actions with running bot services."""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional, Coroutine, Any

LOGGER = logging.getLogger(__name__)

try:
    from wa.manager import wa_controller  # type: ignore
except Exception as exc:  # pragma: no cover - optional dependency
    LOGGER.warning("WhatsApp controller unavailable: %s", exc)
    wa_controller = None

_EVENT_LOOP: Optional[asyncio.AbstractEventLoop] = None
_PENDING_WA_STATE: Optional[bool] = None
_LAST_WA_STATE: Optional[bool] = None
_LAST_PRIVATE_STATE: Optional[bool] = None


def register_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Expose the Telegram application's asyncio loop for cross-thread tasks."""
    global _EVENT_LOOP, _PENDING_WA_STATE
    _EVENT_LOOP = loop
    if _PENDING_WA_STATE is not None:
        state = _PENDING_WA_STATE
        _apply_whatsapp_state(state)


def _submit_to_loop(coro: Coroutine[Any, Any, Any]) -> None:
    loop = _EVENT_LOOP
    if loop is None or loop.is_closed():
        raise RuntimeError("Event loop not registered for control panel runtime")

    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None

    if running is loop:
        future = asyncio.create_task(coro)
    else:
        future = asyncio.run_coroutine_threadsafe(coro, loop)

    def _log_result(_future: "asyncio.Future") -> None:
        try:
            _future.result()
        except Exception as err:  # pragma: no cover - log for visibility
            LOGGER.warning("WhatsApp controller task failed: %s", err)

    future.add_done_callback(_log_result)


def _apply_whatsapp_state(enabled: bool) -> None:
    global _LAST_WA_STATE, _PENDING_WA_STATE
    if wa_controller is None:
        return

    loop = _EVENT_LOOP
    if loop is None or loop.is_closed():
        # Remember the desired state until the loop is registered.
        _PENDING_WA_STATE = enabled
        if enabled:
            wa_controller.enable()
        else:
            wa_controller.disable()
        LOGGER.info("WhatsApp state %s queued until event loop is ready.", enabled)
        return

    if _LAST_WA_STATE is not None and _LAST_WA_STATE == enabled and _PENDING_WA_STATE is None:
        return

    try:
        if enabled:
            wa_controller.enable()
            _submit_to_loop(wa_controller.start())
        else:
            wa_controller.disable()
            _submit_to_loop(wa_controller.stop())
        _LAST_WA_STATE = enabled
        _PENDING_WA_STATE = None
    except Exception as exc:
        LOGGER.warning("Failed to apply WhatsApp state %s: %s", enabled, exc)


def _apply_private_state(enabled: bool) -> None:
    global _LAST_PRIVATE_STATE
    try:
        from privateTelegram.config.settings import save_settings, settings  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        LOGGER.debug(
            "Private Telegram settings unavailable for runtime sync.",
            exc_info=True,
        )
        return

    current = bool(settings.get("enabled", True))
    if current == enabled and _LAST_PRIVATE_STATE == enabled:
        return

    settings["enabled"] = enabled
    try:
        save_settings()
        _LAST_PRIVATE_STATE = enabled
    except Exception as exc:  # pragma: no cover - warn on failure
        LOGGER.warning("Failed to persist private Telegram state %s: %s", enabled, exc)


def apply_platform_states(platforms: Dict[str, bool], *, active: bool) -> None:
    """Apply platform enablement flags to the running services."""
    whatsapp_enabled = bool(platforms.get("whatsapp", True)) and active
    _apply_whatsapp_state(whatsapp_enabled)
    private_enabled = bool(platforms.get("privateTelegram", True)) and active
    _apply_private_state(private_enabled)


def refresh_working_hours_cache() -> None:
    """Ask the WhatsApp controller to reload working-hour settings."""
    if wa_controller is None:
        return
    try:
        wa_controller.refresh_working_hours()
    except Exception as exc:  # pragma: no cover - best-effort refresh
        LOGGER.debug("Skipping WhatsApp working-hours refresh: %s", exc)
