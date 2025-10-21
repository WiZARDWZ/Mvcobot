"""Database helpers for recording standardised part code lookups."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from .code_standardization import StandardizedCode, standardize_code

LOGGER = logging.getLogger(__name__)

try:  # pragma: no cover - database is optional during unit tests
    from database.connector_bot import record_code_request
except Exception:  # pragma: no cover - fallback when connector is unavailable
    record_code_request = None  # type: ignore[assignment]


def _prepare_timestamp(ts: Optional[datetime]) -> datetime:
    if ts is None:
        ts = datetime.utcnow().replace(tzinfo=timezone.utc)
    elif ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)
    return ts.replace(tzinfo=None)


def record_code_lookup(
    platform: str,
    code: StandardizedCode,
    *,
    part_name: Optional[str] = None,
    requested_at: Optional[datetime] = None,
) -> None:
    """Persist a code lookup event in the analytics table."""
    if not code or record_code_request is None:  # pragma: no cover - defensive
        return

    platform_name = (platform or "unknown").strip() or "unknown"
    name_value = (part_name or "-").strip() or "-"
    timestamp = _prepare_timestamp(requested_at)

    try:
        record_code_request(
            platform=platform_name,
            code_norm=code.padded,
            code_display=code.display,
            part_name=name_value,
            requested_at=timestamp,
        )
    except Exception as exc:  # pragma: no cover - avoid disrupting bots
        LOGGER.debug("Failed to record code lookup for platform %s: %s", platform_name, exc)


def standardize_and_record(
    platform: str,
    raw_code: str,
    *,
    part_name: Optional[str] = None,
    requested_at: Optional[datetime] = None,
) -> Optional[StandardizedCode]:
    """Helper that standardises ``raw_code`` and records it when valid."""
    code = standardize_code(raw_code)
    if not code:
        return None
    record_code_lookup(
        platform,
        code,
        part_name=part_name,
        requested_at=requested_at,
    )
    return code


__all__ = [
    "record_code_lookup",
    "standardize_and_record",
]
