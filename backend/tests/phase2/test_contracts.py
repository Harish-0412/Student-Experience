from astrapath.agents.registry import AgentRegistry
from astrapath.phase2.agents import (
    GoalFeasibilityAgent,
    LearningPathArchitectAgent,
    SkillGapAnalysisAgent,
)
from astrapath.phase2.models import (
    Competency,
    DecisionCard,
    GoalGraphEdge,
    GoalGraphNode,
    GoalTemplate,
    StudentCompetency,
)


def test_phase2_agents_satisfy_frozen_registry_contract() -> None:
    registry = AgentRegistry(
        [
            GoalFeasibilityAgent(),
            SkillGapAnalysisAgent(),
            LearningPathArchitectAgent(),
        ]
    )

    assert [item["name"] for item in registry.list()] == [
        "goal-feasibility-agent",
        "learning-path-architect-agent",
        "skill-gap-analysis-agent",
    ]


def test_required_phase2_table_contracts_are_named() -> None:
    assert {
        Competency.__tablename__,
        StudentCompetency.__tablename__,
        GoalTemplate.__tablename__,
        GoalGraphNode.__tablename__,
        GoalGraphEdge.__tablename__,
        DecisionCard.__tablename__,
    } == {
        "competencies",
        "student_competencies",
        "goal_templates",
        "goal_graph_nodes",
        "goal_graph_edges",
        "decision_cards",
    }
