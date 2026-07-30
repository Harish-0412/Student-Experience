import uuid

from sqlalchemy import select

from astrapath.phase3.models import LearningPlan
from astrapath.phase4.models import ExecutionContext

from .conftest import complete_phase2, create_goal
from .test_planning_journey import CALCULUS_EVIDENCE


def test_phase3_execution_and_phase4_replan_are_transactionally_wired(
    client,
    planning_student,
    session_factory,
) -> None:
    headers = planning_student["headers"]
    goal = create_goal(
        client,
        headers,
        title="Adaptive calculus plan",
        raw_statement="Prepare for a calculus exam with adaptive support",
        weeks=8,
    )
    complete_phase2(
        client,
        headers,
        goal["id"],
        template_slug="calculus-exam",
        weekly_hours=10,
        evidence=CALCULUS_EVIDENCE,
    )

    generated = client.post(
        f"/api/v1/goals/{goal['id']}/plan",
        headers=headers,
        json={},
    )
    assert generated.status_code == 201, generated.text
    source_plan = generated.json()

    approved = client.post(
        f"/api/v1/goals/{goal['id']}/plan/decision",
        headers=headers,
        json={"decision": "approve", "reason": "Start the adaptive plan"},
    )
    assert approved.status_code == 200, approved.text
    source_plan = approved.json()

    with session_factory() as db:
        context = db.scalar(
            select(ExecutionContext).where(
                ExecutionContext.goal_id == uuid.UUID(goal["id"])
            )
        )
        assert context is not None
        assert context.plan_ref == source_plan["id"]
        assert context.plan_version == 1
        assert context.completed_task_count == 0

    first_task = source_plan["tasks"][0]
    completed = client.patch(
        (
            f"/api/v1/goals/{goal['id']}/plan/tasks/"
            f"{first_task['id']}/status"
        ),
        headers=headers,
        json={
            "status": "completed",
            "expected_status": first_task["status"],
            "reason": "Completed during the first study session",
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["tasks"][0]["status"] == "completed"

    with session_factory() as db:
        context = db.scalar(
            select(ExecutionContext).where(
                ExecutionContext.goal_id == uuid.UUID(goal["id"])
            )
        )
        assert context is not None
        assert context.completed_task_count == 1

    progress = client.post(
        f"/api/v1/student/goals/{goal['id']}/progress/rebuild",
        headers=headers,
    )
    assert progress.status_code == 200, progress.text

    scan = client.post(
        f"/api/v1/student/goals/{goal['id']}/risks/scan",
        headers=headers,
        json={},
    )
    assert scan.status_code == 200, scan.text
    risk = next(
        item for item in scan.json()["risks"] if item["risk_type"] == "low_engagement"
    )
    assert risk["requires_admin_review"] is False

    proposal = client.post(
        f"/api/v1/student/goals/{goal['id']}/replans",
        headers=headers,
        json={
            "risk_id": risk["id"],
            "base_plan_ref": source_plan["id"],
            "base_plan_version": source_plan["version"],
            "preserve_completed_work": True,
            "student_constraints": {},
        },
    )
    assert proposal.status_code == 201, proposal.text
    proposed = proposal.json()
    assert proposed["proposed_patch"][0]["op"] == "split_next_task"

    decision = client.post(
        f"/api/v1/student/replans/{proposed['id']}/decision",
        headers=headers,
        json={
            "decision": "approve",
            "expected_version": proposed["version"],
            "reason": "Use smaller tasks to restart momentum",
        },
    )
    assert decision.status_code == 200, decision.text
    applied = decision.json()
    assert applied["status"] == "applied"
    assert applied["applied_plan_version"] == 2
    assert applied["applied_plan_ref"] != source_plan["id"]

    current = client.get(
        f"/api/v1/goals/{goal['id']}/plan",
        headers=headers,
    )
    assert current.status_code == 200, current.text
    current_plan = current.json()
    assert current_plan["id"] == applied["applied_plan_ref"]
    assert current_plan["version"] == 2
    assert current_plan["status"] == "approved"
    assert any(task["status"] == "completed" for task in current_plan["tasks"])

    with session_factory() as db:
        plans = list(
            db.scalars(
                select(LearningPlan)
                .where(LearningPlan.goal_id == uuid.UUID(goal["id"]))
                .order_by(LearningPlan.version)
            )
        )
        assert [plan.status for plan in plans] == ["superseded", "approved"]
        context = db.scalar(
            select(ExecutionContext).where(
                ExecutionContext.goal_id == uuid.UUID(goal["id"])
            )
        )
        assert context is not None
        assert context.plan_ref == applied["applied_plan_ref"]
        assert context.plan_version == 2
        assert context.completed_task_count == 1
