from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from tests.phase3.conftest import complete_phase2, create_goal
from tests.phase3.test_planning_journey import CALCULUS_EVIDENCE


def test_goal_to_execution_risk_replan_and_operational_readiness(
    client: TestClient,
    planning_student: dict,
    admin_identity: tuple[object, dict[str, str]],
    session_factory: sessionmaker[Session],
) -> None:
    del session_factory
    student_headers = planning_student["headers"]
    _admin, admin_headers = admin_identity
    goal = create_goal(
        client,
        student_headers,
        title="Adaptive calculus certification",
        raw_statement="Prepare for a calculus certification with verified practice",
        weeks=8,
    )
    complete_phase2(
        client,
        student_headers,
        goal["id"],
        template_slug="calculus-exam",
        weekly_hours=10,
        evidence=CALCULUS_EVIDENCE,
    )

    generated = client.post(
        f"/api/v1/goals/{goal['id']}/plan",
        headers=student_headers,
        json={
            "constraints": {
                "max_session_minutes": 60,
                "minimum_break_minutes": 15,
                "max_daily_minutes": 120,
                "buffer_ratio": 0.15,
            }
        },
    )
    assert generated.status_code == 201, generated.text
    source_plan = generated.json()
    approved = client.post(
        f"/api/v1/goals/{goal['id']}/plan/decision",
        headers=student_headers,
        json={"decision": "approve", "reason": "Begin the evidence-backed plan"},
    )
    assert approved.status_code == 200, approved.text
    source_plan = approved.json()
    first_task = source_plan["tasks"][0]

    focus = client.post(
        "/api/v1/student/focus-sessions",
        headers=student_headers,
        json={
            "goal_id": goal["id"],
            "task_ref": first_task["id"],
            "milestone_ref": first_task["milestone_id"],
            "objective": first_task["title"],
            "planned_minutes": min(first_task["estimated_minutes"], 60),
            "idempotency_key": "phase5-e2e-focus-001",
        },
    )
    assert focus.status_code == 201, focus.text
    completed_focus = client.post(
        f"/api/v1/student/focus-sessions/{focus.json()['id']}/complete",
        headers=student_headers,
        json={
            "expected_version": 1,
            "actual_minutes": min(first_task["estimated_minutes"], 55),
            "distraction_count": 1,
            "blocker_notes": ["Technical environment access is blocked"],
            "reflection": "The concept is clearer, but tooling remains blocked.",
            "accomplished": True,
        },
    )
    assert completed_focus.status_code == 200, completed_focus.text

    completed_task = client.patch(
        f"/api/v1/goals/{goal['id']}/plan/tasks/{first_task['id']}/status",
        headers=student_headers,
        json={
            "status": "completed",
            "expected_status": first_task["status"],
            "reason": "Completed in a tracked focus session",
        },
    )
    assert completed_task.status_code == 200, completed_task.text

    progress = client.post(
        f"/api/v1/student/goals/{goal['id']}/progress/rebuild",
        headers=student_headers,
    )
    assert progress.status_code == 200, progress.text
    assert progress.json()["focus_minutes"] > 0

    scan = client.post(
        f"/api/v1/student/goals/{goal['id']}/risks/scan",
        headers=student_headers,
        json={"open_blockers": ["Technical environment access is blocked"]},
    )
    assert scan.status_code == 200, scan.text
    risk = next(
        item for item in scan.json()["risks"] if item["requires_admin_review"]
    )
    proposal = client.post(
        f"/api/v1/student/goals/{goal['id']}/replans",
        headers=student_headers,
        json={
            "risk_id": risk["id"],
            "base_plan_ref": source_plan["id"],
            "base_plan_version": source_plan["version"],
            "preserve_completed_work": True,
            "student_constraints": {"max_weekly_minutes": 300},
        },
    )
    assert proposal.status_code == 201, proposal.text
    proposed = proposal.json()
    assert proposed["admin_review_required"] is True
    assert proposed["preserves_completed_work"] is True

    admin_decision = client.post(
        f"/api/v1/admin/phase4/replans/{proposed['id']}/decision",
        headers=admin_headers,
        json={
            "decision": "approve",
            "expected_version": proposed["version"],
            "reason": "The patch preserves completed work and reduces overload.",
        },
    )
    assert admin_decision.status_code == 200, admin_decision.text
    student_decision = client.post(
        f"/api/v1/student/replans/{proposed['id']}/decision",
        headers=student_headers,
        json={
            "decision": "approve",
            "expected_version": admin_decision.json()["version"],
            "reason": "Apply the smaller recovery tasks.",
        },
    )
    assert student_decision.status_code == 200, student_decision.text
    applied = student_decision.json()
    assert applied["status"] == "applied"
    assert applied["applied_plan_version"] == 2

    current = client.get(
        f"/api/v1/goals/{goal['id']}/plan",
        headers=student_headers,
    )
    assert current.status_code == 200, current.text
    assert current.json()["id"] == applied["applied_plan_ref"]
    assert current.json()["version"] == 2
    assert any(task["status"] == "completed" for task in current.json()["tasks"])

    operations = client.get(
        "/api/v1/admin/operations/status",
        headers=admin_headers,
    )
    assert operations.status_code == 200, operations.text
    assert operations.json()["status"] == "ready"
    assert operations.json()["audit"]["valid"] is True
