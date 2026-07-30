from typing import TYPE_CHECKING, Protocol

from sqlalchemy.orm import Session

from astrapath.audit import AuditContext
from astrapath.models import User

if TYPE_CHECKING:
    from astrapath.phase3.models import LearningPlan


class ExecutionContextSink(Protocol):
    """Boundary used by Phase 3 to publish plan state without importing Phase 4."""

    def sync_plan(
        self,
        db: Session,
        plan: "LearningPlan",
        *,
        actor: User,
        audit_context: AuditContext,
    ) -> None: ...
