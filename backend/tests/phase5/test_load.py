import asyncio

from astrapath.config import Settings
from astrapath.main import create_app
from astrapath.phase5.load import run_load


def test_concurrent_liveness_load_gate() -> None:
    app = create_app(
        Settings(
            environment="test",
            jwt_secret="phase5-load-secret-with-at-least-thirty-two-characters",
            rate_limit_requests=5000,
            max_inflight_requests=100,
        )
    )
    report = asyncio.run(
        run_load(
            requests=250,
            concurrency=25,
            app=app,
        )
    )
    assert report.successes == 250
    assert report.error_rate == 0
    assert report.latency_p95_ms < 1000
    assert report.requests_per_second > 20
