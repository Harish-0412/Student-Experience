import uuid
from typing import Annotated

from fastapi import Depends, Header

from astrapath.dependencies import get_current_user
from astrapath.enums import Role
from astrapath.errors import AppError
from astrapath.models import User


def get_standalone_phase2_actor(
    actor_id: Annotated[
        uuid.UUID,
        Header(alias="X-AstraPath-Actor-Id"),
    ],
    actor_role: Annotated[
        str,
        Header(alias="X-AstraPath-Actor-Role"),
    ],
) -> User:
    """Development-only actor used by the isolated Phase 2 test application."""
    try:
        role = Role(actor_role)
    except ValueError as exc:
        raise AppError(403, "invalid_role", "Actor role must be student or admin") from exc
    return User(
        id=actor_id,
        email=f"{actor_id}@phase2.local",
        full_name="Phase 2 Standalone Actor",
        role=role,
    )


def get_phase2_actor(
    actor: Annotated[User, Depends(get_current_user)],
) -> User:
    """Authenticated Phase 1 principal exposed to Phase 2 routes."""
    return actor
