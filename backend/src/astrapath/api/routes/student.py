import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from astrapath.agents.kernel import calculate_profile_completeness
from astrapath.db import get_db
from astrapath.dependencies import make_audit_context, require_student
from astrapath.enums import GoalStatus
from astrapath.errors import AppError
from astrapath.models import (
    Goal,
    GoalVersion,
    StudentProfile,
    User,
    WorkflowState,
)
from astrapath.schemas import (
    GoalClarificationResponse,
    GoalCreate,
    GoalList,
    GoalRead,
    GoalTransitionRequest,
    GoalUpdate,
    GoalVersionRead,
    OnboardingRequest,
    ProfileCompletenessRead,
    ProfileUpdate,
    StudentProfileRead,
    WorkflowRead,
)
from astrapath.services import GoalService, ProfileService, profile_snapshot
from astrapath.workflows.goal_clarification import run_goal_clarification_workflow

router = APIRouter()


def _profiles(request: Request) -> ProfileService:
    return cast(ProfileService, request.app.state.profile_service)


def _goals(request: Request) -> GoalService:
    return cast(GoalService, request.app.state.goal_service)


@router.post(
    "/onboarding",
    response_model=StudentProfileRead,
    status_code=status.HTTP_201_CREATED,
)
def onboarding(
    request: Request,
    payload: OnboardingRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> StudentProfile:
    return _profiles(request).create_onboarding(
        db,
        student,
        payload,
        make_audit_context(request, student),
    )


@router.get("/profile", response_model=StudentProfileRead)
def get_profile(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> StudentProfile:
    return _profiles(request).get(db, student.id)


@router.patch("/profile", response_model=StudentProfileRead)
def update_profile(
    request: Request,
    payload: ProfileUpdate,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> StudentProfile:
    return _profiles(request).update(
        db,
        student,
        payload,
        make_audit_context(request, student),
    )


@router.get("/profile/completeness", response_model=ProfileCompletenessRead)
def profile_completeness(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> ProfileCompletenessRead:
    profile = _profiles(request).get(db, student.id)
    completeness, missing, warnings = calculate_profile_completeness(
        profile_snapshot(profile)
    )
    return ProfileCompletenessRead(
        completeness=completeness,
        missing_fields=missing,
        warnings=warnings,
        ready_for_goal_planning=completeness >= 0.7 and bool(profile.availability),
    )


@router.post("/goals", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_goal(
    request: Request,
    payload: GoalCreate,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> Goal:
    return _goals(request).create(
        db,
        student,
        payload,
        make_audit_context(request, student),
    )


@router.get("/goals", response_model=GoalList)
def list_goals(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    goal_status: Annotated[GoalStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> GoalList:
    items, total = _goals(request).list_owned(
        db,
        student.id,
        status=goal_status,
        limit=limit,
        offset=offset,
    )
    return GoalList(items=items, total=total, limit=limit, offset=offset)


@router.get("/goals/{goal_id}", response_model=GoalRead)
def get_goal(
    request: Request,
    goal_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> Goal:
    return _goals(request).get_owned(db, student.id, goal_id)


@router.patch("/goals/{goal_id}", response_model=GoalRead)
def update_goal(
    request: Request,
    goal_id: uuid.UUID,
    payload: GoalUpdate,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> Goal:
    return _goals(request).update(
        db,
        student,
        goal_id,
        payload,
        make_audit_context(request, student),
    )


@router.get("/goals/{goal_id}/versions", response_model=list[GoalVersionRead])
def goal_versions(
    request: Request,
    goal_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> list[GoalVersion]:
    return _goals(request).versions(db, student.id, goal_id)


def _transition_goal(
    request: Request,
    db: Session,
    student: User,
    goal_id: uuid.UUID,
    payload: GoalTransitionRequest,
    transition: str,
) -> Goal:
    return _goals(request).transition(
        db,
        student,
        goal_id,
        transition=transition,
        expected_version=payload.expected_version,
        reason=payload.reason,
        audit_context=make_audit_context(request, student),
    )


@router.post("/goals/{goal_id}/activate", response_model=GoalRead)
def activate_goal(
    request: Request,
    goal_id: uuid.UUID,
    payload: GoalTransitionRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> Goal:
    return _transition_goal(request, db, student, goal_id, payload, "activate")


@router.post("/goals/{goal_id}/pause", response_model=GoalRead)
def pause_goal(
    request: Request,
    goal_id: uuid.UUID,
    payload: GoalTransitionRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> Goal:
    return _transition_goal(request, db, student, goal_id, payload, "pause")


@router.post("/goals/{goal_id}/resume", response_model=GoalRead)
def resume_goal(
    request: Request,
    goal_id: uuid.UUID,
    payload: GoalTransitionRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> Goal:
    return _transition_goal(request, db, student, goal_id, payload, "resume")


@router.post("/goals/{goal_id}/complete", response_model=GoalRead)
def complete_goal(
    request: Request,
    goal_id: uuid.UUID,
    payload: GoalTransitionRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> Goal:
    return _transition_goal(request, db, student, goal_id, payload, "complete")


@router.post("/goals/{goal_id}/close", response_model=GoalRead)
def close_goal(
    request: Request,
    goal_id: uuid.UUID,
    payload: GoalTransitionRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> Goal:
    return _transition_goal(request, db, student, goal_id, payload, "close")


@router.post("/goals/{goal_id}/clarify", response_model=GoalClarificationResponse)
async def clarify_goal(
    request: Request,
    goal_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> GoalClarificationResponse:
    goal = _goals(request).get_owned(db, student.id, goal_id)
    profile = _profiles(request).get(db, student.id)
    correlation_id = request.headers.get(
        "x-correlation-id", getattr(request.state, "request_id", str(uuid.uuid4()))
    )
    workflow, clarification = await run_goal_clarification_workflow(
        db,
        student,
        profile,
        goal,
        correlation_id=correlation_id,
        supervisor=request.app.state.supervisor,
        audit=request.app.state.audit_service,
        audit_context=make_audit_context(request, student),
    )
    return GoalClarificationResponse(
        workflow=workflow,
        summary=clarification.summary,
        clarification_questions=clarification.data["clarification_questions"],
        confidence=clarification.confidence,
    )


@router.get("/workflows/{workflow_id}", response_model=WorkflowRead)
def get_workflow(
    workflow_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> WorkflowState:
    workflow = db.scalar(
        select(WorkflowState).where(
            WorkflowState.id == workflow_id,
            WorkflowState.student_id == student.id,
        )
    )
    if not workflow:
        raise AppError(404, "workflow_not_found", "Workflow was not found")
    return workflow
