import math
from datetime import date
from typing import Any

from pydantic import BaseModel, Field

from astrapath.enums import AgentRunStatus
from astrapath.phase2.contracts import (
    AgentContext,
    AgentIdentity,
    AgentResult,
    ClarifiedGoal,
    DecisionCardData,
    EffortRange,
    FeasibilityCategory,
    FeasibilityRequest,
    FeasibilityResult,
)


class FeasibilityAgentInput(BaseModel):
    clarified_goal: ClarifiedGoal
    requirements: list[dict[str, Any]]
    current_levels: dict[str, int] = Field(default_factory=dict)
    request: FeasibilityRequest


class GoalFeasibilityAgent:
    name = "goal-feasibility-agent"
    version = "2.0.0"
    identity = AgentIdentity(
        agent_id="agent-3",
        agent_name=name,
        version=version,
        deployment="phase2-rules",
    )
    allowed_tools: frozenset[str] = frozenset()

    async def execute(
        self, context: AgentContext, input_data: FeasibilityAgentInput
    ) -> AgentResult:
        clarified = input_data.clarified_goal
        request = input_data.request
        target_date = request.target_date or clarified.target_date
        weekly_hours = (
            request.weekly_hours
            if request.weekly_hours is not None
            else clarified.weekly_hours
        )
        weekly_capacity = max(
            0.0, weekly_hours - request.existing_commitment_hours_per_week
        )
        weeks = max(0.0, (target_date - date.today()).days / 7)
        available = round(weeks * weekly_capacity, 1)

        excluded = set(request.excluded_competencies)
        expected = 0.0
        optional_remaining = 0.0
        prerequisite_burden = 0
        assumptions = [
            "Effort is a planning range, not a completion guarantee",
            "Weekly availability is assumed to remain reasonably consistent",
        ]
        for requirement in input_data.requirements:
            slug = requirement["competency_slug"]
            if slug in excluded:
                continue
            target = requirement["target_level"]
            current = input_data.current_levels.get(slug, 0)
            gap_fraction = max(0.0, (target - current) / target)
            remaining = float(requirement["estimated_hours"]) * gap_fraction
            expected += remaining
            if not requirement["required"]:
                optional_remaining += remaining
            if requirement["required"] and current == 0 and requirement["prerequisite_slugs"]:
                prerequisite_burden += 1

        effort = EffortRange(
            minimum=round(expected * 0.8, 1),
            expected=round(expected, 1),
            maximum=round(expected * 1.3, 1),
        )
        category = self._category(expected, available, weeks, weekly_capacity)
        risks: list[str] = []
        adjustments: list[str] = []
        scenarios: list[str] = []

        if weeks < 2:
            risks.append("The target date leaves less than two weeks for learning and review")
        if weekly_capacity == 0:
            risks.append("Existing commitments use all declared weekly learning time")
        if prerequisite_burden >= 3:
            risks.append(
                f"{prerequisite_burden} required topics have unstarted prerequisites"
            )
        if available < effort.expected:
            shortfall = effort.expected - available
            if weeks > 0:
                extra_weekly = math.ceil(shortfall / weeks * 2) / 2
                adjustments.append(
                    f"Add about {extra_weekly:g} focused hours per week"
                )
                scenarios.append(
                    f"Keep the deadline and increase weekly effort by {extra_weekly:g} hours"
                )
            if weekly_capacity > 0:
                extension = math.ceil(shortfall / weekly_capacity)
                adjustments.append(f"Extend the target by about {extension} weeks")
                scenarios.append(
                    f"Keep weekly effort and extend the deadline by about {extension} weeks"
                )
            if optional_remaining:
                adjustments.append(
                    f"Defer up to {round(optional_remaining, 1):g} hours of optional material"
                )
                scenarios.append("Reduce optional outcomes and preserve the core path")
        else:
            scenarios.extend(
                [
                    "Keep the current scope and reserve remaining capacity for review",
                    "Use spare capacity for an optional project or additional practice",
                ]
            )
        if not adjustments:
            adjustments.append("Keep the current scope and review progress each week")

        cards: list[DecisionCardData] = []
        if category != FeasibilityCategory.FEASIBLE:
            cards.append(
                DecisionCardData(
                    decision_type="feasibility",
                    decision=(
                        f"Treat the goal as {category.value.replace('_', ' ')} "
                        "under the current time constraints"
                    ),
                    reasons=[
                        f"Expected remaining effort is about {effort.expected:g} hours",
                        f"Declared capacity provides about {available:g} hours",
                    ],
                    evidence=[
                        f"goal:{context.goal_id}",
                        "student_weekly_capacity",
                        "template_effort_model",
                    ],
                    alternatives=scenarios,
                    approval_required=category
                    in {
                        FeasibilityCategory.CHALLENGING_BUT_POSSIBLE,
                        FeasibilityCategory.UNLIKELY_UNDER_CURRENT_CONDITIONS,
                    },
                    agent_name=self.name,
                )
            )

        confidence = 0.86
        if not input_data.current_levels:
            confidence -= 0.12
            assumptions.append("No competency evidence was available before feasibility analysis")
        if clarified.assumptions:
            confidence -= 0.06
        result = FeasibilityResult(
            category=category,
            estimated_effort_hours=effort,
            available_hours=available,
            weekly_capacity_hours=round(weekly_capacity, 1),
            weeks_available=round(weeks, 1),
            major_risks=risks,
            recommended_adjustments=adjustments,
            scenario_options=list(dict.fromkeys(scenarios)),
            confidence=max(0.5, round(confidence, 2)),
            assumptions=assumptions,
            decision_cards=cards,
        )
        return AgentResult(
            agent=self.identity,
            status=(
                AgentRunStatus.STUDENT_APPROVAL_REQUIRED
                if any(card.approval_required for card in cards)
                else AgentRunStatus.COMPLETED
            ),
            confidence=result.confidence,
            summary=f"Goal feasibility is {category.value.replace('_', ' ')}",
            data=result.model_dump(mode="json"),
            assumptions=result.assumptions,
            evidence_refs=[f"goal:{context.goal_id}", "template_effort_model"],
            warnings=risks,
            next_actions=result.scenario_options,
            user_visible_explanation=(
                f"The plan needs about {effort.expected:g} hours and currently has "
                f"about {available:g} hours available."
            ),
        )

    @staticmethod
    def _category(
        expected: float, available: float, weeks: float, weekly_capacity: float
    ) -> FeasibilityCategory:
        if weeks <= 0 or weekly_capacity <= 0:
            return FeasibilityCategory.UNLIKELY_UNDER_CURRENT_CONDITIONS
        if expected <= 0:
            return FeasibilityCategory.FEASIBLE
        ratio = available / expected
        if ratio >= 1.2:
            return FeasibilityCategory.FEASIBLE
        if ratio >= 1.0:
            return FeasibilityCategory.FEASIBLE_WITH_CONSTRAINTS
        if ratio >= 0.65:
            return FeasibilityCategory.CHALLENGING_BUT_POSSIBLE
        return FeasibilityCategory.UNLIKELY_UNDER_CURRENT_CONDITIONS
