import uuid
from datetime import date, datetime, time
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class AvailabilityWindow(ContractModel):
    start: time
    end: time
    energy: Literal["low", "medium", "high"] = "medium"

    @model_validator(mode="after")
    def positive_window(self) -> Self:
        if self.end <= self.start:
            raise ValueError("Availability window end must be after start")
        return self


class FixedCommitment(ContractModel):
    title: str = Field(min_length=1, max_length=160)
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def positive_duration(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("Fixed commitment end must be after start")
        return self


class SchedulingConstraints(ContractModel):
    availability: dict[str, list[AvailabilityWindow]] | None = None
    max_session_minutes: int = Field(default=60, ge=15, le=180)
    minimum_break_minutes: int = Field(default=15, ge=0, le=60)
    max_daily_minutes: int = Field(default=120, ge=30, le=480)
    buffer_ratio: float = Field(default=0.15, ge=0.05, le=0.5)
    do_not_disturb: list[FixedCommitment] = Field(default_factory=list, max_length=100)

    @field_validator("availability")
    @classmethod
    def valid_weekdays(
        cls, value: dict[str, list[AvailabilityWindow]] | None
    ) -> dict[str, list[AvailabilityWindow]] | None:
        if value is None:
            return value
        allowed = {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }
        invalid = sorted(set(value) - allowed)
        if invalid:
            raise ValueError(f"Unknown weekdays: {', '.join(invalid)}")
        return value


class PlanGenerationRequest(ContractModel):
    starts_on: date | None = None
    include_optional: bool = False
    constraints: SchedulingConstraints = Field(default_factory=SchedulingConstraints)
    fixed_commitments: list[FixedCommitment] = Field(default_factory=list, max_length=200)
    integration_metadata: dict[str, Any] = Field(default_factory=dict)


class MilestoneSpec(ContractModel):
    key: str
    graph_node_id: uuid.UUID | None
    competency_id: uuid.UUID | None
    title: str
    description: str
    target_date: date
    acceptance_criteria: list[str]
    evidence_requirements: list[str]
    dependency_keys: list[str]
    sequence_number: int = Field(ge=1)
    estimated_minutes: int = Field(gt=0)
    buffer_minutes: int = Field(ge=0)


class TaskSpec(ContractModel):
    key: str
    milestone_key: str
    competency_id: uuid.UUID | None
    title: str
    description: str
    task_type: Literal["learn", "practice", "apply", "review", "evidence"]
    priority: int = Field(ge=1, le=5)
    estimated_minutes: int = Field(gt=0)
    evidence_required: bool
    evidence_description: str | None
    sequence_number: int = Field(ge=1)
    due_date: date


class MilestoneRead(ContractModel):
    id: uuid.UUID
    graph_node_id: uuid.UUID | None
    title: str
    description: str
    target_date: date
    status: str
    acceptance_criteria: list[str]
    evidence_requirements: list[str]
    dependency_ids: list[str]
    sequence_number: int
    estimated_minutes: int
    buffer_minutes: int


class TaskRead(ContractModel):
    id: uuid.UUID
    milestone_id: uuid.UUID
    competency_id: uuid.UUID | None
    title: str
    description: str
    task_type: str
    status: str
    priority: int
    estimated_minutes: int
    scheduled_start: datetime | None
    scheduled_end: datetime | None
    evidence_required: bool
    evidence_description: str | None
    sequence_number: int


class ScheduleConflict(ContractModel):
    code: str
    severity: Literal["info", "warning", "blocking"]
    message: str
    task_key: str | None = None
    unscheduled_minutes: int = Field(default=0, ge=0)
    evidence: list[str] = Field(default_factory=list)


class ScheduleBlockSpec(ContractModel):
    task_key: str
    starts_at: datetime
    ends_at: datetime
    block_type: str
    energy_level: str


class ScheduleBlockRead(ContractModel):
    id: uuid.UUID
    task_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    block_type: str
    energy_level: str
    status: str


class ScheduleRead(ContractModel):
    id: uuid.UUID
    timezone: str
    starts_on: date
    ends_on: date
    weekly_capacity_minutes: int
    allocated_minutes: int
    buffer_minutes: int
    schedule_health_score: float = Field(ge=0, le=1)
    status: str
    conflicts: list[ScheduleConflict]
    alternatives: list[str]
    constraints: dict[str, Any]
    blocks: list[ScheduleBlockRead]


class PlanRead(ContractModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    student_id: uuid.UUID
    version: int
    status: str
    starts_on: date
    target_date: date
    total_estimated_minutes: int
    generation_constraints: dict[str, Any]
    milestones: list[MilestoneRead]
    tasks: list[TaskRead]
    schedule: ScheduleRead
    decision_cards: list[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class PlanDecisionRequest(ContractModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=500)


class TaskEditRequest(ContractModel):
    title: str | None = Field(default=None, min_length=3, max_length=240)
    priority: int | None = Field(default=None, ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, ge=15, le=2400)
    reason: str = Field(min_length=3, max_length=500)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if not self.model_dump(exclude_unset=True).keys() - {"reason"}:
            raise ValueError("At least one task field must be supplied")
        return self


class TaskStatusRequest(ContractModel):
    status: Literal["ready", "in_progress", "completed", "blocked"]
    expected_status: Literal[
        "planned", "ready", "in_progress", "completed", "blocked"
    ]
    reason: str = Field(min_length=3, max_length=500)


class ApprovedReplanCommand(ContractModel):
    source_plan_id: uuid.UUID
    source_plan_version: int = Field(ge=1)
    operations: list[dict[str, Any]] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=3, max_length=1000)


class CalendarRead(ContractModel):
    student_id: uuid.UUID
    starts_on: date
    ends_on: date
    blocks: list[ScheduleBlockRead]
    total_scheduled_minutes: int


class DailyAction(ContractModel):
    task_id: uuid.UUID
    goal_id: uuid.UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    estimated_minutes: int
    priority: int
    reason: str
    completion_evidence: str | None


class DailyPlanRead(ContractModel):
    date: date
    timezone: str
    daily_plan: list[DailyAction]
    minimum_viable_day: list[DailyAction]
    stretch_task: DailyAction | None
    total_minutes: int
    capacity_warning: str | None = None
