from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from astrapath.db import get_db
from astrapath.dependencies import get_current_user, make_audit_context
from astrapath.models import User
from astrapath.schemas import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserRead,
)
from astrapath.services import AuthService

router = APIRouter()


def _request_network_context(request: Request) -> tuple[str | None, str | None]:
    context = make_audit_context(request, None)
    return context.user_agent, context.ip_address


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(
    request: Request,
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    user_agent, ip_address = _request_network_context(request)
    service = cast(AuthService, request.app.state.auth_service)
    return service.register(
        db,
        payload,
        make_audit_context(request, None),
        user_agent=user_agent,
        ip_address=ip_address,
    )


@router.post("/login", response_model=TokenPair)
def login(
    request: Request,
    payload: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    user_agent, ip_address = _request_network_context(request)
    service = cast(AuthService, request.app.state.auth_service)
    return service.login(
        db,
        payload,
        make_audit_context(request, None),
        user_agent=user_agent,
        ip_address=ip_address,
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(
    request: Request,
    payload: RefreshRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    user_agent, ip_address = _request_network_context(request)
    service = cast(AuthService, request.app.state.auth_service)
    return service.refresh(
        db,
        payload.refresh_token,
        make_audit_context(request, None),
        user_agent=user_agent,
        ip_address=ip_address,
    )


@router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    payload: LogoutRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    request.app.state.auth_service.logout(
        db,
        user,
        payload.refresh_token,
        make_audit_context(request, user),
    )
    return MessageResponse(message="Signed out")


@router.get("/me", response_model=UserRead)
def me(user: Annotated[User, Depends(get_current_user)]) -> User:
    return user
