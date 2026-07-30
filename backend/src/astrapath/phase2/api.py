import uuid
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Request, status
from sqlalchemy.orm import Session

from astrapath.db import get_db
from astrapath.dependencies import make_audit_context
from astrapath.models import User
from astrapath.phase2.contracts import (
    CompetencyCreate,
    CompetencyRead,
    CompetencyUpdate,
    FeasibilityRequest,
    FeasibilityResult,
    GoalClarificationRequest,
    GoalClarificationResult,
    GoalCompetenciesResult,
    GoalGraphResult,
    GoalTemplateCreate,
    GoalTemplateRead,
    SkillGapRequest,
    SkillGapWorkflowResult,
)
from astrapath.phase2.integration import get_phase2_actor
from astrapath.phase2.service import GoalIntelligenceService

phase2_router = APIRouter(prefix="/api/v1")

DatabaseSession = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(get_phase2_actor)]
OptionalFeasibilityBody = Body(default=None)
OptionalSkillGapBody = Body(default=None)


@phase2_router.post(
    "/goals/{goal_id}/clarify",
    response_model=GoalClarificationResult,
    tags=["goal-intelligence"],
)
async def clarify_goal(
    request: Request,
    goal_id: uuid.UUID,
    payload: GoalClarificationRequest,
    db: DatabaseSession,
    actor: Actor,
) -> GoalClarificationResult:
    return await _service(request, db, actor).clarify(goal_id, actor, payload)


@phase2_router.post(
    "/goals/{goal_id}/feasibility",
    response_model=FeasibilityResult,
    tags=["goal-intelligence"],
)
async def assess_feasibility(
    request: Request,
    goal_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
    payload: FeasibilityRequest | None = OptionalFeasibilityBody,
) -> FeasibilityResult:
    return await _service(request, db, actor).feasibility(
        goal_id, actor, payload or FeasibilityRequest()
    )


@phase2_router.post(
    "/goals/{goal_id}/skill-gap",
    response_model=SkillGapWorkflowResult,
    tags=["goal-intelligence"],
)
async def analyze_skill_gap(
    request: Request,
    goal_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
    payload: SkillGapRequest | None = OptionalSkillGapBody,
) -> SkillGapWorkflowResult:
    return await _service(request, db, actor).skill_gap(
        goal_id, actor, payload or SkillGapRequest()
    )


@phase2_router.get(
    "/goals/{goal_id}/competencies",
    response_model=GoalCompetenciesResult,
    tags=["goal-intelligence"],
)
def get_goal_competencies(
    request: Request,
    goal_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
) -> GoalCompetenciesResult:
    return _service(request, db, actor).competencies(goal_id, actor)


@phase2_router.get(
    "/goals/{goal_id}/graph",
    response_model=GoalGraphResult,
    tags=["goal-intelligence"],
)
def get_goal_graph(
    request: Request,
    goal_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
) -> GoalGraphResult:
    return _service(request, db, actor).graph(goal_id, actor)


@phase2_router.post(
    "/admin/competencies",
    response_model=CompetencyRead,
    status_code=status.HTTP_201_CREATED,
    tags=["phase2-admin"],
)
def create_competency(
    request: Request,
    payload: CompetencyCreate,
    db: DatabaseSession,
    actor: Actor,
) -> CompetencyRead:
    return _service(request, db, actor).create_competency(actor, payload)


@phase2_router.patch(
    "/admin/competencies/{competency_id}",
    response_model=CompetencyRead,
    tags=["phase2-admin"],
)
def update_competency(
    request: Request,
    competency_id: uuid.UUID,
    payload: CompetencyUpdate,
    db: DatabaseSession,
    actor: Actor,
) -> CompetencyRead:
    return _service(request, db, actor).update_competency(
        competency_id, actor, payload
    )


@phase2_router.post(
    "/admin/goal-templates",
    response_model=GoalTemplateRead,
    status_code=status.HTTP_201_CREATED,
    tags=["phase2-admin"],
)
def create_goal_template(
    request: Request,
    payload: GoalTemplateCreate,
    db: DatabaseSession,
    actor: Actor,
) -> GoalTemplateRead:
    return _service(request, db, actor).create_template(actor, payload)


def _service(
    request: Request, db: Session, actor: User
) -> GoalIntelligenceService:
    audit = getattr(request.app.state, "audit_service", None)
    return GoalIntelligenceService(
        db,
        audit=audit,
        audit_context=make_audit_context(request, actor) if audit else None,
    )
