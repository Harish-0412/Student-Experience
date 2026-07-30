from enum import StrEnum


class Role(StrEnum):
    STUDENT = "student"
    ADMIN = "admin"


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class GoalStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CLOSED = "closed"


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    INPUT_REQUIRED = "input_required"
    APPROVAL_REQUIRED = "approval_required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    INPUT_REQUIRED = "input_required"
    STUDENT_APPROVAL_REQUIRED = "student_approval_required"
    ADMIN_REVIEW_REQUIRED = "admin_review_required"
    BLOCKED = "blocked"
    FAILED = "failed"

