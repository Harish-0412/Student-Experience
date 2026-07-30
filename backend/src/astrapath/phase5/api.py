from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from astrapath.db import get_db
from astrapath.dependencies import require_admin
from astrapath.models import User
from astrapath.phase5.contracts import (
    AuditVerification,
    MetricsSnapshot,
    OperationalStatus,
    SecurityPolicyRead,
)
from astrapath.phase5.service import OperationalService

phase5_router = APIRouter(prefix="/api/v1/admin/operations", tags=["phase5-operations"])

AdminActor = Annotated[User, Depends(require_admin)]
DatabaseSession = Annotated[Session, Depends(get_db)]


@phase5_router.get("/status", response_model=OperationalStatus)
def operational_status(
    request: Request,
    db: DatabaseSession,
    _actor: AdminActor,
) -> OperationalStatus:
    return _service(request).status(db, request.app)


@phase5_router.get("/metrics", response_model=MetricsSnapshot)
def metrics(request: Request, _actor: AdminActor) -> MetricsSnapshot:
    return _service(request).metrics.snapshot()


@phase5_router.get("/security-policy", response_model=SecurityPolicyRead)
def security_policy(request: Request, _actor: AdminActor) -> SecurityPolicyRead:
    return _service(request).security_policy(request.app)


@phase5_router.post("/audit/verify", response_model=AuditVerification)
def verify_audit(
    request: Request,
    db: DatabaseSession,
    _actor: AdminActor,
) -> AuditVerification:
    return _service(request).verify_audit_chain(db)


def _service(request: Request) -> OperationalService:
    return cast(OperationalService, request.app.state.operational_service)
