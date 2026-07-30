from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from astrapath.models import AuditLog, StudentProfileVersion
from tests.conftest import onboard


def test_profile_is_versioned_and_audited(
    client: TestClient,
    student_identity: tuple[dict, dict[str, str]],
    session_factory: sessionmaker[Session],
) -> None:
    _student, headers = student_identity
    profile = onboard(client, headers)
    assert profile["version"] == 1

    updated = client.patch(
        "/api/v1/student/profile",
        headers=headers,
        json={
            "expected_version": 1,
            "change_reason": "More weekly availability",
            "weekly_learning_minutes": 600,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["weekly_learning_minutes"] == 600

    stale = client.patch(
        "/api/v1/student/profile",
        headers=headers,
        json={
            "expected_version": 1,
            "change_reason": "Stale browser tab",
            "weekly_learning_minutes": 300,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["details"]["current_version"] == 2

    with session_factory() as db:
        version_count = db.scalar(select(func.count(StudentProfileVersion.id)))
        audit_count = db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.action.in_(
                    ["student.profile_created", "student.profile_updated"]
                )
            )
        )
    assert version_count == 2
    assert audit_count == 2


def test_student_cannot_use_admin_api(
    client: TestClient,
    student_identity: tuple[dict, dict[str, str]],
) -> None:
    _student, headers = student_identity
    response = client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"

