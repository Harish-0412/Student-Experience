import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from astrapath.agents.contracts import (
    AgentBudget,
    AgentContext,
    AgentIdentity,
    AgentResult,
    StatePatch,
)

__all__ = [
    "AgentBudget",
    "AgentContext",
    "AgentIdentity",
    "AgentResult",
    "StatePatch",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class FeasibilityCategory(StrEnum):
    FEASIBLE = "feasible"
    FEASIBLE_WITH_CONSTRAINTS = "feasible_with_constraints"
    CHALLENGING_BUT_POSSIBLE = "challenging_but_possible"
    UNLIKELY_UNDER_CURRENT_CONDITIONS = "unlikely_under_current_conditions"
    INSUFFICIENT_INFORMATION = "insufficient_information"
    REQUIRES_HUMAN_REVIEW = "requires_human_review"


class DecisionCardData(ContractModel):
    id: uuid.UUID | None = None
    decision_type: str
    decision: str
    reasons: list[str]
    evidence: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    approval_required: bool = False
    status: Literal["proposed", "accepted", "rejected", "superseded"] = "proposed"
    agent_name: str


class GoalClarificationRequest(ContractModel):
    raw_goal: str | None = Field(default=None, min_length=5, max_length=4000)
    desired_outcome: str | None = Field(default=None, min_length=3, max_length=500)
    target_date: date | None = None
    target_level: int | None = Field(default=None, ge=1, le=5)
    weekly_hours: float | None = Field(default=None, ge=0.5, le=80)
    constraints: list[str] = Field(default_factory=list, max_length=20)
    template_slug: str | None = Field(default=None, min_length=2, max_length=80)

    @field_validator("constraints")
    @classmethod
    def clean_constraints(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if any(len(item) > 300 for item in cleaned):
            raise ValueError("Constraints must not exceed 300 characters")
        return list(dict.fromkeys(cleaned))


class ClarifiedGoal(ContractModel):
    goal_id: uuid.UUID
    measurable_outcome: str
    category: str
    target_level: int = Field(ge=1, le=5)
    target_date: date
    weekly_hours: float = Field(gt=0)
    constraints: list[str]
    success_criteria: list[str]
    template_slug: str
    assumptions: list[str]
    clarification_questions: list[str]
    confidence: float = Field(ge=0, le=1)


class GoalClarificationResult(ContractModel):
    clarified_goal: ClarifiedGoal
    decision_cards: list[DecisionCardData]


class FeasibilityRequest(ContractModel):
    weekly_hours: float | None = Field(default=None, ge=0, le=80)
    target_date: date | None = None
    existing_commitment_hours_per_week: float = Field(default=0, ge=0, le=80)
    excluded_competencies: list[str] = Field(default_factory=list, max_length=30)


class EffortRange(ContractModel):
    minimum: float = Field(ge=0)
    expected: float = Field(ge=0)
    maximum: float = Field(ge=0)


class FeasibilityResult(ContractModel):
    category: FeasibilityCategory
    estimated_effort_hours: EffortRange
    available_hours: float = Field(ge=0)
    weekly_capacity_hours: float = Field(ge=0)
    weeks_available: float = Field(ge=0)
    major_risks: list[str]
    recommended_adjustments: list[str]
    scenario_options: list[str]
    confidence: float = Field(ge=0, le=1)
    assumptions: list[str]
    decision_cards: list[DecisionCardData]


class StudentCompetencyInput(ContractModel):
    competency_slug: str = Field(min_length=2, max_length=100)
    proficiency_level: int = Field(ge=0, le=5)
    confidence: float = Field(default=0.6, ge=0, le=1)
    source: Literal["self_reported", "diagnostic", "course", "project", "mentor"] = (
        "self_reported"
    )
    evidence_refs: list[str] = Field(default_factory=list, max_length=20)


class SkillGapRequest(ContractModel):
    competency_evidence: list[StudentCompetencyInput] = Field(
        default_factory=list, max_length=100
    )

    @model_validator(mode="after")
    def unique_competencies(self) -> Self:
        slugs = [item.competency_slug for item in self.competency_evidence]
        if len(slugs) != len(set(slugs)):
            raise ValueError("Each competency may be supplied only once")
        return self


class CompetencyGap(ContractModel):
    competency_id: uuid.UUID
    slug: str
    name: str
    required_level: int = Field(ge=0, le=5)
    current_level: int = Field(ge=0, le=5)
    gap: int = Field(ge=0, le=5)
    confidence: float = Field(ge=0, le=1)
    classification: Literal["verified", "developing", "missing", "uncertain"]
    evidence_refs: list[str]
    priority: int = Field(ge=1)
    required: bool


class SkillGapResult(ContractModel):
    required_competencies: list[CompetencyGap]
    verified_competencies: list[CompetencyGap]
    developing_competencies: list[CompetencyGap]
    missing_competencies: list[CompetencyGap]
    uncertain_competencies: list[CompetencyGap]
    recommended_diagnostics: list[str]
    gap_priority: list[str]
    decision_cards: list[DecisionCardData]


class GraphNodeRead(ContractModel):
    id: uuid.UUID
    competency_id: uuid.UUID | None
    node_type: str
    title: str
    required_level: int | None
    current_level: int | None
    estimated_hours: float
    sequence_order: int
    is_optional: bool
    metadata: dict[str, Any]


class GraphEdgeRead(ContractModel):
    id: uuid.UUID
    source_node_id: uuid.UUID
    target_node_id: uuid.UUID
    relationship_type: str
    reason: str


class GoalGraphResult(ContractModel):
    goal_id: uuid.UUID
    nodes: list[GraphNodeRead]
    edges: list[GraphEdgeRead]
    core_path: list[str]
    optional_branches: list[str]
    estimated_duration_weeks: float
    decision_cards: list[DecisionCardData]


class SkillGapWorkflowResult(ContractModel):
    skill_gap: SkillGapResult
    graph: GoalGraphResult


class GoalCompetenciesResult(ContractModel):
    goal_id: uuid.UUID
    template_slug: str
    competencies: list[CompetencyGap]


class CompetencyCreate(ContractModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    name: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=3, max_length=2000)
    category: str = Field(min_length=2, max_length=80)
    prerequisite_slugs: list[str] = Field(default_factory=list, max_length=30)
    active: bool = True


class CompetencyUpdate(ContractModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, min_length=3, max_length=2000)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    prerequisite_slugs: list[str] | None = Field(default=None, max_length=30)
    active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("At least one competency field must be supplied")
        return self


class CompetencyRead(CompetencyCreate):
    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class TemplateRequirement(ContractModel):
    competency_slug: str = Field(min_length=2, max_length=100)
    target_level: int = Field(ge=1, le=5)
    estimated_hours: float = Field(gt=0, le=1000)
    required: bool = True
    prerequisite_slugs: list[str] = Field(default_factory=list, max_length=30)


class GoalTemplateCreate(ContractModel):
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=100)
    name: str = Field(min_length=3, max_length=160)
    description: str = Field(min_length=3, max_length=2000)
    category: str = Field(min_length=2, max_length=80)
    matching_terms: list[str] = Field(min_length=1, max_length=50)
    default_duration_weeks: int = Field(ge=1, le=260)
    default_target_level: int = Field(default=3, ge=1, le=5)
    measurable_outcome: str = Field(min_length=5, max_length=500)
    success_criteria: list[str] = Field(min_length=1, max_length=20)
    requirements: list[TemplateRequirement] = Field(min_length=1, max_length=100)
    active: bool = True


class GoalTemplateRead(GoalTemplateCreate):
    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime
