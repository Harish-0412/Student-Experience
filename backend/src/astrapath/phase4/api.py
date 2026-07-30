import uuid
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from astrapath.db import get_db
from astrapath.dependencies import make_audit_context
from astrapath.errors import AppError
from astrapath.models import User
from astrapath.phase4.agents.base import AgentDescriptor
from astrapath.phase4.contracts import (
    AdminEvidenceDecision,
    AgentRunRead,
    AssessmentAttemptCreate,
    AssessmentAttemptRead,
    AssessmentCreate,
    AssessmentGenerateRequest,
    AssessmentRead,
    AssessmentStatusUpdate,
    CoachingRequest,
    CoachingResponse,
    EvidenceRead,
    EvidenceSubmissionCreate,
    EvidenceVerificationReport,
    ExecutionContextRead,
    ExecutionContextSync,
    FocusSessionComplete,
    FocusSessionRead,
    FocusSessionStart,
    MasteryEstimateRead,
    NotificationRead,
    ProgressSnapshotRead,
    ReplanDecision,
    ReplanProposalRead,
    ReplanRequest,
    ResourceBundle,
    ResourceCreate,
    ResourceRead,
    ResourceRecommendationRequest,
    ResourceStatusUpdate,
    RiskRead,
    RiskScanRequest,
    RiskScanResult,
    StorageReceiptCreate,
    StorageReceiptRead,
    TutorMessageRequest,
    TutorResponse,
)
from astrapath.phase4.integration import get_phase4_actor
from astrapath.phase4.phase3_bridge import Phase3Phase4Bridge
from astrapath.phase4.registry import build_phase4_registry
from astrapath.phase4.service import Phase4Service

phase4_router = APIRouter(prefix="/api/v1")

DatabaseSession = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(get_phase4_actor)]


@phase4_router.post(
    "/admin/phase4/resources",
    response_model=ResourceRead,
    status_code=status.HTTP_201_CREATED,
    tags=["phase4-admin"],
)
def create_resource(
    request: Request,
    payload: ResourceCreate,
    db: DatabaseSession,
    actor: Actor,
) -> ResourceRead:
    return _service(request, db, actor).create_resource(actor, payload)


@phase4_router.patch(
    "/admin/phase4/resources/{resource_id}/status",
    response_model=ResourceRead,
    tags=["phase4-admin"],
)
def update_resource_status(
    request: Request,
    resource_id: uuid.UUID,
    payload: ResourceStatusUpdate,
    db: DatabaseSession,
    actor: Actor,
) -> ResourceRead:
    return _service(request, db, actor).update_resource_status(
        actor, resource_id, payload
    )


@phase4_router.post(
    "/student/goals/{goal_id}/resource-recommendations",
    response_model=ResourceBundle,
    tags=["phase4-student"],
)
async def recommend_resources(
    request: Request,
    goal_id: uuid.UUID,
    payload: ResourceRecommendationRequest,
    db: DatabaseSession,
    actor: Actor,
) -> ResourceBundle:
    return await _service(request, db, actor).recommend_resources(
        actor, goal_id, payload
    )


@phase4_router.post(
    "/student/focus-sessions",
    response_model=FocusSessionRead,
    status_code=status.HTTP_201_CREATED,
    tags=["phase4-student"],
)
async def start_focus_session(
    request: Request,
    payload: FocusSessionStart,
    db: DatabaseSession,
    actor: Actor,
) -> FocusSessionRead:
    return await _service(request, db, actor).start_focus_session(actor, payload)


@phase4_router.post(
    "/student/focus-sessions/{session_id}/complete",
    response_model=FocusSessionRead,
    tags=["phase4-student"],
)
async def complete_focus_session(
    request: Request,
    session_id: uuid.UUID,
    payload: FocusSessionComplete,
    db: DatabaseSession,
    actor: Actor,
) -> FocusSessionRead:
    return await _service(request, db, actor).complete_focus_session(
        actor, session_id, payload
    )


@phase4_router.post(
    "/student/tutor/messages",
    response_model=TutorResponse,
    tags=["phase4-student"],
)
async def tutor_message(
    request: Request,
    payload: TutorMessageRequest,
    db: DatabaseSession,
    actor: Actor,
) -> TutorResponse:
    return await _service(request, db, actor).tutor_message(actor, payload)


