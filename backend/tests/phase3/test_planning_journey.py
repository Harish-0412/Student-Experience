from datetime import datetime, timedelta

from sqlalchemy import select

from astrapath.models import AuditLog

from .conftest import complete_phase2, create_goal

CALCULUS_EVIDENCE = [
    {
        "competency_slug": "algebra-functions",
        "proficiency_level": 3,
        "confidence": 0.95,
        "source": "diagnostic",
    },
    {
        "competency_slug": "limits-continuity",
        "proficiency_level": 3,
        "confidence": 0.9,
        "source": "diagnostic",
    },
    {
        "competency_slug": "derivatives",
        "proficiency_level": 3,
        "confidence": 0.9,
        "source": "course",
    },
    {
        "competency_slug": "integrals",
        "proficiency_level": 2,
        "confidence": 0.85,
        "source": "diagnostic",
    },
]


def test_complete_plan_edit_approve_calendar_and_daily_journey(
    client,
    planning_student,
    session_factory,
) -> None:
    headers = planning_student["headers"]
    goal = create_goal(
        client,
        headers,
        title="Calculus exam",
        raw_statement="Prepare for my calculus exam",
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
    plan = generated.json()
    assert plan["status"] == "proposed"
    assert plan["milestones"]
    assert plan["tasks"]
    assert plan["schedule"]["blocks"]
    assert not [
        item
        for item in plan["schedule"]["conflicts"]
        if item["severity"] == "blocking"
    ]
    assert plan["schedule"]["buffer_minutes"] > 0

    blocks = sorted(
        plan["schedule"]["blocks"], key=lambda item: item["starts_at"]
    )
    assert all(
        datetime.fromisoformat(left["ends_at"])
        <= datetime.fromisoformat(right["starts_at"])
        for left, right in zip(blocks, blocks[1:], strict=False)
    )

    first_task = plan["tasks"][0]
    edited_minutes = max(15, first_task["estimated_minutes"] - 15)
    edited = client.patch(
        f"/api/v1/goals/{goal['id']}/plan/tasks/{first_task['id']}",
        headers=headers,
        json={
            "estimated_minutes": edited_minutes,
            "reason": "Prior course work reduced the required review time",
        },
    )
    assert edited.status_code == 200, edited.text
    edited_plan = edited.json()
    edited_task = next(
        item for item in edited_plan["tasks"] if item["id"] == first_task["id"]
    )
    assert edited_task["estimated_minutes"] == edited_minutes
    scheduled_tasks = [
        item for item in edited_plan["tasks"] if item["scheduled_start"]
    ]
    assert all(
        datetime.fromisoformat(left["scheduled_end"])
        <= datetime.fromisoformat(right["scheduled_start"])
        for left, right in zip(
            scheduled_tasks, scheduled_tasks[1:], strict=False
        )
    )

    approved = client.post(
        f"/api/v1/goals/{goal['id']}/plan/decision",
        headers=headers,
        json={"decision": "approve", "reason": "The schedule fits my semester"},
    )
    assert approved.status_code == 200, approved.text
    approved_plan = approved.json()
    assert approved_plan["status"] == "approved"
    assert approved_plan["schedule"]["status"] == "approved"

    first_date = datetime.fromisoformat(
        approved_plan["schedule"]["blocks"][0]["starts_at"]
    ).date()
    calendar = client.get(
        f"/api/v1/goals/{goal['id']}/calendar",
        headers=headers,
        params={
            "starts_on": first_date.isoformat(),
            "ends_on": (first_date + timedelta(days=6)).isoformat(),
        },
    )
    assert calendar.status_code == 200, calendar.text
    assert calendar.json()["blocks"]

    daily = client.get(
        "/api/v1/student/daily-plan",
        headers=headers,
        params={"date": first_date.isoformat()},
    )
    assert daily.status_code == 200, daily.text
    assert daily.json()["daily_plan"]
    assert daily.json()["minimum_viable_day"]

    with session_factory() as db:
        approval_log = db.scalar(
            select(AuditLog).where(
                AuditLog.action == "phase3.plan_approved",
                AuditLog.resource_id == approved_plan["id"],
            )
        )
        assert approval_log is not None


def test_student_can_reject_proposed_plan(client, planning_student) -> None:
    headers = planning_student["headers"]
    goal = create_goal(
        client,
        headers,
        title="Calculus exam rejection",
        raw_statement="Prepare for another calculus exam",
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
    rejected = client.post(
        f"/api/v1/goals/{goal['id']}/plan/decision",
        headers=headers,
        json={
            "decision": "reject",
            "reason": "I need a different study approach",
        },
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["schedule"]["status"] == "rejected"


def test_conflicting_deadlines_and_limited_availability_do_not_overlap(
    client,
    planning_student,
) -> None:
    headers = planning_student["headers"]
    first_goal = create_goal(
        client,
        headers,
        title="Calculus deadline",
        raw_statement="Prepare for a calculus exam",
        weeks=4,
    )
    complete_phase2(
        client,
        headers,
        first_goal["id"],
        template_slug="calculus-exam",
        weekly_hours=2,
        evidence=[
            *CALCULUS_EVIDENCE[:3],
            {
                "competency_slug": "integrals",
                "proficiency_level": 3,
                "confidence": 0.9,
                "source": "diagnostic",
            },
            {
                "competency_slug": "calculus-exam-practice",
                "proficiency_level": 2,
                "confidence": 0.8,
                "source": "diagnostic",
            },
        ],
    )
    limited_constraints = {
        "availability": {
            "tuesday": [
                {"start": "18:00", "end": "19:00", "energy": "high"}
            ],
            "thursday": [
                {"start": "18:00", "end": "19:00", "energy": "high"}
            ],
        },
        "max_session_minutes": 60,
        "minimum_break_minutes": 15,
        "max_daily_minutes": 60,
        "buffer_ratio": 0.15,
    }
    first_plan_response = client.post(
        f"/api/v1/goals/{first_goal['id']}/plan",
        headers=headers,
        json={"constraints": limited_constraints},
    )
    assert first_plan_response.status_code == 201, first_plan_response.text
    first_plan = first_plan_response.json()
    assert first_plan["schedule"]["blocks"]

    second_goal = create_goal(
        client,
        headers,
        title="DSA interview deadline",
        raw_statement="Prepare for a data structures coding interview",
        weeks=4,
    )
    complete_phase2(
        client,
        headers,
        second_goal["id"],
        template_slug="data-structures-interview",
        weekly_hours=2,
        evidence=[
            {
                "competency_slug": "programming-problem-solving",
                "proficiency_level": 3,
                "confidence": 0.9,
                "source": "course",
            },
            {
                "competency_slug": "complexity-analysis",
                "proficiency_level": 3,
                "confidence": 0.9,
                "source": "course",
            },
            {
                "competency_slug": "arrays-hash-maps",
                "proficiency_level": 3,
                "confidence": 0.9,
                "source": "diagnostic",
            },
            {
                "competency_slug": "recursion-trees",
                "proficiency_level": 3,
                "confidence": 0.9,
                "source": "diagnostic",
            },
            {
                "competency_slug": "graphs-dynamic-programming",
                "proficiency_level": 2,
                "confidence": 0.85,
                "source": "diagnostic",
            },
            {
                "competency_slug": "technical-interview-practice",
                "proficiency_level": 2,
                "confidence": 0.8,
                "source": "diagnostic",
            },
        ],
    )
    second_plan_response = client.post(
        f"/api/v1/goals/{second_goal['id']}/plan",
        headers=headers,
        json={"constraints": limited_constraints},
    )
    assert second_plan_response.status_code == 201, second_plan_response.text
    second_plan = second_plan_response.json()
    conflict_codes = {
        item["code"] for item in second_plan["schedule"]["conflicts"]
    }
    assert "deadline_capacity_shortfall" in conflict_codes
    assert "cross_goal_deadline_conflict" in conflict_codes

    first_intervals = [
        (
            datetime.fromisoformat(item["starts_at"]),
            datetime.fromisoformat(item["ends_at"]),
        )
        for item in first_plan["schedule"]["blocks"]
    ]
    second_intervals = [
        (
            datetime.fromisoformat(item["starts_at"]),
            datetime.fromisoformat(item["ends_at"]),
        )
        for item in second_plan["schedule"]["blocks"]
    ]
    assert all(
        first_end <= second_start or second_end <= first_start
        for first_start, first_end in first_intervals
        for second_start, second_end in second_intervals
    )

    approval = client.post(
        f"/api/v1/goals/{second_goal['id']}/plan/decision",
        headers=headers,
        json={"decision": "approve", "reason": "Try to approve conflicting plan"},
    )
    assert approval.status_code == 409
    assert approval.json()["error"]["code"] == (
        "schedule_conflicts_require_resolution"
    )
