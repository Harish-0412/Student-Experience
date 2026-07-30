import re
import uuid
from datetime import date, datetime
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from astrapath.enums import GoalStatus, Role, UserStatus, WorkflowStatus


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class RegisterRequest(ApiModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        groups = sum(
            bool(re.search(pattern, value))
            for pattern in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]")
        )
        if groups < 3:
            raise ValueError(
                "Password must include characters from at least three of: "
                "lowercase, uppercase, number, symbol"
            )
        return value


class LoginRequest(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(ApiModel):
    refresh_token: str = Field(min_length=20)


class LogoutRequest(ApiModel):
    refresh_token: str = Field(min_length=20)


class UserRead(ApiModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: Role
    status: UserStatus
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


class TokenPair(ApiModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int
    user: UserRead


class ProfileFields(ApiModel):
    display_name: str = Field(min_length=1, max_length=100)
    timezone: str = Field(default="Asia/Kolkata", min_length=1, max_length=64)
    locale: str = Field(default="en-IN", min_length=2, max_length=16)
    education_level: str | None = Field(default=None, max_length=120)
    institution: str | None = Field(default=None, max_length=200)
    weekly_learning_minutes: int = Field(default=300, ge=0, le=10080)
    learning_preferences: list[str] = Field(default_factory=list, max_length=20)
    availability: dict[str, Any] = Field(default_factory=dict)
    device_access: list[str] = Field(default_factory=list, max_length=20)
    accessibility_needs: list[str] = Field(default_factory=list, max_length=20)
    consent_scopes: list[str] = Field(default_factory=list, max_length=30)

    @field_validator(
        "learning_preferences",
        "device_access",
        "accessibility_needs",
        "consent_scopes",
    )
    @classmethod
    def unique_bounded_values(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if any(len(item) > 80 for item in normalized):
            raise ValueError("List values must not exceed 80 characters")
        return list(dict.fromkeys(normalized))


class OnboardingRequest(ProfileFields):
    onboarding_completed: bool = True


class ProfileUpdate(ApiModel):
    expected_version: int = Field(ge=1)
    change_reason: str = Field(default="student_update", min_length=3, max_length=255)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    locale: str | None = Field(default=None, min_length=2, max_length=16)
    education_level: str | None = Field(default=None, max_length=120)
    institution: str | None = Field(default=None, max_length=200)
    weekly_learning_minutes: int | None = Field(default=None, ge=0, le=10080)
    learning_preferences: list[str] | None = Field(default=None, max_length=20)
    availability: dict[str, Any] | None = None
    device_access: list[str] | None = Field(default=None, max_length=20)
    accessibility_needs: list[str] | None = Field(default=None, max_length=20)
    consent_scopes: list[str] | None = Field(default=None, max_length=30)
    onboarding_completed: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> Self:
        excluded = {"expected_version", "change_reason"}
        if not self.model_dump(exclude_unset=True).keys() - excluded:
            raise ValueError("At least one profile field must be supplied")
        return self


class StudentProfileRead(ProfileFields):
    id: uuid.UUID
    user_id: uuid.UUID
    version: int
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime


class ProfileCompletenessRead(ApiModel):
    completeness: float = Field(ge=0, le=1)
    missing_fields: list[str]
    warnings: list[str]
    ready_for_goal_planning: bool


class GoalCreate(ApiModel):
    title: str = Field(min_length=3, max_length=160)
    raw_statement: str = Field(min_length=5, max_length=4000)
    description: str | None = Field(default=None, max_length=10000)
    category: str | None = Field(default=None, max_length=80)
    target_date: date | None = None
    priority: int = Field(default=3, ge=1, le=5)
    success_criteria: list[str] = Field(default_factory=list, max_length=20)
    assumptions: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("target_date")
    @classmethod
    def validate_target_date(cls, value: date | None) -> date | None:
        if value is not None and value < date.today():
            raise ValueError("Target date cannot be in the past")
        return value

    @field_validator("success_criteria", "assumptions")
    @classmethod
    def clean_goal_lists(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if any(len(item) > 500 for item in cleaned):
            raise ValueError("Goal list values must not exceed 500 characters")
        return list(dict.fromkeys(cleaned))


class GoalUpdate(ApiModel):
    expected_version: int = Field(ge=1)
    change_reason: str = Field(default="student_update", min_length=3, max_length=255)
    title: str | None = Field(default=None, min_length=3, max_length=160)
    raw_statement: str | None = Field(default=None, min_length=5, max_length=4000)
    description: str | None = Field(default=None, max_length=10000)
    category: str | None = Field(default=None, max_length=80)
    target_date: date | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    success_criteria: list[str] | None = Field(default=None, max_length=20)
    assumptions: list[str] | None = Field(default=None, max_length=20)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        excluded = {"expected_version", "change_reason"}
        if not self.model_dump(exclude_unset=True).keys() - excluded:
            raise ValueError("At least one goal field must be supplied")
        return self


class GoalTransitionRequest(ApiModel):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=3, max_length=255)


class GoalRead(ApiModel):
    id: uuid.UUID
    student_id: uuid.UUID
    version: int
    title: str
    raw_statement: str
    description: str | None
    category: str | None
    target_date: date | None
    priority: int
    status: GoalStatus
    success_criteria: list[str]
    assumptions: list[str]
    paused_at: datetime | None
    completed_at: datetime | None
    closed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GoalVersionRead(ApiModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    version: int
    snapshot: dict[str, Any]
    changed_by_user_id: uuid.UUID
    change_type: str
    change_reason: str | None
    created_at: datetime


class GoalList(ApiModel):
    items: list[GoalRead]
    total: int
    limit: int
    offset: int


class WorkflowRead(ApiModel):
    id: uuid.UUID
    workflow_type: str
    student_id: uuid.UUID
    goal_id: uuid.UUID | None
    status: WorkflowStatus
    current_step: str
    version: int
    state_data: dict[str, Any]
    correlation_id: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class GoalClarificationResponse(ApiModel):
    workflow: WorkflowRead
    summary: str
    clarification_questions: list[str]
    confidence: float = Field(ge=0, le=1)


class UserStatusUpdate(ApiModel):
    status: UserStatus
    reason: str = Field(min_length=3, max_length=255)

    @field_validator("status")
    @classmethod
    def only_operational_statuses(cls, value: UserStatus) -> UserStatus:
        if value == UserStatus.DELETED:
            raise ValueError("Account deletion requires a dedicated privacy workflow")
        return value


class UserList(ApiModel):
    items: list[UserRead]
    total: int
    limit: int
    offset: int


class AuditLogRead(ApiModel):
    id: uuid.UUID
    occurred_at: datetime
    actor_id: uuid.UUID | None
    actor_role: str
    action: str
    resource_type: str
    resource_id: str
    student_id: uuid.UUID | None
    request_id: str | None
    correlation_id: str | None
    before_data: dict[str, Any] | None
    after_data: dict[str, Any] | None
    event_metadata: dict[str, Any]
    previous_hash: str | None
    event_hash: str


class AuditLogList(ApiModel):
    items: list[AuditLogRead]
    total: int
    limit: int
    offset: int


class MessageResponse(ApiModel):
    message: str


class HealthResponse(ApiModel):
    status: str
    service: str
    version: str
