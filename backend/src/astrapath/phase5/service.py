import hashlib
import json
from datetime import UTC
from typing import Any, cast

from fastapi import FastAPI
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from astrapath.agents.registry import AgentRegistry
from astrapath.models import AuditLog
from astrapath.phase4.registry import Phase4Registry
from astrapath.phase5.contracts import (
    AuditVerification,
    ComponentStatus,
    OperationalStatus,
    SecurityPolicyRead,
)
from astrapath.phase5.metrics import MetricsRegistry


def _canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


class OperationalService:
    def __init__(self, metrics: MetricsRegistry) -> None:
        self.metrics = metrics

    def verify_audit_chain(self, db: Session) -> AuditVerification:
        records = list(
            db.scalars(
                select(AuditLog).order_by(AuditLog.occurred_at, AuditLog.id)
            )
        )
        previous_hash: str | None = None
        for index, record in enumerate(records, start=1):
            occurred_at = record.occurred_at
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=UTC)
            payload = {
                "occurred_at": occurred_at.isoformat(),
                "actor_id": str(record.actor_id) if record.actor_id else None,
                "actor_role": record.actor_role,
                "action": record.action,
                "resource_type": record.resource_type,
                "resource_id": record.resource_id,
                "student_id": str(record.student_id) if record.student_id else None,
                "request_id": record.request_id,
                "correlation_id": record.correlation_id,
                "before": record.before_data,
                "after": record.after_data,
                "metadata": record.event_metadata,
                "previous_hash": previous_hash,
            }
            expected_hash = hashlib.sha256(
                _canonical_json(payload).encode("utf-8")
            ).hexdigest()
            if record.previous_hash != previous_hash:
                return AuditVerification(
                    valid=False,
                    checked_records=index,
                    first_invalid_record_id=str(record.id),
                    reason="previous_hash_mismatch",
                )
            if record.event_hash != expected_hash:
                return AuditVerification(
                    valid=False,
                    checked_records=index,
                    first_invalid_record_id=str(record.id),
                    reason="event_hash_mismatch",
                )
            previous_hash = record.event_hash
        return AuditVerification(valid=True, checked_records=len(records))

    def status(self, db: Session, app: FastAPI) -> OperationalStatus:
        components: list[ComponentStatus] = []
        try:
            db.execute(text("SELECT 1"))
            components.append(ComponentStatus(name="database", status="ready", detail="reachable"))
        except Exception:
            components.append(
                ComponentStatus(name="database", status="degraded", detail="unreachable")
            )

        audit = self.verify_audit_chain(db)
        components.append(
            ComponentStatus(
                name="audit_chain",
                status="ready" if audit.valid else "degraded",
                detail=(
                    f"{audit.checked_records} records verified"
                    if audit.valid
                    else audit.reason or "verification failed"
                ),
            )
        )

        shared_registry = cast(AgentRegistry, app.state.agent_registry)
        phase4_registry = cast(Phase4Registry, app.state.phase4_registry)
        shared_count = len(shared_registry.list())
        phase4_count = len(phase4_registry.descriptors())
        components.extend(
            [
                ComponentStatus(
                    name="phase1_phase3_agent_registry",
                    status="ready" if shared_count == 9 else "degraded",
                    detail=f"{shared_count} agents registered",
                ),
                ComponentStatus(
                    name="phase4_agent_registry",
                    status="ready" if phase4_count == 10 else "degraded",
                    detail=f"{phase4_count} agents registered",
                ),
                ComponentStatus(
                    name="phase3_phase4_bridge",
                    status=(
                        "ready"
                        if getattr(app.state, "phase3_phase4_bridge", None)
                        else "degraded"
                    ),
                    detail="transactional replan adapter",
                ),
                ComponentStatus(
                    name="phase5_request_guard",
                    status="ready",
                    detail="security and reliability middleware active",
                ),
            ]
        )
        status = (
            "ready"
            if all(component.status == "ready" for component in components)
            else "degraded"
        )
        return OperationalStatus(
            status=status,
            phases=[1, 2, 3, 4, 5],
            shared_agent_count=shared_count,
            phase4_agent_count=phase4_count,
            components=components,
            audit=audit,
            metrics=self.metrics.snapshot(),
        )

    @staticmethod
    def security_policy(app: FastAPI) -> SecurityPolicyRead:
        settings = app.state.settings
        return SecurityPolicyRead(
            max_request_bytes=settings.max_request_bytes,
            rate_limit_requests=settings.rate_limit_requests,
            auth_rate_limit_requests=settings.auth_rate_limit_requests,
            rate_limit_window_seconds=settings.rate_limit_window_seconds,
            max_inflight_requests=settings.max_inflight_requests,
            idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
            trusted_host_count=len(settings.trusted_hosts),
            trust_proxy_headers=settings.trust_proxy_headers,
            production_transport_security=settings.environment
            in {"staging", "production"},
        )
