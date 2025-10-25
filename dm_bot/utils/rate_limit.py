"""Rate limiting helpers for DM bot notifications."""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, Tuple

_PERIOD_PATTERN = re.compile(r"^(?P<count>\d+)\s*/\s*(?P<window>\d+)?\s*(?P<unit>[a-zA-Z]+)?$")


def _parse_unit(unit: str) -> Optional[float]:
    unit = unit.lower()
    if unit in {"s", "sec", "secs", "second", "seconds"}:
        return 1.0
    if unit in {"m", "min", "mins", "minute", "minutes"}:
        return 60.0
    if unit in {"h", "hr", "hrs", "hour", "hours"}:
        return 3600.0
    if unit in {"d", "day", "days"}:
        return 86400.0
    return None


def _parse_rule(rule: str) -> Optional[Tuple[int, float]]:
    match = _PERIOD_PATTERN.match(rule.strip())
    if not match:
        return None
    count = int(match.group("count"))
    if count <= 0:
        return None
    window_raw = match.group("window")
    unit_raw = match.group("unit") or "min"
    unit_seconds = _parse_unit(unit_raw) or 60.0
    if window_raw is None:
        window = unit_seconds
    else:
        window = int(window_raw) * unit_seconds
    if window <= 0:
        return None
    return count, float(window)


@dataclass
class _Bucket:
    limit: Tuple[int, float]
    timestamps: Deque[float]


class RateLimiter:
    """Simple sliding-window rate limiter for DM bot notifications."""

    def __init__(self) -> None:
        self._buckets: Dict[str, _Bucket] = {}

    def allow(self, key: str, rule: Optional[str]) -> bool:
        if not rule:
            return True
        parsed = _parse_rule(rule)
        if not parsed:
            return True
        count, window = parsed
        bucket = self._buckets.get(key)
        now = time.monotonic()
        if bucket is None or bucket.limit != parsed:
            bucket = _Bucket(limit=parsed, timestamps=deque())
            self._buckets[key] = bucket
        timestamps = bucket.timestamps
        cutoff = now - window
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()
        if len(timestamps) >= count:
            return False
        timestamps.append(now)
        return True


__all__ = ["RateLimiter"]
