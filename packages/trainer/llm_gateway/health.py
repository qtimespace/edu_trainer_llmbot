import time
from collections import defaultdict
from collections.abc import Callable
from typing import Literal

State = Literal["healthy", "degraded", "open", "half_open"]


class CircuitBreaker:
    """Состояние провайдеров в памяти процесса: healthy → degraded → open → half_open."""

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 60.0,
                 clock: Callable[[], float] = time.monotonic):
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._failures: dict[str, int] = defaultdict(int)
        self._opened_at: dict[str, float] = {}

    def state(self, provider: str) -> State:
        if provider in self._opened_at:
            return "half_open" if self._clock() - self._opened_at[provider] >= self._cooldown else "open"
        return "degraded" if self._failures[provider] > 0 else "healthy"

    def allow(self, provider: str) -> bool:
        return self.state(provider) != "open"

    def record_success(self, provider: str) -> None:
        self._failures[provider] = 0
        self._opened_at.pop(provider, None)

    def record_failure(self, provider: str) -> None:
        if self.state(provider) == "half_open":
            self._opened_at[provider] = self._clock()
            return
        self._failures[provider] += 1
        if self._failures[provider] >= self._threshold:
            self._opened_at[provider] = self._clock()
