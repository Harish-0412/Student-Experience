import uuid
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from astrapath.phase4.enums import (
    AcademicIntegrityMode,
    AgentExecutionStatus,
    AssessmentStatus,
    AttemptStatus,
    EvidenceStatus,
    FocusSessionStatus,
    ReplanStatus,
    ResourceStatus,
    RiskSeverity,
    RiskStatus,
    TutorMode,
)


class Phase4Model(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
    )


class AgentOutput(Phase4Model):
    status: AgentExecutionStatus = AgentExecutionStatus.COMPLETED
    confidence: float = Field(ge=0, le=1)
    assumptions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ExecutionContextSync(Phase4Model):
    plan_ref: str | None = Field(default=None, max_length=120)
    plan_version: int | None = Field(default=None, ge=1)
    planned_task_count: int = Field(default=0, ge=0, le=10000)
    completed_task_count: int = Field(default=0, ge=0, le=10000)
    planned_milestone_count: int = Field(default=0, ge=0, le=1000)
    completed_milestone_count: int = Field(default=0, ge=0, le=1000)
    planned_weekly_minutes: int = Field(default=0, ge=0, le=10080)
    weekly_capacity_minutes: int = Field(default=0, ge=0, le=10080)
    schedule_adherence: float = Field(default=1.0, ge=0, le=1)
    source_updated_at: datetime

    @model_validator(mode="after")
    def validate_totals(self) -> Self:
        if self.completed_task_count > self.planned_task_count:
            raise ValueError("Completed task count cannot exceed planned task count")
        if self.completed_milestone_count > self.planned_milestone_count:
            raise ValueError(
                "Completed milestone count cannot exceed planned milestone count"
            )
        return self


class ExecutionContextRead(ExecutionContextSync):
    id: uuid.UUID
    goal_id: uuid.UUID
    student_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime


class ResourceCreate(Phase4Model):
    competency_ref: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=3, max_length=240)
    url: HttpUrl
    provider: str = Field(min_length=2, max_length=160)
    resource_type: Literal[
        "article", "video", "course", "book", "documentation", "exercise", "tool"
    ]
    difficulty: int = Field(ge=1, le=5)
    language: str = Field(default="en", min_length=2, max_length=16)
    cost_amount: float = Field(default=0, ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    license_name: str | None = Field(default=None, max_length=120)
    content_excerpt: str = Field(min_length=20, max_length=5000)
    quality_score: float = Field(default=0.5, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("currency")
    @classmethod
    def currency_upper(cls, value: str) -> str:
        return value.upper()


class ResourceStatusUpdate(Phase4Model):
    status: ResourceStatus
    reason: str = Field(min_length=3, max_length=500)
    expected_version: int = Field(ge=1)


class ResourceRead(ResourceCreate):
    id: uuid.UUID
    status: ResourceStatus
    created_by_user_id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")


class ResourceRecommendationRequest(Phase4Model):
    competency_ref: str = Field(min_length=1, max_length=120)
    difficulty: int = Field(default=2, ge=1, le=5)
    language: str = Field(default="en", min_length=2, max_length=16)
    max_cost: float | None = Field(default=None, ge=0)
    preferred_types: list[str] = Field(default_factory=list, max_length=10)
    query: str | None = Field(default=None, max_length=500)
    limit: int = Field(default=5, ge=1, le=10)


class RankedResource(Phase4Model):
    resource: ResourceRead
    rank: int = Field(ge=1)
    relevance_score: float = Field(ge=0, le=1)
    selection_reason: str


class ResourceBundle(AgentOutput):
    goal_id: uuid.UUID
    competency_ref: str
    resources: list[RankedResource]


class FocusSessionStart(Phase4Model):
    goal_id: uuid.UUID
    task_ref: str | None = Field(default=None, max_length=120)
    milestone_ref: str | None = Field(default=None, max_length=120)
    objective: str = Field(min_length=3, max_length=500)
    planned_minutes: int = Field(ge=5, le=240)
    idempotency_key: str = Field(min_length=8, max_length=128)


class FocusSessionComplete(Phase4Model):
    expected_version: int = Field(ge=1)
    actual_minutes: int = Field(ge=1, le=480)
    distraction_count: int = Field(default=0, ge=0, le=100)
    blocker_notes: list[str] = Field(default_factory=list, max_length=20)
    reflection: str | None = Field(default=None, max_length=2000)
    accomplished: bool


class FocusSessionRead(Phase4Model):
    id: uuid.UUID
    student_id: uuid.UUID
    goal_id: uuid.UUID
    task_ref: str | None
    milestone_ref: str | None
    objective: str
    planned_minutes: int
    actual_minutes: int | None
    distraction_count: int
    blocker_notes: list[str]
    reflection: str | None
    accomplished: bool | None
    status: FocusSessionStatus
    version: int
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class FocusCoachOutput(AgentOutput):
    session_id: uuid.UUID
    opening_prompt: str
    completion_feedback: str | None = None
    recommended_break_minutes: int = Field(default=5, ge=0, le=60)
    blocker_detected: bool = False


class TutorMessageRequest(Phase4Model):
    goal_id: uuid.UUID
    competency_ref: str = Field(min_length=1, max_length=120)
    thread_id: uuid.UUID | None = None
    mode: TutorMode = TutorMode.EXPLAIN
    integrity_mode: AcademicIntegrityMode = AcademicIntegrityMode.LEARNING
    message: str = Field(min_length=2, max_length=6000)


class TutorCitation(Phase4Model):
    resource_id: uuid.UUID
    title: str
    url: str
    excerpt: str


class TutorResponse(AgentOutput):
    thread_id: uuid.UUID
    response: str
    mode: TutorMode
    citations: list[TutorCitation]
    follow_up_questions: list[str]
    integrity_boundary_applied: bool


class AssessmentQuestionInput(Phase4Model):
    id: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=3, max_length=2000)
    kind: Literal["multiple_choice", "short_answer", "boolean"]
    options: list[str] = Field(default_factory=list, max_length=12)
    correct_answer: str | bool | None = None
    expected_keywords: list[str] = Field(default_factory=list, max_length=20)
    points: float = Field(default=1, gt=0, le=100)
    explanation: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_scoring_definition(self) -> Self:
        if self.kind in {"multiple_choice", "boolean"} and self.correct_answer is None:
            raise ValueError("Objective questions require a correct answer")
        if self.kind == "multiple_choice" and len(self.options) < 2:
            raise ValueError("Multiple-choice questions require at least two options")
        if self.kind == "short_answer" and not self.expected_keywords:
            raise ValueError("Short-answer questions require expected keywords")
        return self


class AssessmentCreate(Phase4Model):
    goal_id: uuid.UUID
    competency_ref: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=3, max_length=240)
    assessment_type: Literal["quiz", "project", "oral", "code", "reflection"]
    instructions: str = Field(min_length=5, max_length=5000)
    questions: list[AssessmentQuestionInput] = Field(min_length=1, max_length=100)
    rubric: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    passing_percentage: float = Field(default=70, ge=0, le=100)
    time_limit_minutes: int | None = Field(default=None, ge=1, le=480)


