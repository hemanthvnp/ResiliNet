"""In-memory run sessions (change add-rest-api, task 2.1; design: "Sessions are a dict keyed by a server-generated run id").

Each session has its own lock, so a slow recompute on one run never blocks another. At the cap,
the session with the lowest creation number is evicted: a counter, not a clock (design, Determinism).
"""

from __future__ import annotations

import itertools
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from fastapi import HTTPException

DEFAULT_CAP = 64


@dataclass
class Session:
    state: Any
    created: int
    lock: threading.Lock = field(default_factory=threading.Lock)


class SessionStore:
    def __init__(self, cap: int = DEFAULT_CAP) -> None:
        self.cap = cap
        self._sessions: dict[str, Session] = {}
        self._counter = itertools.count()
        self._lock = threading.Lock()  # guards the dict only, never held during a recompute

    def create(self, state: Any) -> str:
        run_id = uuid.uuid4().hex
        with self._lock:
            # ponytail: O(n) scan for the oldest, fine at a cap of tens
            while len(self._sessions) >= self.cap:
                oldest = min(self._sessions, key=lambda rid: self._sessions[rid].created)
                del self._sessions[oldest]
            self._sessions[run_id] = Session(state, next(self._counter))
        return run_id

    @contextmanager
    def locked(self, run_id: str) -> Iterator[Session]:
        """Hold the run's lock; read and replace `session.state` inside. Unknown run gives 404."""
        with self._lock:
            session = self._sessions.get(run_id)
        if session is None:
            raise HTTPException(404, f"unknown run {run_id!r}")
        with session.lock:
            yield session
