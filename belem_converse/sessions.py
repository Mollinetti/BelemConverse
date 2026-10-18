"""Conversations: 4 answered questions, the last plan, and the ranked list.

A session is keyed by the client's session_id and forgotten after 30 idle
minutes or when the store is full (least recently used first).
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field

MAX_TURNS = 4


@dataclass
class Session:
    turns_used: int = 0
    last_plan: dict | None = None  # slots of the last answered question
    ranked_ids: list[str] = field(default_factory=list)  # placeIds, best first (≤30)
    # Per-request fields of ranked places (distanceKm, openNowStatus), by placeId.
    annotations: dict[str, dict] = field(default_factory=dict)
    cursor: int = 0  # how many of ranked_ids have been shown
    touched_at: float = 0.0

    @property
    def turns_left(self) -> int:
        return MAX_TURNS - self.turns_used


# ponytail: in-process store; one Render instance. Move to a SQLite table if >1 instance.
class SessionStore:
    def __init__(self, ttl_s: float = 1800, max_sessions: int = 5000, clock=time.monotonic):
        self.ttl_s = ttl_s
        self.max_sessions = max_sessions
        self.clock = clock
        self._sessions: OrderedDict[str, Session] = OrderedDict()  # least recently used first

    def __len__(self) -> int:
        return len(self._sessions)

    def get_or_create(self, session_id: str) -> Session:
        now = self.clock()
        session = self._sessions.pop(session_id, None)
        if session is None or now - session.touched_at > self.ttl_s:
            session = Session()
        session.touched_at = now
        self._sessions[session_id] = session
        while len(self._sessions) > self.max_sessions or (
            now - next(iter(self._sessions.values())).touched_at > self.ttl_s
        ):
            self._sessions.popitem(last=False)
        return session
