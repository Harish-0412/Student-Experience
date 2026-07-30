import uuid
from datetime import date, timedelta
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from astrapath.db import get_db
from astrapath.dependencies import make_audit_context, require_student
from astrapath.models import User
from astrapath.phase3.contracts import (
    CalendarRead,
    DailyPlanRead,
    PlanDecisionRequest,
    PlanGenerationRequest,
    PlanRead,
    TaskEditRequest,
    TaskStatusRequest,
)
from astrapath.phase3.service import PlanningService

phase3_router = APIRouter(prefix="/api/v1")


def _planning(request: Request) -> PlanningService:
    return cast(PlanningService, request.app.state.planning_service)


def _correlation_id(request: Request) -> str:
    return request.headers.get(
        "x-correlation-id",
        getattr(request.state, "request_id", str(uuid.uuid4())),
    )


@phase3_router.post(
    "/goals/{goal_id}/plan",
    response_model=PlanRead,
    status_code=status.HTTP_201_CREATED,
    tags=["planning"],
)
async def generate_plan(
    request: Request,
    goal_id: uuid.UUID,
    payload: PlanGenerationRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> PlanRead:
    return await _planning(request).generate_plan(
        db,
        student,
        goal_id,
        payload,
        audit_context=make_audit_context(request, student),
        correlation_id=_correlation_id(request),
    )


@phase3_router.get(
    "/goals/{goal_id}/plan",
    response_model=PlanRead,
    tags=["planning"],
)
def get_plan(
    request: Request,
    goal_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> PlanRead:
    return _planning(request).get_plan(db, student, goal_id)


@phase3_router.post(
    "/goals/{goal_id}/schedule",
    response_model=PlanRead,
    tags=["planning"],
)
async def regenerate_schedule(
    request: Request,
    goal_id: uuid.UUID,
    payload: PlanGenerationRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> PlanRead:
    return await _planning(request).regenerate_schedule(
        db,
        student,
        goal_id,
        payload,
        audit_context=make_audit_context(request, student),
        correlation_id=_correlation_id(request),
    )


@phase3_router.patch(
    "/goals/{goal_id}/plan/tasks/{task_id}",
    response_model=PlanRead,
    tags=["planning"],
)
async def edit_plan_task(
    request: Request,
    goal_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: TaskEditRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> PlanRead:
    return await _planning(request).edit_task(
        db,
        student,
        goal_id,
        task_id,
        payload,
        audit_context=make_audit_context(request, student),
        correlation_id=_correlation_id(request),
    )


@phase3_router.patch(
    "/goals/{goal_id}/plan/tasks/{task_id}/status",
    response_model=PlanRead,
    tags=["planning"],
)
def update_task_status(
    request: Request,
    goal_id: uuid.UUID,
    task_id: uuid.UUID,
    payload: TaskStatusRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> PlanRead:
    return _planning(request).update_task_status(
        db,
        student,
        goal_id,
        task_id,
        payload,
        audit_context=make_audit_context(request, student),
    )


@phase3_router.post(
    "/goals/{goal_id}/plan/decision",
    response_model=PlanRead,
    tags=["planning"],
)
def decide_plan(
    request: Request,
    goal_id: uuid.UUID,
    payload: PlanDecisionRequest,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
) -> PlanRead:
    return _planning(request).decide_plan(
        db,
        student,
        goal_id,
        payload,
        audit_context=make_audit_context(request, student),
    )


@phase3_router.get(
    "/goals/{goal_id}/calendar",
    response_model=CalendarRead,
    tags=["planning"],
)
def get_calendar(
    request: Request,
    goal_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    starts_on: Annotated[date | None, Query()] = None,
    ends_on: Annotated[date | None, Query()] = None,
) -> CalendarRead:
    resolved_start = starts_on or date.today()
    resolved_end = ends_on or resolved_start + timedelta(days=6)
    return _planning(request).calendar(
        db, student, goal_id, resolved_start, resolved_end
    )


@phase3_router.get(
    "/student/daily-plan",
    response_model=DailyPlanRead,
    tags=["planning"],
)
async def get_daily_plan(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    student: Annotated[User, Depends(require_student)],
    plan_date: Annotated[date | None, Query(alias="date")] = None,
) -> DailyPlanRead:
    return await _planning(request).daily_plan(
        db,
        student,
        plan_date or date.today(),
        audit_context=make_audit_context(request, student),
        correlation_id=_correlation_id(request),
    )
