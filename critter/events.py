from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

USER_MESSAGE = "user_message"
THINKING = "thinking"
ASSISTANT_TEXT = "assistant_text"
TOOL_STARTED = "tool_started"
TOOL_FINISHED = "tool_finished"
PERMISSION_REQUEST = "permission_request"
MOOD = "mood"
DONE = "done"
ERROR = "error"

log = logging.getLogger("critter")


@dataclass(frozen=True)
class Event:
    kind: str
    payload: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class EventBus:
    """Tiny synchronous pub/sub. Subscribers run in the publisher's thread,
    so a UI adapter should hand the event to its own thread (Qt signal)."""

    def __init__(self) -> None:
        self._subs: list[Callable[[Event], None]] = []
        self._lock = threading.Lock()

    def subscribe(self, fn: Callable[[Event], None]) -> None:
        with self._lock:
            self._subs.append(fn)

    def publish(self, kind: str, **payload) -> Event:
        ev = Event(kind, payload)
        with self._lock:
            subs = list(self._subs)
        for fn in subs:
            try:
                fn(ev)
            except Exception:
                log.exception("subscriber failed on %s", kind)
        return ev
