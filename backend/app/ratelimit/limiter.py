"""In-memory rate limiting primitives.

Two complementary mechanisms, because neither alone is sufficient against
password guessing:

- `SlidingWindowLimiter` caps requests per key per window. Keyed by client IP
  it stops one host hammering the login endpoint, including across many
  different accounts.
- `FailureTracker` locks a single account after repeated failures, with
  exponential backoff. This is what stops a *distributed* attack: an attacker
  rotating through a botnet defeats a per-IP limit entirely, but still has to
  get past the per-account counter.

Known tradeoff, stated rather than hidden: a per-account lockout means someone
who knows your email can deliberately trigger it and keep you out for up to
`max_seconds`. The cap is deliberately minutes rather than hours to bound that,
and failures are cleared the moment a correct password succeeds. Until password
reset exists, a longer cap would be the more harmful side of the trade.

State is per-process and in memory. With more than one worker, each holds its
own counters, so the effective limit multiplies by the worker count. That is
fine for a single-process deployment and is the reason the limits below are
set conservatively; a multi-worker deployment wants a shared store such as
Redis, and this module is deliberately small enough to swap behind the same
interface.
"""

from __future__ import annotations

import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from threading import Lock

# Bound on tracked keys, so an attacker cycling IPs cannot grow memory without
# limit. Least-recently-used keys are evicted first.
MAX_TRACKED_KEYS = 20_000


@dataclass(frozen=True)
class Decision:
    """The outcome of one check. `retry_after` is whole seconds, >= 1."""

    allowed: bool
    retry_after: int = 0


class SlidingWindowLimiter:
    """Allows `limit` events per `window_seconds` for each key.

    A sliding window rather than a fixed one: a fixed window lets twice the
    limit through across a boundary, which matters when the limit is small.
    """

    def __init__(self, limit: int, window_seconds: int, *, name: str = "") -> None:
        if limit < 1 or window_seconds < 1:
            raise ValueError("limit and window_seconds must both be >= 1")
        self.limit = limit
        self.window = window_seconds
        self.name = name
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def check(self, key: str, *, now: float | None = None) -> Decision:
        """Record an event for `key` and say whether it is allowed.

        A rejected event is *not* recorded, so a client that keeps hammering
        while blocked does not push its own unblock time further out.
        """
        moment = time.monotonic() if now is None else now

        with self._lock:
            events = self._events.get(key)
            if events is None:
                events = deque()
                self._events[key] = events
            self._events.move_to_end(key)

            cutoff = moment - self.window
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= self.limit:
                retry = max(1, int(events[0] + self.window - moment) + 1)
                return Decision(allowed=False, retry_after=retry)

            events.append(moment)
            self._evict_if_needed()
            return Decision(allowed=True)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)

    def _evict_if_needed(self) -> None:
        """Caller holds the lock."""
        while len(self._events) > MAX_TRACKED_KEYS:
            self._events.popitem(last=False)


class FailureTracker:
    """Counts consecutive failures per key and locks the key with backoff.

    After `threshold` consecutive failures, each further failure locks the key
    for `base_seconds * 2 ** (n - threshold)`, capped at `max_seconds`. A
    success clears the record entirely.
    """

    def __init__(
        self,
        threshold: int,
        base_seconds: int,
        max_seconds: int,
        *,
        name: str = "",
    ) -> None:
        self.threshold = threshold
        self.base = base_seconds
        self.max_seconds = max_seconds
        self.name = name
        # key -> (consecutive_failures, locked_until_monotonic)
        self._state: OrderedDict[str, tuple[int, float]] = OrderedDict()
        self._lock = Lock()

    def locked_for(self, key: str, *, now: float | None = None) -> int:
        """Seconds remaining on an active lock, or 0 when not locked."""
        moment = time.monotonic() if now is None else now
        with self._lock:
            record = self._state.get(key)
            if record is None:
                return 0
            _, locked_until = record
            remaining = locked_until - moment
            return max(0, int(remaining) + 1) if remaining > 0 else 0

    def record_failure(self, key: str, *, now: float | None = None) -> int:
        """Register a failure. Returns the resulting lock in seconds (0 if none)."""
        moment = time.monotonic() if now is None else now
        with self._lock:
            failures, _ = self._state.get(key, (0, 0.0))
            failures += 1

            lock_seconds = 0
            locked_until = 0.0
            if failures >= self.threshold:
                exponent = failures - self.threshold
                # Cap the exponent before shifting so a long-running attack
                # cannot build an enormous intermediate value.
                exponent = min(exponent, 32)
                lock_seconds = min(self.base * (2**exponent), self.max_seconds)
                locked_until = moment + lock_seconds

            self._state[key] = (failures, locked_until)
            self._state.move_to_end(key)
            while len(self._state) > MAX_TRACKED_KEYS:
                self._state.popitem(last=False)

            return lock_seconds

    def record_success(self, key: str) -> None:
        with self._lock:
            self._state.pop(key, None)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._state.clear()
            else:
                self._state.pop(key, None)
