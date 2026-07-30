import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from astrapath.audit import AuditContext, AuditService
from astrapath.config import Settings
from astrapath.enums import GoalStatus, Role, UserStatus
from astrapath.errors import AppError
from astrapath.models import (
    AuditLog,
    AuthSession,
    Goal,
    GoalVersion,
    StudentProfile,
    StudentProfileVersion,
    User,
)
from astrapath.schemas import (
    GoalCreate,
    GoalRead,
    GoalUpdate,
    LoginRequest,
    OnboardingRequest,
    ProfileUpdate,
    RegisterRequest,
    StudentProfileRead,
    TokenPair,
)
from astrapath.security import (
    TokenService,
    hash_password,
    hash_refresh_token,
    verify_password,
)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def profile_snapshot(profile: StudentProfile) -> dict[str, Any]:
    return StudentProfileRead.model_validate(profile).model_dump(mode="json")


def goal_snapshot(goal: Goal) -> dict[str, Any]:
    return GoalRead.model_validate(goal).model_dump(mode="json")


class AuthService:
    def __init__(
        self, settings: Settings, tokens: TokenService, audit: AuditService
    ) -> None:
        self.settings = settings
        self.tokens = tokens
        self.audit = audit

    def _require_local_auth(self) -> None:
        if self.settings.auth_mode != "local":
            raise AppError(
                404,
                "local_auth_disabled",
                "Password authentication is disabled; use the configured OIDC provider",
            )

    def register(
        self,
        db: Session,
        payload: RegisterRequest,
        audit_context: AuditContext,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        self._require_local_auth()
        email = str(payload.email).strip().lower()
        if db.scalar(select(User.id).where(User.email == email)):
            raise AppError(409, "email_exists", "An account with this email already exists")
        user = User(
            email=email,
            full_name=payload.full_name.strip(),
            password_hash=hash_password(payload.password),
            role=Role.STUDENT,
            status=UserStatus.ACTIVE,
            last_login_at=datetime.now(UTC),
        )
        db.add(user)
        db.flush()
        audit_context.actor = user
        self.audit.record(
            db,
            audit_context,
            action="auth.student_registered",
            resource_type="user",
            resource_id=user.id,
            student_id=user.id,
            after={"email": user.email, "full_name": user.full_name, "role": user.role.value},
        )
        token_pair = self._issue_pair(db, user, user_agent=user_agent, ip_address=ip_address)
        db.commit()
        db.refresh(user)
        token_pair.user = user  # type: ignore[assignment]
        return token_pair

    def login(
        self,
        db: Session,
        payload: LoginRequest,
        audit_context: AuditContext,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        self._require_local_auth()
        email = str(payload.email).strip().lower()
        user = db.scalar(select(User).where(User.email == email))
        if not user or not verify_password(payload.password, user.password_hash):
            raise AppError(401, "invalid_credentials", "Email or password is incorrect")
        if user.status == UserStatus.SUSPENDED:
            raise AppError(403, "account_suspended", "This account has been suspended")
        if user.status != UserStatus.ACTIVE:
            raise AppError(401, "account_inactive", "This account is not active")
        user.last_login_at = datetime.now(UTC)
        audit_context.actor = user
        self.audit.record(
            db,
            audit_context,
            action="auth.login_succeeded",
            resource_type="user",
            resource_id=user.id,
            student_id=user.id if user.role == Role.STUDENT else None,
        )
        token_pair = self._issue_pair(db, user, user_agent=user_agent, ip_address=ip_address)
        db.commit()
        db.refresh(user)
        token_pair.user = user  # type: ignore[assignment]
        return token_pair

    def refresh(
        self,
        db: Session,
        refresh_token: str,
        audit_context: AuditContext,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        self._require_local_auth()
        identity = self.tokens.verify_local_token(refresh_token, expected_type="refresh")
        try:
            user_id = uuid.UUID(identity.subject)
        except ValueError as exc:
            raise AppError(401, "invalid_subject", "Token subject is invalid") from exc
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.refresh_token_hash == hash_refresh_token(refresh_token)
            )
        )
        now = datetime.now(UTC)
        if not session or session.revoked_at or _aware(session.expires_at) <= now:
            raise AppError(401, "invalid_refresh_token", "Refresh token is expired or revoked")
        user = db.get(User, user_id)
        if (
            not user
            or user.status != UserStatus.ACTIVE
            or user.auth_version != identity.auth_version
        ):
            raise AppError(401, "invalid_refresh_token", "Refresh token is no longer valid")

        session.revoked_at = now
        new_pair = self._issue_pair(db, user, user_agent=user_agent, ip_address=ip_address)
        replacement = db.scalar(
            select(AuthSession)
            .where(AuthSession.user_id == user.id)
            .order_by(AuthSession.created_at.desc())
            .limit(1)
        )
        session.replaced_by_session_id = replacement.id if replacement else None
        audit_context.actor = user
        self.audit.record(
            db,
            audit_context,
            action="auth.token_refreshed",
            resource_type="auth_session",
            resource_id=session.id,
            student_id=user.id if user.role == Role.STUDENT else None,
        )
        db.commit()
        new_pair.user = user  # type: ignore[assignment]
        return new_pair

    def logout(
        self,
        db: Session,
        user: User,
        refresh_token: str,
        audit_context: AuditContext,
    ) -> None:
        self._require_local_auth()
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.user_id == user.id,
                AuthSession.refresh_token_hash == hash_refresh_token(refresh_token),
            )
        )
        if session and not session.revoked_at:
            session.revoked_at = datetime.now(UTC)
            self.audit.record(
                db,
                audit_context,
                action="auth.logout",
                resource_type="auth_session",
                resource_id=session.id,
                student_id=user.id if user.role == Role.STUDENT else None,
            )
            db.commit()

    def _issue_pair(
        self,
        db: Session,
        user: User,
        *,
        user_agent: str | None,
        ip_address: str | None,
    ) -> TokenPair:
        access_token, expires_in = self.tokens.create_access_token(
            user.id, user.role, user.auth_version
        )
        refresh_token, refresh_expires_at = self.tokens.create_refresh_token(
            user.id, user.role, user.auth_version
        )
        db.add(
            AuthSession(
                user_id=user.id,
                refresh_token_hash=hash_refresh_token(refresh_token),
                expires_at=refresh_expires_at,
                user_agent=user_agent,
                ip_address=ip_address,
            )
        )
        db.flush()
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            user=user,
        )


