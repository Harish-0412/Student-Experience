from enum import StrEnum


class ResourceStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    STALE = "stale"


class FocusSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class TutorMode(StrEnum):
    HINT = "hint"
    EXPLAIN = "explain"
    QUIZ = "quiz"
    DEBUG = "debug"


class AssessmentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


class AttemptStatus(StrEnum):
    SCORED = "scored"
    REVIEW_REQUIRED = "review_required"


class EvidenceStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    RESUBMISSION_REQUIRED = "resubmission_required"
    ADMIN_REVIEW_REQUIRED = "admin_review_required"


class RiskSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskStatus(StrEnum):
    OPEN = "open"
    MITIGATED = "mitigated"
    DISMISSED = "dismissed"


class ReplanStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED_PENDING_PHASE3 = "approved_pending_phase3"
    REJECTED = "rejected"
    APPLIED = "applied"


class AgentExecutionStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    INPUT_REQUIRED = "input_required"
    ADMIN_REVIEW_REQUIRED = "admin_review_required"
    STUDENT_APPROVAL_REQUIRED = "student_approval_required"
    BLOCKED = "blocked"
    FAILED = "failed"


class AcademicIntegrityMode(StrEnum):
    LEARNING = "learning"
    PRACTICE = "practice"
    GRADED = "graded"