class AssessmentGenerateRequest(Phase4Model):
    goal_id: uuid.UUID
    competency_ref: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=3, max_length=240)
    learning_outcomes: list[str] = Field(min_length=1, max_length=20)
    source_facts: list[str] = Field(min_length=2, max_length=50)
    question_count: int = Field(default=5, ge=2, le=20)
    difficulty: int = Field(default=2, ge=1, le=5)
    passing_percentage: float = Field(default=70, ge=0, le=100)


class AssessmentStatusUpdate(Phase4Model):
    status: AssessmentStatus
    expected_version: int = Field(ge=1)


class AssessmentQuestionPublic(Phase4Model):
    id: str
    prompt: str
    kind: str
    options: list[str]
    points: float


class AssessmentRead(Phase4Model):
    id: uuid.UUID
    goal_id: uuid.UUID
    competency_ref: str
    title: str
    assessment_type: str
    instructions: str
    questions: list[AssessmentQuestionPublic]
    rubric: list[dict[str, Any]]
    max_score: float
    passing_percentage: float
    time_limit_minutes: int | None
    status: AssessmentStatus
    version: int
    created_at: datetime
    updated_at: datetime


class AssessmentAnswer(Phase4Model):
    question_id: str = Field(min_length=1, max_length=80)
    answer: str | bool


class AssessmentAttemptCreate(Phase4Model):
    answers: list[AssessmentAnswer] = Field(min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=8, max_length=128)


class AssessmentAttemptRead(Phase4Model):
    id: uuid.UUID
    assessment_id: uuid.UUID
    student_id: uuid.UUID
    attempt_number: int
    answers: list[dict[str, Any]]
    score: float
    max_score: float
    percentage: float
    passed: bool
    feedback: list[dict[str, Any]]
    status: AttemptStatus
    submitted_at: datetime


class EvidenceSubmissionCreate(Phase4Model):
    goal_id: uuid.UUID
    competency_ref: str = Field(min_length=1, max_length=120)
    task_ref: str | None = Field(default=None, max_length=120)
    milestone_ref: str | None = Field(default=None, max_length=120)
    assessment_attempt_id: uuid.UUID | None = None
    original_name: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=3, max_length=120)
    size_bytes: int = Field(gt=0, le=100_000_000)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    storage_key: str = Field(min_length=3, max_length=500)
    content_text: str | None = Field(default=None, max_length=100_000)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=30)
    idempotency_key: str = Field(min_length=8, max_length=128)


class StorageReceiptCreate(Phase4Model):
    storage_key: str = Field(min_length=3, max_length=500)
    media_type: str = Field(min_length=3, max_length=120)
    size_bytes: int = Field(gt=0, le=100_000_000)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    scanner_status: Literal["clean", "quarantined"]


class StorageReceiptRead(StorageReceiptCreate):
    id: uuid.UUID
    verified_by_user_id: uuid.UUID
    verified_at: datetime


