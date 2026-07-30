from collections.abc import Generator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from astrapath.config import Settings
from astrapath.db import get_db
from astrapath.main import create_app
from tests.conftest import TEST_PASSWORD, bearer, create_admin, register_student


@contextmanager
def configured_client(
    session_factory: sessionmaker[Session],
    **overrides: object,
) -> Generator[tuple[TestClient, object], None, None]:
    settings = Settings(
        environment="test",
        database_url="sqlite://",
        auth_mode="local",
        jwt_secret="phase5-test-secret-with-at-least-thirty-two-characters",
        **overrides,
    )
    app = create_app(settings)

    def override_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, app


def test_security_headers_identifiers_payload_limit_and_trusted_host(
    session_factory: sessionmaker[Session],
) -> None:
    with configured_client(session_factory, max_request_bytes=256) as (client, _app):
        healthy = client.get(
            "/api/v1/health/live",
            headers={"X-Request-ID": "phase5-request-001"},
        )
        assert healthy.status_code == 200
        assert healthy.headers["x-request-id"] == "phase5-request-001"
        assert healthy.headers["x-content-type-options"] == "nosniff"
        assert healthy.headers["x-frame-options"] == "DENY"
        assert "default-src 'none'" in healthy.headers["content-security-policy"]
        assert "camera=()" in healthy.headers["permissions-policy"]

        invalid_id = client.get(
            "/api/v1/health/live",
            headers={"X-Request-ID": "invalid request id"},
        )
        assert invalid_id.status_code == 400
        assert invalid_id.json()["error"]["code"] == "invalid_request_identifier"

        oversized = client.post(
            "/api/v1/auth/register",
            content=b"x" * 257,
            headers={"Content-Type": "application/json"},
        )
        assert oversized.status_code == 413
        assert oversized.json()["error"]["code"] == "payload_too_large"

        untrusted = client.get(
            "/api/v1/health/live",
            headers={"Host": "attacker.example"},
        )
        assert untrusted.status_code == 400
        assert untrusted.headers["x-frame-options"] == "DENY"


def test_production_policy_and_unexpected_errors_fail_closed() -> None:
    with pytest.raises(ValidationError, match="Wildcard trusted hosts"):
        Settings(
            environment="production",
            jwt_secret="production-secret-with-at-least-thirty-two-characters",
            trusted_hosts=["*"],
        )

    app = create_app(
        Settings(
            environment="production",
            jwt_secret="production-secret-with-at-least-thirty-two-characters",
        )
    )

    def explode() -> None:
        raise RuntimeError("private implementation detail")

    app.add_api_route("/phase5-test-error", explode)
    with TestClient(
        app,
        base_url="https://testserver",
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/phase5-test-error")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private implementation detail" not in response.text
    assert response.headers["strict-transport-security"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_http_idempotency_replays_and_rejects_changed_input(
    session_factory: sessionmaker[Session],
) -> None:
    with configured_client(session_factory) as (client, _app):
        registration = {
            "email": "idempotent@example.com",
            "full_name": "Idempotent Student",
            "password": TEST_PASSWORD,
        }
        token_pair = client.post(
            "/api/v1/auth/register",
            json=registration,
        ).json()
        payload = {
            "title": "Idempotent goal",
            "raw_statement": "Build an idempotent learning plan",
            "priority": 4,
            "success_criteria": ["Plan is generated"],
            "assumptions": [],
        }
        headers = {"Idempotency-Key": "registration-001"}
        headers.update(bearer(token_pair["access_token"]))
        created = client.post("/api/v1/student/goals", json=payload, headers=headers)
        replayed = client.post("/api/v1/student/goals", json=payload, headers=headers)
        assert created.status_code == 201
        assert replayed.status_code == 201
        assert replayed.headers["x-idempotent-replay"] == "true"
        assert replayed.json() == created.json()

        changed = client.post(
            "/api/v1/student/goals",
            json={**payload, "title": "Changed goal"},
            headers=headers,
        )
        assert changed.status_code == 409
        assert changed.json()["error"]["code"] == "idempotency_conflict"

        auth_cache_attempt = client.post(
            "/api/v1/auth/login",
            json={
                "email": registration["email"],
                "password": registration["password"],
            },
            headers={"Idempotency-Key": "auth-login-001"},
        )
        assert auth_cache_attempt.status_code == 400
        assert auth_cache_attempt.json()["error"]["code"] == "idempotency_not_supported"


def test_rate_limit_is_enforced_without_losing_request_context(
    session_factory: sessionmaker[Session],
) -> None:
    with configured_client(
        session_factory,
        rate_limit_requests=2,
        rate_limit_window_seconds=60,
    ) as (client, _app):
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/live").status_code == 200
        rejected = client.get("/api/v1/health/live")
        assert rejected.status_code == 429
        assert rejected.json()["error"]["code"] == "rate_limit_exceeded"
        assert rejected.headers["retry-after"]
        assert rejected.headers["x-request-id"]


def test_operations_require_admin_and_verify_audit_chain(
    app_client: tuple[TestClient, object],
    session_factory: sessionmaker[Session],
) -> None:
    client, _app = app_client
    student_tokens = register_student(client, email="operations-student@example.com")
    student_headers = bearer(student_tokens["access_token"])
    _admin, admin_headers = create_admin(
        app_client,
        session_factory,
        email="operations-admin@example.com",
    )

    unauthenticated = client.get("/api/v1/admin/operations/status")
    assert unauthenticated.status_code == 401
    forbidden = client.get(
        "/api/v1/admin/operations/status",
        headers=student_headers,
    )
    assert forbidden.status_code == 403

    status = client.get("/api/v1/admin/operations/status", headers=admin_headers)
    assert status.status_code == 200, status.text
    assert status.json()["status"] == "ready"
    assert status.json()["phases"] == [1, 2, 3, 4, 5]
    assert status.json()["shared_agent_count"] == 9
    assert status.json()["phase4_agent_count"] == 10

    verification = client.post(
        "/api/v1/admin/operations/audit/verify",
        headers=admin_headers,
    )
    assert verification.status_code == 200
    assert verification.json()["valid"] is True

    with session_factory() as db:
        db.execute(
            text(
                "UPDATE audit_logs SET action = 'tampered' "
                "WHERE id = (SELECT id FROM audit_logs ORDER BY occurred_at LIMIT 1)"
            )
        )
        db.commit()

    tampered = client.post(
        "/api/v1/admin/operations/audit/verify",
        headers=admin_headers,
    )
    assert tampered.status_code == 200
    assert tampered.json()["valid"] is False
    assert tampered.json()["reason"] == "event_hash_mismatch"
