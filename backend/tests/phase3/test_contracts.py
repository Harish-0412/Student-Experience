from astrapath.agents.registry import AgentRegistry
from astrapath.phase3.agents import (
    DailyActionPlanningAgent,
    MilestoneDecompositionAgent,
    ScheduleTimeBudgetAgent,
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
