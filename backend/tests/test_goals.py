from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from astrapath.models import AuditLog, GoalVersion
from tests.conftest import bearer, create_goal, register_student


def test_goal_lifecycle_versions_and_audit(
    client: TestClient,
    student_identity: tuple[dict, dict[str, str]],
    session_factory: sessionmaker[Session],
) -> None:
    _student, headers = student_identity
    goal = create_goal(client, headers)
    assert goal["status"] == "draft"
    assert goal["version"] == 1

    activated = client.post(
        f"/api/v1/student/goals/{goal['id']}/activate",
        headers=headers,
        json={"expected_version": 1, "reason": "Goal definition approved"},
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    paused = client.post(
        f"/api/v1/student/goals/{goal['id']}/pause",
        headers=headers,
        json={"expected_version": 2, "reason": "Exam week"},
    )
    assert paused.status_code == 200
    resumed = client.post(
        f"/api/v1/student/goals/{goal['id']}/resume",
        headers=headers,
        json={"expected_version": 3, "reason": "Exam week completed"},
    )
    assert resumed.status_code == 200
    completed = client.post(
        f"/api/v1/student/goals/{goal['id']}/complete",
        headers=headers,
        json={"expected_version": 4, "reason": "Success criteria met"},
    )
    assert completed.status_code == 200
    assert completed.json()["version"] == 5

    terminal_edit = client.patch(
        f"/api/v1/student/goals/{goal['id']}",
        headers=headers,
        json={
            "expected_version": 5,
            "change_reason": "Should fail",
            "title": "Changed terminal goal",
        },
    )
    assert terminal_edit.status_code == 409
    assert terminal_edit.json()["error"]["code"] == "goal_not_editable"

    versions = client.get(
        f"/api/v1/student/goals/{goal['id']}/versions",
        headers=headers,
    )
    assert versions.status_code == 200
    assert [item["version"] for item in versions.json()] == [5, 4, 3, 2, 1]

    with session_factory() as db:
        assert db.scalar(select(func.count(GoalVersion.id))) == 5
        goal_audits = db.scalar(
            select(func.count(AuditLog.id)).where(AuditLog.resource_type == "goal")
        )
    assert goal_audits == 5


def test_activation_requires_success_definition(
    client: TestClient,
    student_identity: tuple[dict, dict[str, str]],
) -> None:
    _student, headers = student_identity
    goal = create_goal(client, headers, success_criteria=[])
    response = client.post(
        f"/api/v1/student/goals/{goal['id']}/activate",
        headers=headers,
        json={"expected_version": 1, "reason": "Try incomplete activation"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "goal_not_ready"


def test_goal_ownership_is_enforced(
    client: TestClient,
    student_identity: tuple[dict, dict[str, str]],
) -> None:
    _first_student, first_headers = student_identity
    goal = create_goal(client, first_headers)
    second = register_student(client, email="second@example.com", name="Second Student")
    response = client.get(
        f"/api/v1/student/goals/{goal['id']}",
        headers=bearer(second["access_token"]),
    )
    assert response.status_code == 404

