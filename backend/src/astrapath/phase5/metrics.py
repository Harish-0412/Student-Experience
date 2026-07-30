import math
import threading
from collections import Counter, deque
from collections.abc import Iterable

from astrapath.phase5.contracts import MetricsSnapshot


def _percentile(values: Iterable[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0
    index = max(math.ceil(percentile * len(ordered)) - 1, 0)
    return round(ordered[index], 3)


class MetricsRegistry:
    """Bounded, private-content-free process metrics for the API runtime."""

    def __init__(self, latency_sample_size: int = 10_000) -> None:
        self._lock = threading.Lock()
        self._requests_total = 0
        self._in_flight = 0
        self._by_status: Counter[str] = Counter()
        self._by_method: Counter[str] = Counter()
        self._by_route: Counter[str] = Counter()
        self._latencies_ms: deque[float] = deque(maxlen=latency_sample_size)
        self._idempotent_replays = 0
        self._rate_limited = 0
        self._payload_rejections = 0
        self._capacity_rejections = 0
        self._unhandled_errors = 0

    def begin(self) -> None:
        with self._lock:
            self._requests_total += 1
            self._in_flight += 1

    def complete(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        with self._lock:
            self._in_flight = max(self._in_flight - 1, 0)
            self._by_status[str(status_code)] += 1
            self._by_method[method] += 1
            self._by_route[route] += 1
            self._latencies_ms.append(duration_ms)

    def rejected(self, kind: str) -> None:
        with self._lock:
            if kind == "rate_limit":
                self._rate_limited += 1
            elif kind == "payload":
                self._payload_rejections += 1
            elif kind == "capacity":
                self._capacity_rejections += 1
            elif kind == "unhandled":
                self._unhandled_errors += 1

    def replayed(self) -> None:
        with self._lock:
            self._idempotent_replays += 1

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            latencies = list(self._latencies_ms)
            return MetricsSnapshot(
                requests_total=self._requests_total,
                requests_in_flight=self._in_flight,
                responses_by_status=dict(self._by_status),
                requests_by_method=dict(self._by_method),
                requests_by_route=dict(self._by_route),
                latency_p50_ms=_percentile(latencies, 0.50),
                latency_p95_ms=_percentile(latencies, 0.95),
                idempotent_replays_total=self._idempotent_replays,
                rate_limited_total=self._rate_limited,
                payload_rejections_total=self._payload_rejections,
                capacity_rejections_total=self._capacity_rejections,
                unhandled_errors_total=self._unhandled_errors,
            )