class ProfileService:
    def __init__(self, audit: AuditService) -> None:
        self.audit = audit

    def create_onboarding(
        self,
        db: Session,
        student: User,
        payload: OnboardingRequest,
        audit_context: AuditContext,
    ) -> StudentProfile:
        if db.scalar(select(StudentProfile.id).where(StudentProfile.user_id == student.id)):
            raise AppError(409, "profile_exists", "Student profile already exists")
        profile = StudentProfile(user_id=student.id, **payload.model_dump())
        db.add(profile)
        db.flush()
        snapshot = profile_snapshot(profile)
        db.add(
            StudentProfileVersion(
                profile_id=profile.id,
                version=profile.version,
                snapshot=snapshot,
                changed_by_user_id=student.id,
                change_reason="onboarding",
            )
        )
        self.audit.record(
            db,
            audit_context,
            action="student.profile_created",
            resource_type="student_profile",
            resource_id=profile.id,
            student_id=student.id,
            after=snapshot,
        )
        db.commit()
        db.refresh(profile)
        return profile

    def get(self, db: Session, student_id: uuid.UUID) -> StudentProfile:
        profile = db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == student_id)
        )
        if not profile:
            raise AppError(404, "profile_not_found", "Student profile has not been created")
        return profile

    def update(
        self,
        db: Session,
        student: User,
        payload: ProfileUpdate,
        audit_context: AuditContext,
    ) -> StudentProfile:
        profile = db.scalar(
            select(StudentProfile)
            .where(StudentProfile.user_id == student.id)
            .with_for_update()
        )
        if not profile:
            raise AppError(404, "profile_not_found", "Student profile has not been created")
        if profile.version != payload.expected_version:
            raise AppError(
                409,
                "version_conflict",
                "Profile was updated by another request",
                {"current_version": profile.version},
            )
        before = profile_snapshot(profile)
        changes = payload.model_dump(
            exclude={"expected_version", "change_reason"}, exclude_unset=True
        )
        for field_name, value in changes.items():
            setattr(profile, field_name, value)
        profile.version += 1
        db.flush()
        after = profile_snapshot(profile)
        db.add(
            StudentProfileVersion(
                profile_id=profile.id,
                version=profile.version,
                snapshot=after,
                changed_by_user_id=student.id,
                change_reason=payload.change_reason,
            )
        )
        self.audit.record(
            db,
            audit_context,
            action="student.profile_updated",
            resource_type="student_profile",
            resource_id=profile.id,
            student_id=student.id,
            before=before,
            after=after,
            metadata={"change_reason": payload.change_reason},
        )
        db.commit()
        db.refresh(profile)
        return profile


