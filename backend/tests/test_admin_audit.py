import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from astrapath.models import AuditLog
from tests.conftest import create_goal, register_student


def test_admin_can_view_users_agents_and_audit(
    client: TestClient,
    admin_identity: tuple[object, dict[str, str]],
) -> None:
    _admin, headers = admin_identity
    register_student(client)

    users = client.get("/api/v1/admin/users", headers=headers)
    assert users.status_code == 200
    assert users.json()["total"] == 2
    assert {item["role"] for item in users.json()["items"]} == {"student", "admin"}

    agents = client.get("/api/v1/admin/agents", headers=headers)
    assert agents.status_code == 200
    assert {item["name"] for item in agents.json()} == {
        "GoalClarificationAgent",
        "StudentProfileAgent",
        "SupervisorGovernanceAgent",
        "daily-action-planning-agent",
        "goal-feasibility-agent",
        "learning-path-architect-agent",
        "milestone-decomposition-agent",
        "schedule-time-budget-agent",
        "skill-gap-analysis-agent",
    }

    audit = client.get("/api/v1/admin/audit", headers=headers)
    assert audit.status_code == 200
    assert audit.json()["total"] >= 2
    assert all(item["event_hash"] for item in audit.json()["items"])


def test_admin_suspension_invalidates_existing_tokens(
    client: TestClient,
    admin_identity: tuple[object, dict[str, str]],
) -> None:
    _admin, admin_headers = admin_identity
    student = register_student(client)
    status_change = client.patch(
        f"/api/v1/admin/users/{student['user']['id']}/status",
        headers=admin_headers,
        json={"status": "suspended", "reason": "Security investigation"},
    )
    assert status_change.status_code == 200
    assert status_change.json()["status"] == "suspended"

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {student['access_token']}"},
    )
    assert me.status_code == 401


def test_audit_model_rejects_mutation(
    client: TestClient,
    student_identity: tuple[dict, dict[str, str]],
    session_factory: sessionmaker[Session],
) -> None:
    _student, headers = student_identity
    create_goal(client, headers)
    with session_factory() as db:
        log = db.scalar(select(AuditLog).limit(1))
        assert log is not None
        log.action = "tampered"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