class CriteriaResult(Phase4Model):
    criterion: str
    satisfied: bool
    confidence: float = Field(ge=0, le=1)
    explanation: str


class EvidenceVerificationReport(AgentOutput):
    evidence_id: uuid.UUID
    decision: EvidenceStatus
    quality_score: float = Field(ge=0, le=1)
    criteria_results: list[CriteriaResult]
    integrity_flags: list[str]
    feedback: str


class EvidenceRead(Phase4Model):
    id: uuid.UUID
    student_id: uuid.UUID
    goal_id: uuid.UUID
    competency_ref: str
    task_ref: str | None
    milestone_ref: str | None
    assessment_attempt_id: uuid.UUID | None
    original_name: str
    media_type: str
    size_bytes: int
    sha256: str
    storage_key: str
    acceptance_criteria: list[str]
    status: EvidenceStatus
    quality_score: float | None
    submitted_at: datetime
    reviewed_at: datetime | None


class AdminEvidenceDecision(Phase4Model):
    decision: Literal["verified", "rejected", "resubmission_required"]
    reason: str = Field(min_length=5, max_length=2000)


class ProgressSnapshotRead(Phase4Model):
    id: uuid.UUID
    student_id: uuid.UUID
    goal_id: uuid.UUID
    version: int
    activity_progress: float = Field(ge=0, le=100)
    milestone_progress: float = Field(ge=0, le=100)
    mastery_progress: float = Field(ge=0, le=100)
    goal_confidence: float = Field(ge=0, le=100)
    schedule_variance: float
    verified_evidence_count: int
    assessment_count: int
    focus_minutes: int
    calculation: dict[str, Any]
    as_of: datetime


class MasteryEstimateRead(Phase4Model):
    id: uuid.UUID
    student_id: uuid.UUID
    goal_id: uuid.UUID
    competency_ref: str
    version: int
    score: float = Field(ge=0, le=1)
    confidence_lower: float = Field(ge=0, le=1)
    confidence_upper: float = Field(ge=0, le=1)
    evidence_count: int
    weak_subskills: list[str]
    next_assessment_recommendation: str
    calculation: dict[str, Any]
    estimated_at: datetime


class CoachingRequest(Phase4Model):
    goal_id: uuid.UUID
    check_in: str = Field(min_length=2, max_length=2000)
    motivation_level: int = Field(ge=1, le=5)
    notification_enabled: bool = True


class CoachingResponse(AgentOutput):
    coaching_id: uuid.UUID
    message: str
    reflection_prompt: str
    habit_experiment: str
    notification_adjustment: str | None


class RiskScanRequest(Phase4Model):
    open_blockers: list[str] = Field(default_factory=list, max_length=30)
    tutor_misconceptions: list[str] = Field(default_factory=list, max_length=30)
    resource_issue: str | None = Field(default=None, max_length=1000)


class RiskRead(Phase4Model):
    id: uuid.UUID
    student_id: uuid.UUID
    goal_id: uuid.UUID
    risk_type: str
    severity: RiskSeverity
    status: RiskStatus
    score: float = Field(ge=0, le=1)
    evidence_refs: list[str]
    likely_causes: list[str]
    intervention: str
    requires_admin_review: bool
    version: int
    detected_at: datetime
    resolved_at: datetime | None


class RiskScanResult(AgentOutput):
    goal_id: uuid.UUID
    risks: list[RiskRead]


class ReplanRequest(Phase4Model):
    risk_id: uuid.UUID
    base_plan_ref: str = Field(min_length=1, max_length=120)
    base_plan_version: int = Field(ge=1)
    preserve_completed_work: bool = True
    student_constraints: dict[str, Any] = Field(default_factory=dict)


class ReplanProposalRead(Phase4Model):
    id: uuid.UUID
    student_id: uuid.UUID
    goal_id: uuid.UUID
    risk_id: uuid.UUID
    base_plan_ref: str
    base_plan_version: int
    status: ReplanStatus
    proposed_patch: list[dict[str, Any]]
    impact_analysis: dict[str, Any]
    alternatives: list[dict[str, Any]]
    preserves_completed_work: bool
    student_approval_required: bool
    admin_review_required: bool
    version: int
    created_at: datetime
    decided_at: datetime | None
    applied_plan_ref: str | None
    applied_plan_version: int | None
    applied_at: datetime | None


class ReplanDecision(Phase4Model):
    decision: Literal["approve", "reject"]
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=1000)


class NotificationRead(Phase4Model):
    id: uuid.UUID
    student_id: uuid.UUID
    notification_type: str
    title: str
    body: str
    related_type: str | None
    related_id: str | None
    read_at: datetime | None
    created_at: datetime


class AgentRunRead(Phase4Model):
    id: uuid.UUID
    agent_name: str
    agent_version: str
    status: AgentExecutionStatus
    idempotency_key: str
    input_hash: str
    output_hash: str | None
    policy_version: str
    started_at: datetime
    completed_at: datetime | None


class Page(Phase4Model):
    items: list[Any]
    total: int
    limit: int
    offset: int
