import argparse
import asyncio
import json
import math
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class LoadReport:
    requests: int
    concurrency: int
    successes: int
    failures: int
    error_rate: float
    duration_seconds: float
    requests_per_second: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_max_ms: float


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(math.ceil(len(ordered) * percentile) - 1, 0)
    return round(ordered[index], 3)


async def run_load(
    *,
    requests: int,
    concurrency: int,
    path: str = "/api/v1/health/live",
    base_url: str = "http://127.0.0.1:8000",
    app: Any | None = None,
    timeout_seconds: float = 10,
) -> LoadReport:
    if requests < 1 or concurrency < 1:
        raise ValueError("requests and concurrency must be positive")
    transport = httpx.ASGITransport(app=app) if app is not None else None
    semaphore = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    statuses: list[int] = []

    async with httpx.AsyncClient(
        base_url=base_url,
        transport=transport,
        timeout=timeout_seconds,
        headers={"Host": "testserver" if app is not None else httpx.URL(base_url).host},
    ) as client:
        started_at = time.perf_counter()

        async def execute() -> None:
            async with semaphore:
                request_started = time.perf_counter()
                try:
                    response = await client.get(path)
                    statuses.append(response.status_code)
                except httpx.HTTPError:
                    statuses.append(0)
                latencies.append((time.perf_counter() - request_started) * 1000)

        await asyncio.gather(*(execute() for _ in range(requests)))
        elapsed = time.perf_counter() - started_at

    successes = sum(200 <= status < 400 for status in statuses)
    failures = requests - successes
    return LoadReport(
        requests=requests,
        concurrency=concurrency,
        successes=successes,
        failures=failures,
        error_rate=round(failures / requests, 6),
        duration_seconds=round(elapsed, 3),
        requests_per_second=round(requests / elapsed, 3),
        latency_p50_ms=_percentile(latencies, 0.50),
        latency_p95_ms=_percentile(latencies, 0.95),
        latency_max_ms=round(max(latencies, default=0), 3),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AstraPath Phase 5 HTTP load check")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--path", default="/api/v1/health/live")
    parser.add_argument("--requests", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=25)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    parser.add_argument("--max-p95-ms", type=float, default=500)
    args = parser.parse_args()
    report = asyncio.run(
        run_load(
            requests=args.requests,
            concurrency=args.concurrency,
            path=args.path,
            base_url=args.base_url,
        )
    )
    print(json.dumps(asdict(report), indent=2))
    if report.error_rate > args.max_error_rate or report.latency_p95_ms > args.max_p95_ms:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
