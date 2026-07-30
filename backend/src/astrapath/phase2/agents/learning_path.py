import uuid
from typing import Any

from pydantic import BaseModel

from astrapath.enums import AgentRunStatus
from astrapath.phase2.contracts import (
    AgentContext,
    AgentIdentity,
    AgentResult,
    ClarifiedGoal,
    CompetencyGap,
    DecisionCardData,
)
from astrapath.phase2.repository import topological_order


class LearningPathAgentInput(BaseModel):
    clarified_goal: ClarifiedGoal
    requirements: list[dict[str, Any]]
    gaps: list[CompetencyGap]
    competency_ids: dict[str, uuid.UUID]


class LearningPathArchitectAgent:
    name = "learning-path-architect-agent"
    version = "2.0.0"
    identity = AgentIdentity(
        agent_id="agent-5",
        agent_name=name,
        version=version,
        deployment="phase2-rules",
    )
    allowed_tools: frozenset[str] = frozenset()

    async def execute(
        self, context: AgentContext, input_data: LearningPathAgentInput
    ) -> AgentResult:
        order = topological_order(input_data.requirements)
        requirement_map = {
            item["competency_slug"]: item for item in input_data.requirements
        }
        gap_map = {item.slug: item for item in input_data.gaps}
        node_specs: list[dict[str, Any]] = []
        edge_specs: list[dict[str, str]] = []
        total_hours = 0.0

        for sequence, slug in enumerate(order):
            requirement = requirement_map[slug]
            gap = gap_map[slug]
            gap_fraction = gap.gap / max(1, gap.required_level)
            estimated_hours = round(
                float(requirement["estimated_hours"]) * gap_fraction, 1
            )
            total_hours += estimated_hours
            node_specs.append(
                {
                    "key": slug,
                    "competency_id": input_data.competency_ids[slug],
                    "node_type": "competency",
                    "title": gap.name,
                    "required_level": gap.required_level,
                    "current_level": gap.current_level,
                    "estimated_hours": estimated_hours,
                    "sequence_order": sequence,
                    "is_optional": not requirement["required"],
                    "metadata": {
                        "slug": slug,
                        "classification": gap.classification,
                        "evidence_refs": gap.evidence_refs,
                    },
                }
            )
            for prerequisite in requirement["prerequisite_slugs"]:
                edge_specs.append(
                    {
                        "source": prerequisite,
                        "target": slug,
                        "relationship_type": "prerequisite",
                        "reason": (
                            f"{gap_map[prerequisite].name} supports "
                            f"{gap.name}"
                        ),
                    }
                )

        outcome_key = "__goal_outcome__"
        node_specs.append(
            {
                "key": outcome_key,
                "competency_id": None,
                "node_type": "outcome",
                "title": input_data.clarified_goal.measurable_outcome,
                "required_level": None,
                "current_level": None,
                "estimated_hours": 0.0,
                "sequence_order": len(order),
                "is_optional": False,
                "metadata": {
                    "success_criteria": input_data.clarified_goal.success_criteria
                },
            }
        )
        prerequisite_slugs = {
            prerequisite
            for requirement in input_data.requirements
            for prerequisite in requirement["prerequisite_slugs"]
        }
        terminal_slugs = [
            slug
            for slug in order
            if slug not in prerequisite_slugs and requirement_map[slug]["required"]
        ]
        for slug in terminal_slugs:
            edge_specs.append(
                {
                    "source": slug,
                    "target": outcome_key,
                    "relationship_type": "contributes_to",
                    "reason": (
                        f"{gap_map[slug].name} provides evidence for the goal outcome"
                    ),
                }
            )

        core_path = [
            slug
            for slug in order
            if requirement_map[slug]["required"] and gap_map[slug].gap > 0
        ]
        optional_branches = [
            slug
            for slug in order
            if not requirement_map[slug]["required"] and gap_map[slug].gap > 0
        ]
        duration = round(
            total_hours / max(input_data.clarified_goal.weekly_hours, 0.5), 1
        )
        cards: list[DecisionCardData] = []
        if optional_branches:
            cards.append(
                DecisionCardData(
                    decision_type="learning_path",
                    decision="Keep advanced breadth topics as an optional branch",
                    reasons=[
                        (
                            "The core outcome can be demonstrated without completing "
                            "every advanced topic"
                        )
                    ],
                    evidence=[f"goal:{context.goal_id}", "template_optional_requirements"],
                    alternatives=["Include the optional branch and extend the expected duration"],
                    approval_required=False,
                    agent_name=self.name,
                )
            )
        data = {
            "node_specs": node_specs,
            "edge_specs": edge_specs,
            "core_path": core_path,
            "optional_branches": optional_branches,
            "estimated_duration_weeks": duration,
            "decision_cards": [card.model_dump(mode="json") for card in cards],
        }
        return AgentResult(
            agent=self.identity,
            status=AgentRunStatus.COMPLETED,
            confidence=0.9,
            summary=(
                f"Created a {len(core_path)}-step core path "
                f"with {len(optional_branches)} optional branches"
            ),
            data=data,
            evidence_refs=[f"skill_gap:{context.goal_id}", "template_prerequisites"],
            next_actions=core_path,
            user_visible_explanation=(
                "The path orders prerequisite competencies before the skills that "
                "depend on them and ends at the measurable goal outcome."
            ),
        )
