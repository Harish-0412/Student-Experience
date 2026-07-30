import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from astrapath.enums import Role
from astrapath.models import AuditLog, User


@dataclass
class AuditContext:
    actor: User | None
    request_id: str | None = None
    correlation_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class AuditService:
    def record(
        self,
        db: Session,
        context: AuditContext,
        *,
        action: str,
        resource_type: str,
        resource_id: str | uuid.UUID,
        student_id: uuid.UUID | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        previous = db.scalar(
            select(AuditLog).order_by(AuditLog.occurred_at.desc(), AuditLog.id.desc()).limit(1)
        )
        occurred_at = datetime.now(UTC)
        event_metadata = {**context.metadata, **(metadata or {})}
        hash_payload = {
            "occurred_at": occurred_at.isoformat(),
            "actor_id": str(context.actor.id) if context.actor else None,
            "actor_role": context.actor.role.value if context.actor else "system",
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "student_id": str(student_id) if student_id else None,
            "request_id": context.request_id,
            "correlation_id": context.correlation_id,
            "before": before,
            "after": after,
            "metadata": event_metadata,
            "previous_hash": previous.event_hash if previous else None,
        }
        event_hash = hashlib.sha256(_canonical_json(hash_payload).encode("utf-8")).hexdigest()
        log = AuditLog(
            occurred_at=occurred_at,
            actor_id=context.actor.id if context.actor else None,
            actor_role=context.actor.role.value if context.actor else "system",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            student_id=student_id,
            request_id=context.request_id,
            correlation_id=context.correlation_id,
            ip_address=context.ip_address,
            user_agent=context.user_agent,
            before_data=before,
            after_data=after,
            event_metadata=event_metadata,
            previous_hash=previous.event_hash if previous else None,
            event_hash=event_hash,
        )
        db.add(log)
        return log


def system_audit_context(metadata: dict[str, Any] | None = None) -> AuditContext:
    return AuditContext(actor=None, metadata=metadata or {"actor_role": Role.ADMIN.value})
