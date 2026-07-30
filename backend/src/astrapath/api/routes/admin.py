import uuid
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from astrapath.db import get_db
from astrapath.dependencies import make_audit_context, require_admin
from astrapath.enums import Role, UserStatus
from astrapath.errors import AppError
from astrapath.models import User
from astrapath.schemas import (
    AuditLogList,
    UserList,
    UserRead,
    UserStatusUpdate,
)
from astrapath.services import AdminService

router = APIRouter()


def _record_admin_read(
    request: Request,
    db: Session,
    admin: User,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    student_id: uuid.UUID | None = None,
) -> None:
    request.app.state.audit_service.record(
        db,
        make_audit_context(request, admin),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        student_id=student_id,
        metadata={"access_reason": request.headers.get("x-access-reason", "operations")},
    )
    db.commit()


@router.get("/users", response_model=UserList)
def list_users(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    role: Role | None = None,
    user_status: Annotated[UserStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserList:
    users, total = request.app.state.admin_service.list_users(
        db,
        role=role,
        status=user_status,
        limit=limit,
        offset=offset,
    )
    _record_admin_read(
        request,
        db,
        admin,
        action="admin.users_viewed",
        resource_type="user_collection",
        resource_id="users",
    )
    return UserList(items=users, total=total, limit=limit, offset=offset)


@router.get("/users/{user_id}", response_model=UserRead)
def get_user(
    request: Request,
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise AppError(404, "user_not_found", "User was not found")
    _record_admin_read(
        request,
        db,
        admin,
        action="admin.user_viewed",
        resource_type="user",
        resource_id=str(user.id),
        student_id=user.id if user.role == Role.STUDENT else None,
    )
    return user


@router.patch("/users/{user_id}/status", response_model=UserRead)
def set_user_status(
    request: Request,
    user_id: uuid.UUID,
    payload: UserStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> User:
    service = cast(AdminService, request.app.state.admin_service)
    return service.set_user_status(
        db,
        admin,
        user_id,
        payload.status,
        payload.reason,
        make_audit_context(request, admin),
    )


@router.get("/audit", response_model=AuditLogList)
def list_audit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
    actor_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    action: str | None = Query(default=None, max_length=120),
    resource_type: str | None = Query(default=None, max_length=80),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AuditLogList:
    logs, total = request.app.state.admin_service.list_audit(
        db,
        actor_id=actor_id,
        student_id=student_id,
        action=action,
        resource_type=resource_type,
        limit=limit,
        offset=offset,
    )
    _record_admin_read(
        request,
        db,
        admin,
        action="admin.audit_viewed",
        resource_type="audit_collection",
        resource_id="audit",
    )
    return AuditLogList(items=logs, total=total, limit=limit, offset=offset)


@router.get("/agents", response_model=list[dict[str, Any]])
def list_agents(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> list[dict[str, Any]]:
    agents: list[dict[str, Any]] = request.app.state.agent_registry.list()
    _record_admin_read(
        request,
        db,
        admin,
        action="admin.agents_viewed",
        resource_type="agent_registry",
        resource_id="phase1",
    )
    return agents
