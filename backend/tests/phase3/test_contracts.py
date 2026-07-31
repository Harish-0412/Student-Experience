import asyncio
import uuid
from datetime import UTC, date, datetime, time

from astrapath.agents.contracts import AgentContext
from astrapath.agents.registry import AgentRegistry
from astrapath.enums import Role
from astrapath.phase3.agents import (
    DailyActionPlanningAgent,
    MilestoneDecompositionAgent,
    ScheduleTimeBudgetAgent,
)
from astrapath.phase3.agents.schedule import ScheduleTimeBudgetInput
from astrapath.phase3.contracts import (
    AvailabilityWindow,
    SchedulingConstraints,
    TaskSpec,
)
from astrapath.phase3.models import (
    LearningPlan,
    Milestone,
    PlanDecision,
    Schedule,
    ScheduleBlock,
    Task,
)


def test_phase3_agents_use_frozen_agent_registry_contract() -> None:
    registry = AgentRegistry(
        [
            MilestoneDecompositionAgent(),
            ScheduleTimeBudgetAgent(),
            DailyActionPlanningAgent(),
        ]
    )
    assert [item["name"] for item in registry.list()] == [
        "daily-action-planning-agent",
        "milestone-decomposition-agent",
        "schedule-time-budget-agent",
    ]


def test_phase3_source_of_truth_tables_are_named() -> None:
    assert {
        LearningPlan.__tablename__,
        Milestone.__tablename__,
        Task.__tablename__,
        Schedule.__tablename__,
        ScheduleBlock.__tablename__,
        PlanDecision.__tablename__,
    } == {
        "learning_plans",
        "milestones",
        "tasks",
        "schedules",
        "schedule_blocks",
        "plan_decisions",
    }


def test_scheduler_reuses_the_remainder_of_a_study_window() -> None:
    identifier = uuid.uuid4()
    context = AgentContext(
        workflow_id=uuid.uuid4(),
        correlation_id="slot-reuse-test",
        actor_id=identifier,
        actor_role=Role.STUDENT,
        student_id=identifier,
        goal_id=uuid.uuid4(),
        policy_version="phase3-test",
        request_time=datetime.now(UTC),
    )
    target = date(2026, 8, 3)
    payload = ScheduleTimeBudgetInput(
        timezone="Asia/Kolkata",
        starts_on=target,
        target_date=target,
        weekly_budget_minutes=120,
        tasks=[
            TaskSpec(
                key="task-one",
                milestone_key="milestone",
                competency_id=None,
                title="First task",
                description="Use the first part of the window",
                task_type="learn",
                priority=3,
                estimated_minutes=25,
                evidence_required=False,
                evidence_description=None,
                sequence_number=1,
                due_date=target,
            ),
            TaskSpec(
                key="task-two",
                milestone_key="milestone",
                competency_id=None,
                title="Second task",
                description="Use the remaining part of the window",
                task_type="practice",
                priority=3,
                estimated_minutes=35,
                evidence_required=False,
                evidence_description=None,
                sequence_number=2,
                due_date=target,
            ),
        ],
        availability={
            "monday": [
                AvailabilityWindow(
                    start=time(18, 0),
                    end=time(19, 0),
                    energy="high",
                )
            ]
        },
        constraints=SchedulingConstraints(buffer_ratio=0.05),
    )

    result = asyncio.run(ScheduleTimeBudgetAgent().execute(context, payload))

    assert result.data["allocated_minutes"] == 60
    assert result.data["conflicts"] == []
    assert len(result.data["blocks"]) == 2
    assert result.data["blocks"][0]["ends_at"] == result.data["blocks"][1]["starts_at"]
