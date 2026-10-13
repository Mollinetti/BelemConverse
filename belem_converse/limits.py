"""Fair use: per-visitor message limit and a daily cap on model calls."""

# ponytail: per-process memory, resets on restart

from __future__ import annotations

import os
import time
from collections import deque
from datetime import datetime
from zoneinfo import ZoneInfo

from belem_converse.cities import get_city_config


class RateLimiter:
    """At most ``max_hits`` hits per key in any ``window_s`` seconds."""

    def __init__(self, max_hits: int = 20, window_s: float = 600, clock=time.monotonic,
                 max_keys: int = 10_000):
        self.max_hits = max_hits
        self.window_s = window_s
        self.clock = clock
        self.max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}

    def __len__(self) -> int:
        return len(self._hits)

    def hit(self, key: str) -> bool:
        """Record a hit for ``key``; False (and not recorded) when over the limit."""
        now = self.clock()
        if len(self._hits) >= self.max_keys:  # forget visitors idle for a whole window
            self._hits = {k: h for k, h in self._hits.items() if now - h[-1] < self.window_s}
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= self.window_s:
            hits.popleft()
        if len(hits) >= self.max_hits:
            return False
        hits.append(now)
        return True


def client_ip(forwarded_for: str | None, socket_host: str | None) -> str:
    """The visitor's address: the right-most X-Forwarded-For entry, which
    Render's proxy appends (left-most entries are whatever the client sent),
    else the socket peer."""
    return (forwarded_for or "").split(",")[-1].strip() or socket_host or "unknown"


class DailyCap:
    """At most ``cap`` model calls per calendar day in the city's time zone."""

    def __init__(self, cap: int | None = None, clock=None):
        if cap is None:
            try:
                cap = int(os.getenv("LLM_DAILY_CAP", ""))
            except ValueError:
                cap = 800
        self.cap = cap
        city_tz = ZoneInfo(get_city_config().timezone)
        self.clock = clock or (lambda: datetime.now(city_tz))
        self._day = None
        self._used = 0

    def take(self) -> bool:
        """Spend one model call from today's budget; False once it is used up."""
        today = self.clock().date()
        if today != self._day:
            self._day, self._used = today, 0
        if self._used >= self.cap:
            return False
        self._used += 1
        return True
