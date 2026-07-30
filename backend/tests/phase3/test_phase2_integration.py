from sqlalchemy import select

from astrapath.models import AuditLog

from .conftest import create_goal


def test_phase2_uses_phase1_bearer_auth_and_audit(
    client,
    planning_student,
    session_factory,
) -> None:
    goal = create_goal(
        client,
        planning_student["headers"],
        title="Calculus exam",
        raw_statement="Prepare for my calculus exam",
        weeks=8,
    )
    unauthenticated = client.post(
        f"/api/v1/goals/{goal['id']}/clarify",
        json={"template_slug": "calculus-exam"},
    )
    assert unauthenticated.status_code == 401

    authenticated = client.post(
        f"/api/v1/goals/{goal['id']}/clarify",
        headers=planning_student["headers"],
        json={
            "template_slug": "calculus-exam",
            "weekly_hours": 10,
        },
    )
    assert authenticated.status_code == 200, authenticated.text

    with session_factory() as db:
        log = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "phase2.goal_clarified",
                AuditLog.resource_id == goal["id"],
            )
        )
        assert log is not None
        assert str(log.actor_id) == planning_student["user"]["id"]
