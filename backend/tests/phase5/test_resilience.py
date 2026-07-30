import asyncio

import pytest

from astrapath.errors import AppError
from astrapath.phase5.resilience import (
    CircuitBreaker,
    CircuitState,
    RetryPolicy,
    retry_async,
)


def test_retry_uses_bounded_exponential_attempts() -> None:
    attempts = 0
    retries: list[int] = []

    async def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TimeoutError("temporary timeout")
        return "ready"

    result = asyncio.run(
        retry_async(
            operation,
            policy=RetryPolicy(
                max_attempts=3,
                base_delay_seconds=0,
                max_delay_seconds=0,
            ),
            on_retry=lambda attempt, _error: retries.append(attempt),
        )
    )
    assert result == "ready"
    assert attempts == 3
    assert retries == [1, 2]


def test_circuit_breaker_opens_and_fails_fast() -> None:
    breaker = CircuitBreaker(failure_threshold=2, recovery_seconds=60)

    async def fail() -> str:
        raise ConnectionError("dependency unavailable")

    with pytest.raises(ConnectionError):
        asyncio.run(breaker.call(fail))
    with pytest.raises(ConnectionError):
        asyncio.run(breaker.call(fail))
    assert breaker.state == CircuitState.OPEN

    with pytest.raises(AppError, match="temporarily unavailable") as error:
        asyncio.run(breaker.call(fail))
    assert error.value.status_code == 503
