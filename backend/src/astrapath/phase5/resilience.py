import asyncio
import inspect
import threading
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from astrapath.errors import AppError


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_seconds: float = 0.05
    max_delay_seconds: float = 1.0
    retryable_exceptions: tuple[type[Exception], ...] = (TimeoutError, ConnectionError)

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delays cannot be negative")


async def retry_async[ResultT](
    operation: Callable[[], Awaitable[ResultT]],
    *,
    policy: RetryPolicy | None = None,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> ResultT:
    resolved = policy or RetryPolicy()
    for attempt in range(1, resolved.max_attempts + 1):
        try:
            return await operation()
        except resolved.retryable_exceptions as exc:
            if attempt == resolved.max_attempts:
                raise
            if on_retry:
                on_retry(attempt, exc)
            delay = min(
                resolved.base_delay_seconds * (2 ** (attempt - 1)),
                resolved.max_delay_seconds,
            )
            await asyncio.sleep(delay)
    raise RuntimeError("retry loop exhausted without returning or raising")


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Small process-local breaker for bounded external service calls."""

    def __init__(self, *, failure_threshold: int = 3, recovery_seconds: float = 30) -> None:
        if failure_threshold < 1 or recovery_seconds < 0:
            raise ValueError("Circuit breaker thresholds must be positive")
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._lock = threading.Lock()
        self._failures = 0
        self._opened_at: float | None = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if (
                self._state == CircuitState.OPEN
                and self._opened_at is not None
                and time.monotonic() - self._opened_at >= self.recovery_seconds
            ):
                self._state = CircuitState.HALF_OPEN
            return self._state

    async def call[ResultT](
        self,
        operation: Callable[[], Awaitable[ResultT] | ResultT],
    ) -> ResultT:
        if self.state == CircuitState.OPEN:
            raise AppError(
                503,
                "dependency_circuit_open",
                "The dependency is temporarily unavailable",
            )
        try:
            result = operation()
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            self._record_failure()
            raise
        self._record_success()
        return result

    def _record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()

    def _record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None
            self._state = CircuitState.CLOSED
