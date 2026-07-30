import uuid
from typing import Any

from pydantic import BaseModel, Field

from astrapath.enums import AgentRunStatus
from astrapath.phase2.contracts import (
    AgentContext,
    AgentIdentity,
    AgentResult,
    CompetencyGap,
    DecisionCardData,
    SkillGapResult,
)
from astrapath.phase2.repository import topological_order


class SkillGapAgentInput(BaseModel):
    requirements: list[dict[str, Any]]
    competencies: dict[str, dict[str, Any]]
    student_levels: dict[str, dict[str, Any]] = Field(default_factory=dict)


class SkillGapAnalysisAgent:
    name = "skill-gap-analysis-agent"
    version = "2.0.0"
    identity = AgentIdentity(
        agent_id="agent-4",
        agent_name=name,
        version=version,
        deployment="phase2-rules",
    )
    allowed_tools: frozenset[str] = frozenset()

    async def execute(
        self, context: AgentContext, input_data: SkillGapAgentInput
    ) -> AgentResult:
        order = topological_order(input_data.requirements)
        priority_by_slug = {slug: index + 1 for index, slug in enumerate(order)}
        gaps: list[CompetencyGap] = []

        for requirement in input_data.requirements:
            slug = requirement["competency_slug"]
            competency = input_data.competencies[slug]
            evidence = input_data.student_levels.get(slug, {})
            current = int(evidence.get("proficiency_level", 0))
            confidence = float(evidence.get("confidence", 0.35 if current == 0 else 0.5))
            target = int(requirement["target_level"])
            gap = max(0, target - current)
            if confidence < 0.6 and current > 0:
                classification = "uncertain"
            elif gap == 0:
                classification = "verified"
            elif current == 0:
                classification = "missing"
            else:
                classification = "developing"
            evidence_refs = list(evidence.get("evidence_refs", []))
            if not evidence_refs:
                evidence_refs = [f"skill_gap:{context.goal_id}:{slug}"]
            gaps.append(
                CompetencyGap(
                    competency_id=uuid.UUID(str(competency["id"])),
                    slug=slug,
                    name=competency["name"],
                    required_level=target,
                    current_level=current,
                    gap=gap,
                    confidence=confidence,
                    classification=classification,
                    evidence_refs=evidence_refs,
                    priority=priority_by_slug[slug],
                    required=bool(requirement["required"]),
                )
            )

        by_slug = {item.slug: item for item in gaps}
        cards: list[DecisionCardData] = []
        for requirement in input_data.requirements:
            child = by_slug[requirement["competency_slug"]]
            if child.gap == 0:
                continue
            for prerequisite_slug in requirement["prerequisite_slugs"]:
                prerequisite = by_slug[prerequisite_slug]
                if prerequisite.gap == 0:
                    continue
                cards.append(
                    DecisionCardData(
                        decision_type="learning_path",
                        decision=f"Study {prerequisite.name} before {child.name}",
                        reasons=[
                            (
                                f"{prerequisite.name} is required before independent "
                                f"application of {child.name}"
                            )
                        ],
                        evidence=[
                            prerequisite.evidence_refs[0],
                            child.evidence_refs[0],
                        ],
                        alternatives=[
                            (
                                f"Start {child.name} now with an added "
                                f"{prerequisite.name} revision block"
                            )
                        ],
                        approval_required=True,
                        agent_name=self.name,
                    )
                )

        verified = [item for item in gaps if item.classification == "verified"]
        developing = [item for item in gaps if item.classification == "developing"]
        missing = [item for item in gaps if item.classification == "missing"]
        uncertain = [item for item in gaps if item.classification == "uncertain"]
        diagnostics = [
            f"Complete a short diagnostic for {item.name}"
            for item in uncertain
        ]
        result = SkillGapResult(
            required_competencies=sorted(gaps, key=lambda item: item.priority),
            verified_competencies=verified,
            developing_competencies=developing,
            missing_competencies=missing,
            uncertain_competencies=uncertain,
            recommended_diagnostics=diagnostics,
            gap_priority=[
                item.slug
                for item in sorted(gaps, key=lambda item: item.priority)
                if item.gap > 0
            ],
            decision_cards=cards,
        )
        confidence = 0.88 if input_data.student_levels else 0.68
        return AgentResult(
            agent=self.identity,
            status=(
                AgentRunStatus.STUDENT_APPROVAL_REQUIRED
                if cards
                else AgentRunStatus.COMPLETED
            ),
            confidence=confidence,
            summary=(
                f"Found {len(missing)} missing, {len(developing)} developing, "
                f"and {len(uncertain)} uncertain competencies"
            ),
            data=result.model_dump(mode="json"),
            assumptions=(
                []
                if input_data.student_levels
                else ["Unreported competencies were treated as not yet introduced"]
            ),
            evidence_refs=[
                reference
                for gap in gaps
                for reference in gap.evidence_refs
            ],
            next_actions=result.gap_priority,
            user_visible_explanation=(
                "The gap list separates demonstrated skills from skills that need "
                "development or a diagnostic check."
            ),
        )