@phase4_router.post(
    "/admin/phase4/assessments",
    response_model=AssessmentRead,
    status_code=status.HTTP_201_CREATED,
    tags=["phase4-admin"],
)
def create_assessment(
    request: Request,
    payload: AssessmentCreate,
    db: DatabaseSession,
    actor: Actor,
) -> AssessmentRead:
    return _service(request, db, actor).create_assessment(actor, payload)


@phase4_router.post(
    "/admin/phase4/assessments/generate",
    response_model=AssessmentRead,
    status_code=status.HTTP_201_CREATED,
    tags=["phase4-admin"],
)
async def generate_assessment(
    request: Request,
    payload: AssessmentGenerateRequest,
    db: DatabaseSession,
    actor: Actor,
) -> AssessmentRead:
    return await _service(request, db, actor).generate_assessment(actor, payload)


@phase4_router.patch(
    "/admin/phase4/assessments/{assessment_id}/status",
    response_model=AssessmentRead,
    tags=["phase4-admin"],
)
def update_assessment_status(
    request: Request,
    assessment_id: uuid.UUID,
    payload: AssessmentStatusUpdate,
    db: DatabaseSession,
    actor: Actor,
) -> AssessmentRead:
    return _service(request, db, actor).update_assessment_status(
        actor, assessment_id, payload
    )


@phase4_router.get(
    "/student/goals/{goal_id}/assessments",
    response_model=list[AssessmentRead],
    tags=["phase4-student"],
)
def list_assessments(
    request: Request,
    goal_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
) -> list[AssessmentRead]:
    return _service(request, db, actor).list_assessments(actor, goal_id)


@phase4_router.post(
    "/student/assessments/{assessment_id}/attempts",
    response_model=AssessmentAttemptRead,
    status_code=status.HTTP_201_CREATED,
    tags=["phase4-student"],
)
async def submit_assessment(
    request: Request,
    assessment_id: uuid.UUID,
    payload: AssessmentAttemptCreate,
    db: DatabaseSession,
    actor: Actor,
) -> AssessmentAttemptRead:
    return await _service(request, db, actor).submit_assessment(
        actor, assessment_id, payload
    )


@phase4_router.post(
    "/admin/phase4/storage-receipts",
    response_model=StorageReceiptRead,
    status_code=status.HTTP_201_CREATED,
    tags=["phase4-admin"],
)
def register_storage_receipt(
    request: Request,
    payload: StorageReceiptCreate,
    db: DatabaseSession,
    actor: Actor,
) -> StorageReceiptRead:
    return _service(request, db, actor).register_storage_receipt(actor, payload)


@phase4_router.post(
    "/student/evidence",
    response_model=EvidenceVerificationReport,
    status_code=status.HTTP_201_CREATED,
    tags=["phase4-student"],
)
async def submit_evidence(
    request: Request,
    payload: EvidenceSubmissionCreate,
    db: DatabaseSession,
    actor: Actor,
) -> EvidenceVerificationReport:
    return await _service(request, db, actor).submit_evidence(actor, payload)


@phase4_router.get(
    "/student/evidence",
    response_model=list[EvidenceRead],
    tags=["phase4-student"],
)
def list_evidence(
    request: Request,
    db: DatabaseSession,
    actor: Actor,
    goal_id: uuid.UUID | None = None,
) -> list[EvidenceRead]:
    return _service(request, db, actor).list_evidence(actor, goal_id)


@phase4_router.get(
    "/student/evidence/{evidence_id}",
    response_model=EvidenceRead,
    tags=["phase4-student"],
)
def get_evidence(
    request: Request,
    evidence_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
) -> EvidenceRead:
    return _service(request, db, actor).get_evidence(actor, evidence_id)


@phase4_router.get(
    "/admin/phase4/evidence/review-queue",
    response_model=list[EvidenceRead],
    tags=["phase4-admin"],
)
def list_evidence_review_queue(
    request: Request,
    db: DatabaseSession,
    actor: Actor,
) -> list[EvidenceRead]:
    return _service(request, db, actor).list_evidence_review_queue(actor)


