import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from astrapath.enums import Role
from astrapath.models import AuditChainHead, AuditLog, User


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
    def __init__(self) -> None:
        self._lock = threading.Lock()

    @staticmethod
    def _reserve_previous_hash(db: Session) -> str | None:
        now = datetime.now(UTC)
        reservation = db.execute(
            update(AuditChainHead)
            .where(AuditChainHead.id == 1)
            .values(
                version=AuditChainHead.version + 1,
                updated_at=now,
            )
            .returning(AuditChainHead.current_hash)
        ).one_or_none()
        if reservation is not None:
            value = reservation[0]
            return str(value) if value is not None else None

        head = AuditChainHead(
            id=1,
            current_hash=None,
            version=1,
            updated_at=now,
        )
        db.add(head)
        db.flush()
        return None

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
        with self._lock:
            previous_hash = self._reserve_previous_hash(db)
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
                "previous_hash": previous_hash,
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
                previous_hash=previous_hash,
                event_hash=event_hash,
            )
            db.add(log)
            db.execute(
                update(AuditChainHead)
                .where(AuditChainHead.id == 1)
                .values(current_hash=event_hash, updated_at=occurred_at)
            )
            return log


def system_audit_context(metadata: dict[str, Any] | None = None) -> AuditContext:
    return AuditContext(actor=None, metadata=metadata or {"actor_role": Role.ADMIN.value})