class GoalService:
    EDITABLE_STATUSES = {GoalStatus.DRAFT, GoalStatus.ACTIVE, GoalStatus.PAUSED}
    TRANSITIONS = {
        "activate": ({GoalStatus.DRAFT}, GoalStatus.ACTIVE),
        "pause": ({GoalStatus.ACTIVE}, GoalStatus.PAUSED),
        "resume": ({GoalStatus.PAUSED}, GoalStatus.ACTIVE),
        "complete": ({GoalStatus.ACTIVE}, GoalStatus.COMPLETED),
        "close": (
            {GoalStatus.DRAFT, GoalStatus.ACTIVE, GoalStatus.PAUSED},
            GoalStatus.CLOSED,
        ),
    }

    def __init__(self, audit: AuditService) -> None:
        self.audit = audit

    def create(
        self,
        db: Session,
        student: User,
        payload: GoalCreate,
        audit_context: AuditContext,
    ) -> Goal:
        goal = Goal(student_id=student.id, status=GoalStatus.DRAFT, **payload.model_dump())
        db.add(goal)
        db.flush()
        snapshot = goal_snapshot(goal)
        db.add(
            GoalVersion(
                goal_id=goal.id,
                version=goal.version,
                snapshot=snapshot,
                changed_by_user_id=student.id,
                change_type="create",
                change_reason="student_created",
            )
        )
        self.audit.record(
            db,
            audit_context,
            action="goal.created",
            resource_type="goal",
            resource_id=goal.id,
            student_id=student.id,
            after=snapshot,
        )
        db.commit()
        db.refresh(goal)
        return goal

    def get_owned(self, db: Session, student_id: uuid.UUID, goal_id: uuid.UUID) -> Goal:
        goal = db.scalar(
            select(Goal).where(Goal.id == goal_id, Goal.student_id == student_id)
        )
        if not goal:
            raise AppError(404, "goal_not_found", "Goal was not found")
        return goal

    def list_owned(
        self,
        db: Session,
        student_id: uuid.UUID,
        *,
        status: GoalStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Goal], int]:
        filters = [Goal.student_id == student_id]
        if status:
            filters.append(Goal.status == status)
        total = db.scalar(select(func.count(Goal.id)).where(*filters)) or 0
        items = list(
            db.scalars(
                select(Goal)
                .where(*filters)
                .order_by(Goal.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return items, total

    def update(
        self,
        db: Session,
        student: User,
        goal_id: uuid.UUID,
        payload: GoalUpdate,
        audit_context: AuditContext,
    ) -> Goal:
        goal = db.scalar(
            select(Goal)
            .where(Goal.id == goal_id, Goal.student_id == student.id)
            .with_for_update()
        )
        if not goal:
            raise AppError(404, "goal_not_found", "Goal was not found")
        if goal.status not in self.EDITABLE_STATUSES:
            raise AppError(409, "goal_not_editable", "Completed or closed goals cannot be edited")
        self._check_version(goal, payload.expected_version)
        before = goal_snapshot(goal)
        changes = payload.model_dump(
            exclude={"expected_version", "change_reason"}, exclude_unset=True
        )
        for field_name, value in changes.items():
            setattr(goal, field_name, value)
        goal.version += 1
        db.flush()
        self._write_version_and_audit(
            db,
            goal,
            student,
            audit_context,
            before=before,
            change_type="update",
            reason=payload.change_reason,
        )
        db.commit()
        db.refresh(goal)
        return goal

    def transition(
        self,
        db: Session,
        student: User,
        goal_id: uuid.UUID,
        *,
        transition: str,
        expected_version: int,
        reason: str,
        audit_context: AuditContext,
    ) -> Goal:
        if transition not in self.TRANSITIONS:
            raise AppError(400, "invalid_transition", "Unsupported goal transition")
        goal = db.scalar(
            select(Goal)
            .where(Goal.id == goal_id, Goal.student_id == student.id)
            .with_for_update()
        )
        if not goal:
            raise AppError(404, "goal_not_found", "Goal was not found")
        self._check_version(goal, expected_version)
        allowed_from, destination = self.TRANSITIONS[transition]
        if goal.status not in allowed_from:
            raise AppError(
                409,
                "invalid_goal_state",
                f"Goal cannot {transition} from status {goal.status.value}",
            )
        if transition == "activate" and (not goal.target_date or not goal.success_criteria):
            raise AppError(
                409,
                "goal_not_ready",
                "A target date and at least one success criterion are required",
            )
        before = goal_snapshot(goal)
        goal.status = destination
        now = datetime.now(UTC)
        if transition == "pause":
            goal.paused_at = now
        elif transition == "resume":
            goal.paused_at = None
        elif transition == "complete":
            goal.completed_at = now
        elif transition == "close":
            goal.closed_at = now
        goal.version += 1
        db.flush()
        self._write_version_and_audit(
            db,
            goal,
            student,
            audit_context,
            before=before,
            change_type=transition,
            reason=reason,
        )
        db.commit()
        db.refresh(goal)
        return goal

    def versions(
        self, db: Session, student_id: uuid.UUID, goal_id: uuid.UUID
    ) -> list[GoalVersion]:
        self.get_owned(db, student_id, goal_id)
        return list(
            db.scalars(
                select(GoalVersion)
                .where(GoalVersion.goal_id == goal_id)
                .order_by(GoalVersion.version.desc())
            )
        )

    @staticmethod
    def _check_version(goal: Goal, expected_version: int) -> None:
        if goal.version != expected_version:
            raise AppError(
                409,
                "version_conflict",
                "Goal was updated by another request",
                {"current_version": goal.version},
            )

    def _write_version_and_audit(
        self,
        db: Session,
        goal: Goal,
        student: User,
        audit_context: AuditContext,
        *,
        before: dict[str, Any],
        change_type: str,
        reason: str,
    ) -> None:
        after = goal_snapshot(goal)
        db.add(
            GoalVersion(
                goal_id=goal.id,
                version=goal.version,
                snapshot=after,
                changed_by_user_id=student.id,
                change_type=change_type,
                change_reason=reason,
            )
        )
        self.audit.record(
            db,
            audit_context,
            action=f"goal.{change_type}d" if change_type != "complete" else "goal.completed",
            resource_type="goal",
            resource_id=goal.id,
            student_id=student.id,
            before=before,
            after=after,
            metadata={"reason": reason},
        )


class AdminService:
    def __init__(self, audit: AuditService) -> None:
        self.audit = audit

    def list_users(
        self,
        db: Session,
        *,
        role: Role | None,
        status: UserStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[User], int]:
        filters = []
        if role:
            filters.append(User.role == role)
        if status:
            filters.append(User.status == status)
        total = db.scalar(select(func.count(User.id)).where(*filters)) or 0
        users = list(
            db.scalars(
                select(User)
                .where(*filters)
                .order_by(User.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return users, total

    def set_user_status(
        self,
        db: Session,
        admin: User,
        user_id: uuid.UUID,
        status: UserStatus,
        reason: str,
        audit_context: AuditContext,
    ) -> User:
        user = db.scalar(select(User).where(User.id == user_id).with_for_update())
        if not user:
            raise AppError(404, "user_not_found", "User was not found")
        if user.id == admin.id:
            raise AppError(409, "self_status_change", "Admins cannot change their own status")
        before = {"status": user.status.value, "auth_version": user.auth_version}
        user.status = status
        user.auth_version += 1
        db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        after = {"status": user.status.value, "auth_version": user.auth_version}
        self.audit.record(
            db,
            audit_context,
            action="admin.user_status_changed",
            resource_type="user",
            resource_id=user.id,
            student_id=user.id if user.role == Role.STUDENT else None,
            before=before,
            after=after,
            metadata={"reason": reason},
        )
        db.commit()
        db.refresh(user)
        return user

    def list_audit(
        self,
        db: Session,
        *,
        actor_id: uuid.UUID | None,
        student_id: uuid.UUID | None,
        action: str | None,
        resource_type: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AuditLog], int]:
        filters = []
        if actor_id:
            filters.append(AuditLog.actor_id == actor_id)
        if student_id:
            filters.append(AuditLog.student_id == student_id)
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        total = db.scalar(select(func.count(AuditLog.id)).where(*filters)) or 0
        logs = list(
            db.scalars(
                select(AuditLog)
                .where(*filters)
                .order_by(AuditLog.occurred_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return logs, total