@phase4_router.post(
    "/admin/phase4/evidence/{evidence_id}/decision",
    response_model=EvidenceRead,
    tags=["phase4-admin"],
)
async def decide_evidence(
    request: Request,
    evidence_id: uuid.UUID,
    payload: AdminEvidenceDecision,
    db: DatabaseSession,
    actor: Actor,
) -> EvidenceRead:
    return await _service(request, db, actor).decide_evidence(
        actor, evidence_id, payload
    )


@phase4_router.put(
    "/admin/phase4/goals/{goal_id}/execution-context",
    response_model=ExecutionContextRead,
    tags=["phase4-admin"],
)
async def sync_execution_context(
    request: Request,
    goal_id: uuid.UUID,
    payload: ExecutionContextSync,
    db: DatabaseSession,
    actor: Actor,
) -> ExecutionContextRead:
    return await _service(request, db, actor).sync_execution_context(
        actor, goal_id, payload
    )


@phase4_router.post(
    "/student/goals/{goal_id}/progress/rebuild",
    response_model=ProgressSnapshotRead,
    tags=["phase4-student"],
)
async def rebuild_progress(
    request: Request,
    goal_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
) -> ProgressSnapshotRead:
    return await _service(request, db, actor).rebuild_progress(actor, goal_id)


@phase4_router.get(
    "/student/goals/{goal_id}/progress",
    response_model=ProgressSnapshotRead,
    tags=["phase4-student"],
)
def latest_progress(
    request: Request,
    goal_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
) -> ProgressSnapshotRead:
    return _service(request, db, actor).latest_progress(actor, goal_id)


@phase4_router.post(
    "/student/goals/{goal_id}/mastery/{competency_ref}/rebuild",
    response_model=MasteryEstimateRead,
    tags=["phase4-student"],
)
async def rebuild_mastery(
    request: Request,
    goal_id: uuid.UUID,
    competency_ref: str,
    db: DatabaseSession,
    actor: Actor,
) -> MasteryEstimateRead:
    return await _service(request, db, actor).rebuild_mastery(
        actor, goal_id, competency_ref
    )


@phase4_router.get(
    "/student/goals/{goal_id}/mastery",
    response_model=list[MasteryEstimateRead],
    tags=["phase4-student"],
)
def list_mastery(
    request: Request,
    goal_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
) -> list[MasteryEstimateRead]:
    return _service(request, db, actor).list_mastery(actor, goal_id)


@phase4_router.post(
    "/student/coaching",
    response_model=CoachingResponse,
    tags=["phase4-student"],
)
async def coach(
    request: Request,
    payload: CoachingRequest,
    db: DatabaseSession,
    actor: Actor,
) -> CoachingResponse:
    return await _service(request, db, actor).coach(actor, payload)


@phase4_router.post(
    "/student/goals/{goal_id}/risks/scan",
    response_model=RiskScanResult,
    tags=["phase4-student"],
)
async def scan_risks(
    request: Request,
    goal_id: uuid.UUID,
    payload: RiskScanRequest,
    db: DatabaseSession,
    actor: Actor,
) -> RiskScanResult:
    return await _service(request, db, actor).scan_risks(actor, goal_id, payload)


@phase4_router.get(
    "/student/goals/{goal_id}/risks",
    response_model=list[RiskRead],
    tags=["phase4-student"],
)
def list_risks(
    request: Request,
    goal_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
) -> list[RiskRead]:
    return _service(request, db, actor).list_risks(actor, goal_id)


@phase4_router.post(
    "/student/goals/{goal_id}/replans",
    response_model=ReplanProposalRead,
    status_code=status.HTTP_201_CREATED,
    tags=["phase4-student"],
)
async def propose_replan(
    request: Request,
    goal_id: uuid.UUID,
    payload: ReplanRequest,
    db: DatabaseSession,
    actor: Actor,
) -> ReplanProposalRead:
    return await _service(request, db, actor).propose_replan(actor, goal_id, payload)


