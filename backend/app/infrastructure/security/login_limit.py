import time
from collections import defaultdict, deque
from threading import Lock


class LoginAttemptLimiter:
    """Bound password guesses per client address in one API process."""

    def __init__(self, maximum_failures: int, window_seconds: int) -> None:
        self._maximum_failures = maximum_failures
        self._window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def retry_after(self, client_address: str) -> int:
        now = time.monotonic()
        with self._lock:
            failures = self._failures.get(client_address)
            if failures is None:
                return 0
            self._prune(failures, now)
            if not failures:
                self._failures.pop(client_address, None)
                return 0
            if len(failures) < self._maximum_failures:
                return 0
            return max(1, int(failures[0] + self._window_seconds - now) + 1)

    def record_failure(self, client_address: str) -> None:
        now = time.monotonic()
        with self._lock:
            failures = self._failures[client_address]
            self._prune(failures, now)
            failures.append(now)

    def clear(self, client_address: str) -> None:
        with self._lock:
            self._failures.pop(client_address, None)

    def _prune(self, failures: deque[float], now: float) -> None:
        while failures and failures[0] + self._window_seconds <= now:
            failures.popleft()
