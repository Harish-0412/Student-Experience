import uuid
from typing import Annotated

from fastapi import Depends, Header

from astrapath.dependencies import get_current_user
from astrapath.enums import Role
from astrapath.errors import AppError
from astrapath.models import User


def get_standalone_phase4_actor(
    actor_id: Annotated[uuid.UUID, Header(alias="X-AstraPath-Actor-Id")],
    actor_role: Annotated[str, Header(alias="X-AstraPath-Actor-Role")],
) -> User:
    """Development-only actor for the isolated Phase 4 application."""
    try:
        role = Role(actor_role)
    except ValueError as exc:
        raise AppError(403, "invalid_role", "Actor role must be student or admin") from exc
    return User(
        id=actor_id,
        email=f"{actor_id}@phase4.local",
        full_name="Phase 4 Standalone Actor",
        role=role,
    )


def get_phase4_actor(
    actor: Annotated[User, Depends(get_current_user)],
) -> User:
    """Expose the authenticated Phase 1 principal to Phase 4 routes."""
    return actor