@phase4_router.post(
    "/student/replans/{proposal_id}/decision",
    response_model=ReplanProposalRead,
    tags=["phase4-student"],
)
async def decide_replan(
    request: Request,
    proposal_id: uuid.UUID,
    payload: ReplanDecision,
    db: DatabaseSession,
    actor: Actor,
) -> ReplanProposalRead:
    proposal = _service(request, db, actor).decide_replan(
        actor, proposal_id, payload
    )
    bridge = _phase3_bridge(request)
    if (
        payload.decision == "approve"
        and proposal.status.value == "approved_pending_phase3"
        and bridge
    ):
        return await bridge.apply_pending_replan(
            db,
            actor,
            proposal.id,
            audit_context=make_audit_context(request, actor),
            correlation_id=request.headers.get(
                "x-correlation-id",
                getattr(request.state, "request_id", str(uuid.uuid4())),
            ),
        )
    return proposal


@phase4_router.post(
    "/student/replans/{proposal_id}/apply",
    response_model=ReplanProposalRead,
    tags=["phase4-student"],
)
async def apply_replan(
    request: Request,
    proposal_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
) -> ReplanProposalRead:
    bridge = _phase3_bridge(request)
    if not bridge:
        raise AppError(
            409,
            "phase3_bridge_unavailable",
            "Phase 3 integration is not available in this application",
        )
    return await bridge.apply_pending_replan(
        db,
        actor,
        proposal_id,
        audit_context=make_audit_context(request, actor),
        correlation_id=request.headers.get(
            "x-correlation-id",
            getattr(request.state, "request_id", str(uuid.uuid4())),
        ),
    )


@phase4_router.post(
    "/admin/phase4/replans/{proposal_id}/decision",
    response_model=ReplanProposalRead,
    tags=["phase4-admin"],
)
def admin_decide_replan(
    request: Request,
    proposal_id: uuid.UUID,
    payload: ReplanDecision,
    db: DatabaseSession,
    actor: Actor,
) -> ReplanProposalRead:
    return _service(request, db, actor).admin_decide_replan(
        actor, proposal_id, payload
    )


@phase4_router.get(
    "/student/notifications",
    response_model=list[NotificationRead],
    tags=["phase4-student"],
)
def list_notifications(
    request: Request,
    db: DatabaseSession,
    actor: Actor,
    unread_only: Annotated[bool, Query()] = False,
) -> list[NotificationRead]:
    return _service(request, db, actor).list_notifications(
        actor, unread_only=unread_only
    )


@phase4_router.post(
    "/student/notifications/{notification_id}/read",
    response_model=NotificationRead,
    tags=["phase4-student"],
)
def mark_notification_read(
    request: Request,
    notification_id: uuid.UUID,
    db: DatabaseSession,
    actor: Actor,
) -> NotificationRead:
    return _service(request, db, actor).mark_notification_read(
        actor, notification_id
    )


@phase4_router.get(
    "/admin/phase4/agents",
    response_model=list[AgentDescriptor],
    tags=["phase4-admin"],
)
def list_agents(
    request: Request,
    db: DatabaseSession,
    actor: Actor,
) -> list[AgentDescriptor]:
    service = _service(request, db, actor)
    service._require_admin(actor)
    return service.registry.descriptors()


@phase4_router.get(
    "/admin/phase4/agent-runs",
    response_model=list[AgentRunRead],
    tags=["phase4-admin"],
)
def list_agent_runs(
    request: Request,
    db: DatabaseSession,
    actor: Actor,
) -> list[AgentRunRead]:
    return [
        AgentRunRead.model_validate(item)
        for item in _service(request, db, actor).list_agent_runs(actor)
    ]


def _service(request: Request, db: Session, actor: User) -> Phase4Service:
    audit = getattr(request.app.state, "audit_service", None)
    registry = getattr(request.app.state, "phase4_registry", None)
    return Phase4Service(
        db,
        audit=audit,
        audit_context=make_audit_context(request, actor) if audit else None,
        registry=registry or build_phase4_registry(),
    )


def _phase3_bridge(request: Request) -> Phase3Phase4Bridge | None:
    bridge = getattr(request.app.state, "phase3_phase4_bridge", None)
    return cast(Phase3Phase4Bridge | None, bridge)
