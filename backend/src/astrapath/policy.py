import uuid

from astrapath.enums import Role
from astrapath.errors import AppError
from astrapath.models import User


class PolicyEngine:
    version = "phase1.1"

    @staticmethod
    def require_role(actor: User, role: Role) -> None:
        if actor.role != role:
            raise AppError(403, "forbidden", f"This operation requires the {role.value} role")

    @staticmethod
    def require_student_ownership(actor: User, student_id: uuid.UUID) -> None:
        if actor.role != Role.STUDENT or actor.id != student_id:
            raise AppError(403, "forbidden", "Students can access only their own records")

    @staticmethod
    def require_admin(actor: User) -> None:
        PolicyEngine.require_role(actor, Role.ADMIN)

