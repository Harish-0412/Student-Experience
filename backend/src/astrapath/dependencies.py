import uuid
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from astrapath.audit import AuditContext
from astrapath.config import Settings
from astrapath.db import get_db
from astrapath.enums import Role, UserStatus
from astrapath.errors import AppError
from astrapath.models import User
from astrapath.policy import PolicyEngine
from astrapath.security import TokenService

bearer = HTTPBearer(auto_error=False)


def get_app_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_token_service(request: Request) -> TokenService:
    return cast(TokenService, request.app.state.token_service)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> User:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise AppError(401, "authentication_required", "A bearer access token is required")

    identity = token_service.verify_access_token(credentials.credentials)
    if settings.auth_mode == "local":
        try:
            user_id = uuid.UUID(identity.subject)
        except ValueError as exc:
            raise AppError(401, "invalid_subject", "Token subject is invalid") from exc
        user = db.get(User, user_id)
        if not user or user.auth_version != identity.auth_version:
            raise AppError(401, "invalid_token", "Token is no longer valid")
    else:
        user = db.scalar(
            select(User).where(
                User.oidc_issuer == identity.issuer,
                User.oidc_subject == identity.subject,
            )
        )
        if not user:
            if not identity.email:
                raise AppError(403, "oidc_profile_incomplete", "OIDC token must include email")
            email = identity.email.strip().lower()
            existing_email = db.scalar(select(User).where(User.email == email))
            if existing_email:
                raise AppError(
                    409,
                    "identity_link_required",
                    "An account with this email already exists; an admin must link the identity",
                )
            user = User(
                email=email,
                full_name=identity.full_name or email.split("@", maxsplit=1)[0],
                role=identity.role,
                status=UserStatus.ACTIVE,
                oidc_issuer=identity.issuer,
                oidc_subject=identity.subject,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

    if user.status == UserStatus.SUSPENDED:
        raise AppError(403, "account_suspended", "This account has been suspended")
    if user.status != UserStatus.ACTIVE:
        raise AppError(401, "account_inactive", "This account is not active")
    return user


def require_student(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    PolicyEngine.require_role(user, Role.STUDENT)
    return user


def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    PolicyEngine.require_admin(user)
    return user


def make_audit_context(request: Request, actor: User | None) -> AuditContext:
    settings = getattr(request.app.state, "settings", None)
    forwarded_for = (
        request.headers.get("x-forwarded-for")
        if settings and settings.trust_proxy_headers
        else None
    )
    ip_address = (
        forwarded_for.split(",", maxsplit=1)[0].strip()
        if forwarded_for
        else request.client.host if request.client else None
    )
    return AuditContext(
        actor=actor,
        request_id=getattr(request.state, "request_id", None),
        correlation_id=request.headers.get("x-correlation-id"),
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
    )
