import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from astrapath.audit import AuditContext, AuditService
from astrapath.db import utc_now
from astrapath.enums import Role
from astrapath.errors import AppError
from astrapath.models import Goal, User
from astrapath.phase4.agents.assessment import (
    AssessmentGenerationAgent,
    AssessmentScoreInput,
)
from astrapath.phase4.agents.evidence import EvidenceVerificationInput
from astrapath.phase4.agents.focus import FocusCoachInput
from astrapath.phase4.agents.intelligence import (
    CoachingAgentInput,
    MasteryComputationInput,
    ProgressComputationInput,
    ReplanAgentInput,
    RiskDetectionInput,
    RiskFinding,
)
from astrapath.phase4.agents.resources import ResourceCurationInput
from astrapath.phase4.agents.tutor import TutorAgentInput
from astrapath.phase4.contracts import (
    AdminEvidenceDecision,
    AssessmentAttemptCreate,
    AssessmentAttemptRead,
    AssessmentCreate,
    AssessmentGenerateRequest,
    AssessmentQuestionInput,
    AssessmentQuestionPublic,
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
from astrapath.phase4.enums import (
    AgentExecutionStatus,
    AssessmentStatus,
    AttemptStatus,
    EvidenceStatus,
    FocusSessionStatus,
    ReplanStatus,
    ResourceStatus,
    RiskStatus,
)
from astrapath.phase4.models import (
    AssessmentAttempt,
    AssessmentDefinition,
    CoachingRecord,
    EvidenceReview,
    EvidenceSubmission,
    ExecutionContext,
    FocusSession,
    LearningResource,
    MasteryEstimate,
    Notification,
    Phase4AgentRun,
    ProgressEvent,
    ProgressSnapshot,
    ReplanProposal,
    ResourceRecommendation,
    Risk,
    StorageReceipt,
    TutorMessage,
    TutorThread,
)
from astrapath.phase4.registry import (
    Phase4AgentRunner,
    Phase4Registry,
    build_phase4_registry,
)


def _payload_hash(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _assessment_read(definition: AssessmentDefinition) -> AssessmentRead:
    public_questions = [
        AssessmentQuestionPublic(
            id=question["id"],
            prompt=question["prompt"],
            kind=question["kind"],
            options=question.get("options", []),
            points=question["points"],
        )
        for question in definition.questions
    ]
    return AssessmentRead(
        id=definition.id,
        goal_id=definition.goal_id,
        competency_ref=definition.competency_ref,
        title=definition.title,
        assessment_type=definition.assessment_type,
        instructions=definition.instructions,
        questions=public_questions,
        rubric=definition.rubric,
        max_score=definition.max_score,
        passing_percentage=definition.passing_percentage,
        time_limit_minutes=definition.time_limit_minutes,
        status=definition.status,
        version=definition.version,
        created_at=definition.created_at,
        updated_at=definition.updated_at,
    )


class Phase4Service:
    def __init__(
        self,
        db: Session,
        *,
        audit: AuditService | None = None,
        audit_context: AuditContext | None = None,
        registry: Phase4Registry | None = None,
        runner: Phase4AgentRunner | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.audit_context = audit_context
        self.registry = registry or build_phase4_registry()
        self.runner = runner or Phase4AgentRunner()

    def create_resource(self, actor: User, payload: ResourceCreate) -> ResourceRead:
        self._require_admin(actor)
        existing = self.db.scalar(
            select(LearningResource).where(LearningResource.url == str(payload.url))
        )
        if existing:
            raise AppError(409, "resource_exists", "A resource with this URL already exists")
        values = payload.model_dump(mode="json")
        metadata = values.pop("metadata")
        resource = LearningResource(
            **values,
            metadata_json=metadata,
            status=ResourceStatus.DRAFT,
            created_by_user_id=actor.id,
        )
        self.db.add(resource)
        self.db.flush()
        self._audit(
            actor,
            "phase4.resource_created",
            "learning_resource",
            resource.id,
            after={"title": resource.title, "status": _enum_value(resource.status)},
        )
        self.db.commit()
        self.db.refresh(resource)
        return ResourceRead.model_validate(resource)

    def update_resource_status(
        self,
        actor: User,
        resource_id: uuid.UUID,
        payload: ResourceStatusUpdate,
    ) -> ResourceRead:
        self._require_admin(actor)
        resource = self.db.scalar(
            select(LearningResource)
            .where(LearningResource.id == resource_id)
            .with_for_update()
        )
        if not resource:
            raise AppError(404, "resource_not_found", "Learning resource was not found")
        if resource.version != payload.expected_version:
            raise AppError(
                409,
                "version_conflict",
                "Learning resource was updated by another request",
                {"current_version": resource.version},
            )
        before = {"status": _enum_value(resource.status), "version": resource.version}
        resource.status = payload.status
        resource.version += 1
        self._audit(
            actor,
            "phase4.resource_status_changed",
            "learning_resource",
            resource.id,
            before=before,
            after={"status": _enum_value(resource.status), "version": resource.version},
            metadata={"reason": payload.reason},
        )
        self.db.commit()
        self.db.refresh(resource)
        return ResourceRead.model_validate(resource)

    async def recommend_resources(
        self,
        actor: User,
        goal_id: uuid.UUID,
        payload: ResourceRecommendationRequest,
    ) -> ResourceBundle:
        goal = self._require_goal(actor, goal_id, student_only=True)
        candidates = list(
            self.db.scalars(
                select(LearningResource).where(
                    LearningResource.competency_ref == payload.competency_ref,
                    LearningResource.status == ResourceStatus.APPROVED,
                )
            )
        )
        request_key = _payload_hash(
            {
                "request": payload.model_dump(mode="json"),
                "catalog": [
                    {
                        "id": str(item.id),
                        "version": item.version,
                        "status": _enum_value(item.status),
                        "quality_score": item.quality_score,
                    }
                    for item in sorted(candidates, key=lambda value: str(value.id))
                ],
            }
        )
        agent = self.registry.get("ResourceCurationAgent")
        result = cast(
            ResourceBundle,
            await self.runner.run(
                self.db,
                actor,
                student_id=actor.id,
                goal_id=goal.id,
                agent=agent,
                input_data=ResourceCurationInput(
                    goal_id=goal.id,
                    request=payload,
                    candidates=[
                        ResourceRead.model_validate(item) for item in candidates
                    ],
                ),
                idempotency_key=f"resource:{actor.id}:{goal.id}:{request_key}",
            ),
        )
        for item in result.resources:
            existing = self.db.scalar(
                select(ResourceRecommendation).where(
                    ResourceRecommendation.student_id == actor.id,
                    ResourceRecommendation.goal_id == goal.id,
                    ResourceRecommendation.resource_id == item.resource.id,
                    ResourceRecommendation.request_key == request_key,
                )
            )
            if not existing:
                self.db.add(
                    ResourceRecommendation(
                        student_id=actor.id,
                        goal_id=goal.id,
                        resource_id=item.resource.id,
                        competency_ref=payload.competency_ref,
                        request_key=request_key,
                        rank=item.rank,
                        relevance_score=item.relevance_score,
                        selection_reason=item.selection_reason,
                    )
                )
        self._audit(
            actor,
            "phase4.resource_bundle_created",
            "goal",
            goal.id,
            student_id=actor.id,
            after={
                "competency_ref": payload.competency_ref,
                "resource_ids": [str(item.resource.id) for item in result.resources],
            },
        )
        self.db.commit()
        return result

    async def start_focus_session(
        self, actor: User, payload: FocusSessionStart
    ) -> FocusSessionRead:
        goal = self._require_goal(actor, payload.goal_id, student_only=True)
        existing = self.db.scalar(
            select(FocusSession).where(
                FocusSession.idempotency_key == payload.idempotency_key
            )
        )
        if existing:
            if existing.student_id != actor.id:
                raise AppError(409, "idempotency_conflict", "Idempotency key is in use")
            if (
                existing.goal_id != goal.id
                or existing.task_ref != payload.task_ref
                or existing.milestone_ref != payload.milestone_ref
                or existing.objective != payload.objective
                or existing.planned_minutes != payload.planned_minutes
            ):
                raise AppError(
                    409,
                    "idempotency_conflict",
                    "Idempotency key was reused with different focus session input",
                )
            return FocusSessionRead.model_validate(existing)
        active = self.db.scalar(
            select(FocusSession).where(
                FocusSession.student_id == actor.id,
                FocusSession.status == FocusSessionStatus.ACTIVE,
            )
        )
        if active:
            raise AppError(
                409,
                "focus_session_active",
                "Complete or abandon the active focus session first",
                {"session_id": str(active.id)},
            )
        session = FocusSession(
            student_id=actor.id,
            goal_id=goal.id,
            task_ref=payload.task_ref,
            milestone_ref=payload.milestone_ref,
            objective=payload.objective,
            planned_minutes=payload.planned_minutes,
            idempotency_key=payload.idempotency_key,
        )
        self.db.add(session)
        self.db.flush()
        await self.runner.run(
            self.db,
            actor,
            student_id=actor.id,
            goal_id=goal.id,
            agent=self.registry.get("FocusSessionCoachAgent"),
            input_data=FocusCoachInput(session_id=session.id, start=payload),
            idempotency_key=f"focus-agent:start:{session.id}",
        )
        self._audit(
            actor,
            "phase4.focus_session_started",
            "focus_session",
            session.id,
            student_id=actor.id,
            after={
                "goal_id": str(goal.id),
                "task_ref": payload.task_ref,
                "planned_minutes": payload.planned_minutes,
            },
        )
        self.db.commit()
        self.db.refresh(session)
        return FocusSessionRead.model_validate(session)

    async def complete_focus_session(
        self,
        actor: User,
        session_id: uuid.UUID,
        payload: FocusSessionComplete,
    ) -> FocusSessionRead:
        session = self.db.scalar(
            select(FocusSession)
            .where(FocusSession.id == session_id, FocusSession.student_id == actor.id)
            .with_for_update()
        )
        if not session:
            raise AppError(404, "focus_session_not_found", "Focus session was not found")
        if session.status != FocusSessionStatus.ACTIVE:
            raise AppError(409, "focus_session_closed", "Focus session is already closed")
        if session.version != payload.expected_version:
            raise AppError(
                409,
                "version_conflict",
                "Focus session was updated by another request",
                {"current_version": session.version},
            )
        session.actual_minutes = payload.actual_minutes
        session.distraction_count = payload.distraction_count
        session.blocker_notes = payload.blocker_notes
        session.reflection = payload.reflection
        session.accomplished = payload.accomplished
        session.status = FocusSessionStatus.COMPLETED
        session.ended_at = utc_now()
        session.version += 1
        start_payload = FocusSessionStart(
            goal_id=session.goal_id,
            task_ref=session.task_ref,
            milestone_ref=session.milestone_ref,
            objective=session.objective,
            planned_minutes=session.planned_minutes,
            idempotency_key=session.idempotency_key,
        )
        await self.runner.run(
            self.db,
            actor,
            student_id=actor.id,
            goal_id=session.goal_id,
            agent=self.registry.get("FocusSessionCoachAgent"),
            input_data=FocusCoachInput(
                session_id=session.id,
                start=start_payload,
                completion=payload,
            ),
            idempotency_key=f"focus-agent:complete:{session.id}:{session.version}",
        )
        self._progress_event(
            actor.id,
            session.goal_id,
            event_type="focus_session.completed",
            source_type="focus_session",
            source_id=str(session.id),
            activity_points=min(payload.actual_minutes / 30, 4),
            mastery_signal=None,
            payload={
                "actual_minutes": payload.actual_minutes,
                "accomplished": payload.accomplished,
                "blockers": payload.blocker_notes,
            },
            idempotency_key=f"progress:focus:{session.id}",
        )
        self.db.flush()
        self._audit(
            actor,
            "phase4.focus_session_completed",
            "focus_session",
            session.id,
            student_id=actor.id,
            after={
                "actual_minutes": payload.actual_minutes,
                "accomplished": payload.accomplished,
                "blocker_count": len(payload.blocker_notes),
            },
        )
        await self.rebuild_progress(actor, session.goal_id, commit=False)
        self.db.commit()
        self.db.refresh(session)
        return FocusSessionRead.model_validate(session)

    async def tutor_message(
        self, actor: User, payload: TutorMessageRequest
    ) -> TutorResponse:
        goal = self._require_goal(actor, payload.goal_id, student_only=True)
        if payload.thread_id:
            thread = self.db.scalar(
                select(TutorThread).where(
                    TutorThread.id == payload.thread_id,
                    TutorThread.student_id == actor.id,
                    TutorThread.goal_id == goal.id,
                )
            )
            if not thread:
                raise AppError(404, "tutor_thread_not_found", "Tutor thread was not found")
            if thread.competency_ref != payload.competency_ref:
                raise AppError(
                    409,
                    "tutor_thread_competency_conflict",
                    "Tutor thread belongs to a different competency",
                )
        else:
            thread = TutorThread(
                student_id=actor.id,
                goal_id=goal.id,
                competency_ref=payload.competency_ref,
                mode=payload.mode,
            )
            self.db.add(thread)
            self.db.flush()
        student_message = TutorMessage(
            thread_id=thread.id,
            role="student",
            content=payload.message,
        )
        self.db.add(student_message)
        self.db.flush()
        sources = list(
            self.db.scalars(
                select(LearningResource)
                .where(
                    LearningResource.competency_ref == payload.competency_ref,
                    LearningResource.status == ResourceStatus.APPROVED,
                )
                .order_by(LearningResource.quality_score.desc())
                .limit(5)
            )
        )
        recent = list(
            self.db.scalars(
                select(TutorMessage)
                .where(TutorMessage.thread_id == thread.id)
                .order_by(TutorMessage.created_at.desc())
                .limit(6)
            )
        )
        result = cast(
            TutorResponse,
            await self.runner.run(
                self.db,
                actor,
                student_id=actor.id,
                goal_id=goal.id,
                agent=self.registry.get("ContextualTutorAgent"),
                input_data=TutorAgentInput(
                    thread_id=thread.id,
                    request=payload,
                    sources=[ResourceRead.model_validate(item) for item in sources],
                    recent_messages=[
                        {"role": item.role, "content": item.content}
                        for item in reversed(recent)
                    ],
                ),
                idempotency_key=f"tutor:{thread.id}:{student_message.id}",
            ),
        )
        self.db.add(
            TutorMessage(
                thread_id=thread.id,
                role="tutor",
                content=result.response,
                citations=[item.model_dump(mode="json") for item in result.citations],
                integrity_boundary_applied=result.integrity_boundary_applied,
            )
        )
        self._audit(
            actor,
            "phase4.tutor_response_created",
            "tutor_thread",
            thread.id,
            student_id=actor.id,
            after={
                "mode": payload.mode.value,
                "citation_count": len(result.citations),
                "integrity_boundary": result.integrity_boundary_applied,
            },
        )
        self.db.commit()
        return result

    def create_assessment(
        self, actor: User, payload: AssessmentCreate
    ) -> AssessmentRead:
        self._require_admin(actor)
        goal = self._require_goal(actor, payload.goal_id)
        definition = self._assessment_from_payload(actor, payload)
        self.db.add(definition)
        self.db.flush()
        self._audit(
            actor,
            "phase4.assessment_created",
            "assessment",
            definition.id,
            student_id=goal.student_id,
            after={"title": definition.title, "status": _enum_value(definition.status)},
        )
        self.db.commit()
        self.db.refresh(definition)
        return _assessment_read(definition)

    async def generate_assessment(
        self, actor: User, payload: AssessmentGenerateRequest
    ) -> AssessmentRead:
        self._require_admin(actor)
        goal = self._require_goal(actor, payload.goal_id)
        result = await self.runner.run(
            self.db,
            actor,
            student_id=goal.student_id,
            goal_id=goal.id,
            agent=self.registry.get("AssessmentGenerationAgent"),
            input_data=payload,
            idempotency_key=(
                f"assessment:generate:{goal.id}:"
                f"{_payload_hash(payload.model_dump(mode='json'))}"
            ),
        )
        definition = self._assessment_from_payload(actor, result.definition)
        self.db.add(definition)
        self.db.flush()
        self._audit(
            actor,
            "phase4.assessment_generated",
            "assessment",
            definition.id,
            student_id=goal.student_id,
            after={"title": definition.title, "status": _enum_value(definition.status)},
        )
        self.db.commit()
        self.db.refresh(definition)
        return _assessment_read(definition)

    def update_assessment_status(
        self,
        actor: User,
        assessment_id: uuid.UUID,
        payload: AssessmentStatusUpdate,
    ) -> AssessmentRead:
        self._require_admin(actor)
        definition = self.db.scalar(
            select(AssessmentDefinition)
            .where(AssessmentDefinition.id == assessment_id)
            .with_for_update()
        )
        if not definition:
            raise AppError(404, "assessment_not_found", "Assessment was not found")
        if definition.version != payload.expected_version:
            raise AppError(
                409,
                "version_conflict",
                "Assessment was updated by another request",
                {"current_version": definition.version},
            )
        if definition.status == AssessmentStatus.RETIRED:
            raise AppError(409, "assessment_retired", "Retired assessments are terminal")
        definition.status = payload.status
        definition.version += 1
        self._audit(
            actor,
            "phase4.assessment_status_changed",
            "assessment",
            definition.id,
            after={
                "status": _enum_value(definition.status),
                "version": definition.version,
            },
        )
        self.db.commit()
        self.db.refresh(definition)
        return _assessment_read(definition)

    def list_assessments(self, actor: User, goal_id: uuid.UUID) -> list[AssessmentRead]:
        self._require_goal(actor, goal_id, student_only=actor.role == Role.STUDENT)
        filters = [AssessmentDefinition.goal_id == goal_id]
        if actor.role == Role.STUDENT:
            filters.append(AssessmentDefinition.status == AssessmentStatus.PUBLISHED)
        return [
            _assessment_read(item)
            for item in self.db.scalars(
                select(AssessmentDefinition)
                .where(*filters)
                .order_by(AssessmentDefinition.created_at.desc())
            )
        ]

    async def submit_assessment(
        self,
        actor: User,
        assessment_id: uuid.UUID,
        payload: AssessmentAttemptCreate,
    ) -> AssessmentAttemptRead:
        existing = self.db.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.idempotency_key == payload.idempotency_key
            )
        )
        if existing:
            if existing.student_id != actor.id:
                raise AppError(409, "idempotency_conflict", "Idempotency key is in use")
            if existing.assessment_id != assessment_id:
                raise AppError(
                    409,
                    "idempotency_conflict",
                    "Idempotency key was reused for a different assessment",
                )
            return AssessmentAttemptRead.model_validate(existing)
        definition = self.db.get(AssessmentDefinition, assessment_id)
        if not definition or definition.status != AssessmentStatus.PUBLISHED:
            raise AppError(404, "assessment_not_found", "Published assessment was not found")
        self._require_goal(actor, definition.goal_id, student_only=True)
        answers = {item.question_id: item.answer for item in payload.answers}
        if len(answers) != len(payload.answers):
            raise AppError(422, "duplicate_answers", "Each question may be answered once")
        questions = [
            AssessmentQuestionInput.model_validate(question)
            for question in definition.questions
        ]
        known_ids = {question.id for question in questions}
        if not set(answers) <= known_ids:
            raise AppError(422, "unknown_question", "An answer references an unknown question")
        scoring_agent = AssessmentGenerationAgent()
        scored = await scoring_agent.score(
            AssessmentScoreInput(questions=questions, answers=answers)
        )
        attempt_number = (
            self.db.scalar(
                select(func.count(AssessmentAttempt.id)).where(
                    AssessmentAttempt.assessment_id == assessment_id,
                    AssessmentAttempt.student_id == actor.id,
                )
            )
            or 0
        ) + 1
        attempt = AssessmentAttempt(
            assessment_id=assessment_id,
            student_id=actor.id,
            attempt_number=attempt_number,
            answers=[item.model_dump(mode="json") for item in payload.answers],
            score=scored.score,
            max_score=scored.max_score,
            percentage=scored.percentage,
            passed=scored.percentage >= definition.passing_percentage,
            feedback=scored.feedback,
            status=(
                AttemptStatus.REVIEW_REQUIRED
                if scored.review_required
                else AttemptStatus.SCORED
            ),
            idempotency_key=payload.idempotency_key,
        )
        self.db.add(attempt)
        self.db.flush()
        self._progress_event(
            actor.id,
            definition.goal_id,
            event_type="assessment.scored",
            source_type="assessment_attempt",
            source_id=str(attempt.id),
            activity_points=2,
            mastery_signal=scored.percentage / 100,
            payload={
                "assessment_id": str(definition.id),
                "competency_ref": definition.competency_ref,
                "percentage": scored.percentage,
                "passed": attempt.passed,
            },
            idempotency_key=f"progress:assessment:{attempt.id}",
        )
        self._notify(
            actor.id,
            "assessment_result",
            "Assessment scored",
            f"{definition.title}: {scored.percentage:.1f}%",
            "assessment_attempt",
            attempt.id,
        )
        self._audit(
            actor,
            "phase4.assessment_submitted",
            "assessment_attempt",
            attempt.id,
            student_id=actor.id,
            after={
                "assessment_id": str(definition.id),
                "percentage": scored.percentage,
                "passed": attempt.passed,
            },
        )
        await self.rebuild_mastery(
            actor,
            definition.goal_id,
            definition.competency_ref,
            commit=False,
        )
        await self.rebuild_progress(actor, definition.goal_id, commit=False)
        self.db.commit()
        self.db.refresh(attempt)
        return AssessmentAttemptRead.model_validate(attempt)

    def register_storage_receipt(
        self, actor: User, payload: StorageReceiptCreate
    ) -> StorageReceiptRead:
        self._require_admin(actor)
        existing = self.db.scalar(
            select(StorageReceipt).where(
                StorageReceipt.storage_key == payload.storage_key
            )
        )
        if existing:
            if (
                existing.sha256 != payload.sha256.lower()
                or existing.size_bytes != payload.size_bytes
                or existing.media_type != payload.media_type
                or existing.scanner_status != payload.scanner_status
            ):
                raise AppError(
                    409,
                    "storage_receipt_conflict",
                    "Storage key is already registered with different content",
                )
            return StorageReceiptRead.model_validate(existing)
        values = payload.model_dump()
        values["sha256"] = payload.sha256.lower()
        receipt = StorageReceipt(**values, verified_by_user_id=actor.id)
        self.db.add(receipt)
        self.db.flush()
        self._audit(
            actor,
            "phase4.storage_object_verified",
            "storage_receipt",
            receipt.id,
            after={
                "storage_key": receipt.storage_key,
                "scanner_status": receipt.scanner_status,
            },
        )
        self.db.commit()
        self.db.refresh(receipt)
        return StorageReceiptRead.model_validate(receipt)

    async def submit_evidence(
        self, actor: User, payload: EvidenceSubmissionCreate
    ) -> EvidenceVerificationReport:
        goal = self._require_goal(actor, payload.goal_id, student_only=True)
        existing = self.db.scalar(
            select(EvidenceSubmission).where(
                EvidenceSubmission.idempotency_key == payload.idempotency_key
            )
        )
        if existing:
            if existing.student_id != actor.id:
                raise AppError(409, "idempotency_conflict", "Idempotency key is in use")
            if (
                existing.goal_id != goal.id
                or existing.sha256 != payload.sha256.lower()
                or existing.storage_key != payload.storage_key
            ):
                raise AppError(
                    409,
                    "idempotency_conflict",
                    "Idempotency key was reused with different evidence input",
                )
            review = self.db.scalar(
                select(EvidenceReview)
                .where(EvidenceReview.evidence_id == existing.id)
                .order_by(EvidenceReview.created_at.desc())
            )
            if not review:
                raise AppError(409, "evidence_processing", "Evidence is still processing")
            return EvidenceVerificationReport(
                status=(
                    AgentExecutionStatus.ADMIN_REVIEW_REQUIRED
                    if review.decision == EvidenceStatus.ADMIN_REVIEW_REQUIRED
                    else AgentExecutionStatus.COMPLETED
                ),
                confidence=1.0,
                evidence_id=existing.id,
                decision=review.decision,
                quality_score=review.quality_score,
                criteria_results=review.criteria_results,
                integrity_flags=review.integrity_flags,
                feedback=review.feedback,
            )
        if payload.assessment_attempt_id:
            owned_attempt = self.db.scalar(
                select(AssessmentAttempt)
                .join(
                    AssessmentDefinition,
                    AssessmentDefinition.id == AssessmentAttempt.assessment_id,
                )
                .where(
                    AssessmentAttempt.id == payload.assessment_attempt_id,
                    AssessmentAttempt.student_id == actor.id,
                    AssessmentDefinition.goal_id == goal.id,
                )
            )
            if not owned_attempt:
                raise AppError(
                    404,
                    "assessment_attempt_not_found",
                    "Assessment attempt was not found for this student and goal",
                )
        duplicate = self.db.scalar(
            select(EvidenceSubmission).where(
                EvidenceSubmission.student_id == actor.id,
                EvidenceSubmission.goal_id == goal.id,
                EvidenceSubmission.sha256 == payload.sha256.lower(),
            )
        )
        if duplicate:
            raise AppError(
                409,
                "evidence_duplicate",
                "This evidence content was already submitted for the goal",
                {"evidence_id": str(duplicate.id)},
            )
        receipt = self.db.scalar(
            select(StorageReceipt).where(
                StorageReceipt.storage_key == payload.storage_key
            )
        )
        storage_verified = bool(
            receipt
            and receipt.sha256.lower() == payload.sha256.lower()
            and receipt.size_bytes == payload.size_bytes
            and receipt.media_type == payload.media_type
        )
        scanner_clean = bool(receipt and receipt.scanner_status == "clean")
        evidence = EvidenceSubmission(
            student_id=actor.id,
            goal_id=goal.id,
            competency_ref=payload.competency_ref,
            task_ref=payload.task_ref,
            milestone_ref=payload.milestone_ref,
            assessment_attempt_id=payload.assessment_attempt_id,
            original_name=payload.original_name,
            media_type=payload.media_type,
            size_bytes=payload.size_bytes,
            sha256=payload.sha256.lower(),
            storage_key=payload.storage_key,
            content_text=payload.content_text,
            acceptance_criteria=payload.acceptance_criteria,
            idempotency_key=payload.idempotency_key,
        )
        self.db.add(evidence)
        self.db.flush()
        report = cast(
            EvidenceVerificationReport,
            await self.runner.run(
                self.db,
                actor,
                student_id=actor.id,
                goal_id=goal.id,
                agent=self.registry.get("EvidenceVerificationAgent"),
                input_data=EvidenceVerificationInput(
                    evidence_id=evidence.id,
                    submission=payload,
                    storage_verified=storage_verified,
                    scanner_clean=scanner_clean,
                ),
                idempotency_key=f"evidence:verify:{evidence.id}",
            ),
        )
        evidence.status = report.decision
        evidence.quality_score = report.quality_score
        evidence.reviewed_at = utc_now()
        self.db.add(
            EvidenceReview(
                evidence_id=evidence.id,
                reviewer_type="agent",
                decision=report.decision,
                quality_score=report.quality_score,
                criteria_results=[
                    item.model_dump(mode="json") for item in report.criteria_results
                ],
                integrity_flags=report.integrity_flags,
                feedback=report.feedback,
            )
        )
        self.db.flush()
        if report.decision == EvidenceStatus.VERIFIED:
            self._record_verified_evidence_event(evidence)
            await self.rebuild_mastery(
                actor,
                goal.id,
                evidence.competency_ref,
                commit=False,
            )
            await self.rebuild_progress(actor, goal.id, commit=False)
        elif report.decision == EvidenceStatus.ADMIN_REVIEW_REQUIRED:
            self._notify(
                actor.id,
                "evidence_review",
                "Evidence awaiting review",
                f"{evidence.original_name} needs an admin review.",
                "evidence",
                evidence.id,
            )
        self._audit(
            actor,
            "phase4.evidence_submitted",
            "evidence",
            evidence.id,
            student_id=actor.id,
            after={
                "goal_id": str(goal.id),
                "decision": report.decision.value,
                "quality_score": report.quality_score,
                "storage_verified": storage_verified,
            },
        )
        self.db.commit()
        return report

    def get_evidence(
        self, actor: User, evidence_id: uuid.UUID
    ) -> EvidenceRead:
        evidence = self.db.get(EvidenceSubmission, evidence_id)
        if not evidence:
            raise AppError(404, "evidence_not_found", "Evidence was not found")
        if actor.role == Role.STUDENT and evidence.student_id != actor.id:
            raise AppError(404, "evidence_not_found", "Evidence was not found")
        return EvidenceRead.model_validate(evidence)

    def list_evidence(
        self,
        actor: User,
        goal_id: uuid.UUID | None = None,
    ) -> list[EvidenceRead]:
        if actor.role != Role.STUDENT:
            raise AppError(403, "student_required", "A student account is required")
        conditions = [EvidenceSubmission.student_id == actor.id]
        if goal_id:
            self._require_goal(actor, goal_id, student_only=True)
            conditions.append(EvidenceSubmission.goal_id == goal_id)
        return [
            EvidenceRead.model_validate(item)
            for item in self.db.scalars(
                select(EvidenceSubmission)
                .where(*conditions)
                .order_by(EvidenceSubmission.submitted_at.desc())
            )
        ]

    def list_evidence_review_queue(self, actor: User) -> list[EvidenceRead]:
        self._require_admin(actor)
        return [
            EvidenceRead.model_validate(item)
            for item in self.db.scalars(
                select(EvidenceSubmission)
                .where(
                    EvidenceSubmission.status == EvidenceStatus.ADMIN_REVIEW_REQUIRED
                )
                .order_by(EvidenceSubmission.submitted_at)
            )
        ]

    async def decide_evidence(
        self,
        actor: User,
        evidence_id: uuid.UUID,
        payload: AdminEvidenceDecision,
    ) -> EvidenceRead:
        self._require_admin(actor)
        evidence = self.db.scalar(
            select(EvidenceSubmission)
            .where(EvidenceSubmission.id == evidence_id)
            .with_for_update()
        )
        if not evidence:
            raise AppError(404, "evidence_not_found", "Evidence was not found")
        if evidence.status != EvidenceStatus.ADMIN_REVIEW_REQUIRED:
            raise AppError(409, "evidence_not_in_review", "Evidence is not awaiting review")
        decision = EvidenceStatus(payload.decision)
        evidence.status = decision
        evidence.reviewed_at = utc_now()
        if decision == EvidenceStatus.VERIFIED:
            evidence.quality_score = max(evidence.quality_score or 0, 0.7)
        self.db.add(
            EvidenceReview(
                evidence_id=evidence.id,
                reviewer_type="admin",
                reviewer_id=actor.id,
                decision=decision,
                quality_score=evidence.quality_score or 0,
                criteria_results=[],
                integrity_flags=[],
                feedback=payload.reason,
            )
        )
        if decision == EvidenceStatus.VERIFIED:
            self._record_verified_evidence_event(evidence)
            self.db.flush()
            student = self.db.get(User, evidence.student_id)
            if student:
                await self.rebuild_mastery(
                    student,
                    evidence.goal_id,
                    evidence.competency_ref,
                    commit=False,
                )
                await self.rebuild_progress(student, evidence.goal_id, commit=False)
        self._notify(
            evidence.student_id,
            "evidence_decision",
            "Evidence review completed",
            payload.reason,
            "evidence",
            evidence.id,
        )
        self._audit(
            actor,
            "phase4.evidence_admin_decided",
            "evidence",
            evidence.id,
            student_id=evidence.student_id,
            after={"decision": decision.value, "reason": payload.reason},
        )
        self.db.commit()
        self.db.refresh(evidence)
        return EvidenceRead.model_validate(evidence)

    async def sync_execution_context(
        self,
        actor: User,
        goal_id: uuid.UUID,
        payload: ExecutionContextSync,
    ) -> ExecutionContextRead:
        self._require_admin(actor)
        goal = self._require_goal(actor, goal_id)
        context = self.db.scalar(
            select(ExecutionContext)
            .where(ExecutionContext.goal_id == goal.id)
            .with_for_update()
        )
        if context and self._aware(payload.source_updated_at) <= self._aware(
            context.source_updated_at
        ):
            raise AppError(
                409,
                "stale_execution_context",
                "Execution context is older than the stored Phase 3 snapshot",
                {"current_version": context.version},
            )
        values = payload.model_dump()
        if context:
            for key, value in values.items():
                setattr(context, key, value)
            context.version += 1
        else:
            context = ExecutionContext(
                goal_id=goal.id,
                student_id=goal.student_id,
                **values,
            )
            self.db.add(context)
        self.db.flush()
        student = self.db.get(User, goal.student_id)
        if student:
            await self.rebuild_progress(student, goal.id, commit=False)
        self._audit(
            actor,
            "phase4.execution_context_synced",
            "execution_context",
            context.id,
            student_id=goal.student_id,
            after={
                "plan_ref": context.plan_ref,
                "plan_version": context.plan_version,
                "version": context.version,
            },
        )
        self.db.commit()
        self.db.refresh(context)
        return ExecutionContextRead.model_validate(context)

    async def rebuild_progress(
        self,
        actor: User,
        goal_id: uuid.UUID,
        *,
        commit: bool = True,
    ) -> ProgressSnapshotRead:
        goal = self._require_goal(actor, goal_id, student_only=actor.role == Role.STUDENT)
        context = self.db.scalar(
            select(ExecutionContext).where(ExecutionContext.goal_id == goal.id)
        )
        focus_minutes = (
            self.db.scalar(
                select(func.coalesce(func.sum(FocusSession.actual_minutes), 0)).where(
                    FocusSession.student_id == goal.student_id,
                    FocusSession.goal_id == goal.id,
                    FocusSession.status == FocusSessionStatus.COMPLETED,
                )
            )
            or 0
        )
        focus_count = (
            self.db.scalar(
                select(func.count(FocusSession.id)).where(
                    FocusSession.student_id == goal.student_id,
                    FocusSession.goal_id == goal.id,
                    FocusSession.status == FocusSessionStatus.COMPLETED,
                )
            )
            or 0
        )
        verified_evidence = list(
            self.db.scalars(
                select(EvidenceSubmission).where(
                    EvidenceSubmission.student_id == goal.student_id,
                    EvidenceSubmission.goal_id == goal.id,
                    EvidenceSubmission.status == EvidenceStatus.VERIFIED,
                )
            )
        )
        attempts = list(
            self.db.scalars(
                select(AssessmentAttempt)
                .join(
                    AssessmentDefinition,
                    AssessmentDefinition.id == AssessmentAttempt.assessment_id,
                )
                .where(
                    AssessmentAttempt.student_id == goal.student_id,
                    AssessmentDefinition.goal_id == goal.id,
                )
            )
        )
        estimates = list(
            self.db.scalars(
                select(MasteryEstimate)
                .where(
                    MasteryEstimate.student_id == goal.student_id,
                    MasteryEstimate.goal_id == goal.id,
                )
                .order_by(
                    MasteryEstimate.competency_ref,
                    MasteryEstimate.version.desc(),
                )
            )
        )
        latest_mastery: dict[str, float] = {}
        for estimate in estimates:
            latest_mastery.setdefault(estimate.competency_ref, estimate.score)
        input_data = ProgressComputationInput(
            goal_id=goal.id,
            execution=(
                ExecutionContextSync.model_validate(context) if context else None
            ),
            focus_minutes=int(focus_minutes),
            completed_focus_sessions=int(focus_count),
            verified_evidence_count=len(verified_evidence),
            evidence_quality_scores=[
                item.quality_score or 0 for item in verified_evidence
            ],
            assessment_percentages=[item.percentage for item in attempts],
            mastery_scores=list(latest_mastery.values()),
        )
        state_hash = _payload_hash(input_data.model_dump(mode="json"))
        latest = self.db.scalar(
            select(ProgressSnapshot)
            .where(ProgressSnapshot.goal_id == goal.id)
            .order_by(ProgressSnapshot.version.desc())
            .limit(1)
        )
        if latest and latest.calculation.get("state_hash") == state_hash:
            return ProgressSnapshotRead.model_validate(latest)
        result = await self.runner.run(
            self.db,
            actor,
            student_id=goal.student_id,
            goal_id=goal.id,
            agent=self.registry.get("ProgressTrackingAgent"),
            input_data=input_data,
            idempotency_key=f"progress:rebuild:{goal.id}:{state_hash}",
        )
        calculation = {**result.calculation, "state_hash": state_hash}
        snapshot = ProgressSnapshot(
            student_id=goal.student_id,
            goal_id=goal.id,
            version=(latest.version + 1 if latest else 1),
            activity_progress=result.activity_progress,
            milestone_progress=result.milestone_progress,
            mastery_progress=result.mastery_progress,
            goal_confidence=result.goal_confidence,
            schedule_variance=result.schedule_variance,
            verified_evidence_count=len(verified_evidence),
            assessment_count=len(attempts),
            focus_minutes=int(focus_minutes),
            calculation=calculation,
        )
        self.db.add(snapshot)
        self.db.flush()
        self._audit(
            actor,
            "phase4.progress_updated",
            "progress_snapshot",
            snapshot.id,
            student_id=goal.student_id,
            after={
                "goal_id": str(goal.id),
                "version": snapshot.version,
                "activity_progress": snapshot.activity_progress,
                "milestone_progress": snapshot.milestone_progress,
                "mastery_progress": snapshot.mastery_progress,
                "goal_confidence": snapshot.goal_confidence,
            },
        )
        if commit:
            self.db.commit()
            self.db.refresh(snapshot)
        return ProgressSnapshotRead.model_validate(snapshot)

    def latest_progress(self, actor: User, goal_id: uuid.UUID) -> ProgressSnapshotRead:
        goal = self._require_goal(actor, goal_id, student_only=actor.role == Role.STUDENT)
        snapshot = self.db.scalar(
            select(ProgressSnapshot)
            .where(ProgressSnapshot.goal_id == goal.id)
            .order_by(ProgressSnapshot.version.desc())
            .limit(1)
        )
        if not snapshot:
            raise AppError(404, "progress_not_found", "Progress has not been calculated")
        return ProgressSnapshotRead.model_validate(snapshot)

    async def rebuild_mastery(
        self,
        actor: User,
        goal_id: uuid.UUID,
        competency_ref: str,
        *,
        tutor_misconceptions: list[str] | None = None,
        commit: bool = True,
    ) -> MasteryEstimateRead:
        goal = self._require_goal(actor, goal_id, student_only=actor.role == Role.STUDENT)
        attempts = list(
            self.db.scalars(
                select(AssessmentAttempt)
                .join(
                    AssessmentDefinition,
                    AssessmentDefinition.id == AssessmentAttempt.assessment_id,
                )
                .where(
                    AssessmentAttempt.student_id == goal.student_id,
                    AssessmentDefinition.goal_id == goal.id,
                    AssessmentDefinition.competency_ref == competency_ref,
                )
            )
        )
        evidence = list(
            self.db.scalars(
                select(EvidenceSubmission).where(
                    EvidenceSubmission.student_id == goal.student_id,
                    EvidenceSubmission.goal_id == goal.id,
                    EvidenceSubmission.competency_ref == competency_ref,
                    EvidenceSubmission.status == EvidenceStatus.VERIFIED,
                )
            )
        )
        input_data = MasteryComputationInput(
            goal_id=goal.id,
            competency_ref=competency_ref,
            assessment_percentages=[item.percentage for item in attempts],
            evidence_quality_scores=[item.quality_score or 0 for item in evidence],
            tutor_misconceptions=tutor_misconceptions or [],
        )
        state_hash = _payload_hash(input_data.model_dump(mode="json"))
        latest = self.db.scalar(
            select(MasteryEstimate)
            .where(
                MasteryEstimate.goal_id == goal.id,
                MasteryEstimate.competency_ref == competency_ref,
            )
            .order_by(MasteryEstimate.version.desc())
            .limit(1)
        )
        if latest and latest.calculation.get("state_hash") == state_hash:
            return MasteryEstimateRead.model_validate(latest)
        result = await self.runner.run(
            self.db,
            actor,
            student_id=goal.student_id,
            goal_id=goal.id,
            agent=self.registry.get("MasteryEstimationAgent"),
            input_data=input_data,
            idempotency_key=f"mastery:{goal.id}:{competency_ref}:{state_hash}",
        )
        estimate = MasteryEstimate(
            student_id=goal.student_id,
            goal_id=goal.id,
            competency_ref=competency_ref,
            version=(latest.version + 1 if latest else 1),
            score=result.score,
            confidence_lower=result.confidence_lower,
            confidence_upper=result.confidence_upper,
            evidence_count=result.evidence_count,
            weak_subskills=result.weak_subskills,
            next_assessment_recommendation=result.next_assessment_recommendation,
            calculation={**result.calculation, "state_hash": state_hash},
        )
        self.db.add(estimate)
        self.db.flush()
        self._audit(
            actor,
            "phase4.mastery_updated",
            "mastery_estimate",
            estimate.id,
            student_id=goal.student_id,
            after={
                "goal_id": str(goal.id),
                "competency_ref": competency_ref,
                "score": estimate.score,
                "version": estimate.version,
            },
        )
        if commit:
            self.db.commit()
            self.db.refresh(estimate)
        return MasteryEstimateRead.model_validate(estimate)

    def list_mastery(
        self, actor: User, goal_id: uuid.UUID
    ) -> list[MasteryEstimateRead]:
        goal = self._require_goal(actor, goal_id, student_only=actor.role == Role.STUDENT)
        estimates = list(
            self.db.scalars(
                select(MasteryEstimate)
                .where(MasteryEstimate.goal_id == goal.id)
                .order_by(
                    MasteryEstimate.competency_ref,
                    MasteryEstimate.version.desc(),
                )
            )
        )
        latest: dict[str, MasteryEstimate] = {}
        for estimate in estimates:
            latest.setdefault(estimate.competency_ref, estimate)
        return [
            MasteryEstimateRead.model_validate(item) for item in latest.values()
        ]

    async def coach(
        self, actor: User, payload: CoachingRequest
    ) -> CoachingResponse:
        goal = self._require_goal(actor, payload.goal_id, student_only=True)
        latest = self.db.scalar(
            select(ProgressSnapshot)
            .where(ProgressSnapshot.goal_id == goal.id)
            .order_by(ProgressSnapshot.version.desc())
            .limit(1)
        )
        coaching_id = uuid.uuid4()
        result = await self.runner.run(
            self.db,
            actor,
            student_id=actor.id,
            goal_id=goal.id,
            agent=self.registry.get("MotivationHabitCoachAgent"),
            input_data=CoachingAgentInput(
                coaching_id=coaching_id,
                request=payload,
                recent_goal_confidence=latest.goal_confidence if latest else 0,
                recent_focus_minutes=latest.focus_minutes if latest else 0,
            ),
            idempotency_key=f"coaching:{coaching_id}",
        )
        record = CoachingRecord(
            id=coaching_id,
            student_id=actor.id,
            goal_id=goal.id,
            check_in=payload.check_in,
            motivation_level=payload.motivation_level,
            message=result.message,
            reflection_prompt=result.reflection_prompt,
            habit_experiment=result.habit_experiment,
            notification_adjustment=result.notification_adjustment,
        )
        self.db.add(record)
        self._audit(
            actor,
            "phase4.coaching_delivered",
            "coaching_record",
            record.id,
            student_id=actor.id,
            after={"goal_id": str(goal.id), "motivation_level": payload.motivation_level},
        )
        self.db.commit()
        return CoachingResponse(
            **result.model_dump(),
        )

    async def scan_risks(
        self,
        actor: User,
        goal_id: uuid.UUID,
        payload: RiskScanRequest,
    ) -> RiskScanResult:
        goal = self._require_goal(actor, goal_id, student_only=True)
        latest_progress = self.db.scalar(
            select(ProgressSnapshot)
            .where(ProgressSnapshot.goal_id == goal.id)
            .order_by(ProgressSnapshot.version.desc())
            .limit(1)
        )
        if not latest_progress:
            await self.rebuild_progress(actor, goal.id, commit=False)
            latest_progress = self.db.scalar(
                select(ProgressSnapshot)
                .where(ProgressSnapshot.goal_id == goal.id)
                .order_by(ProgressSnapshot.version.desc())
                .limit(1)
            )
        assert latest_progress is not None
        context = self.db.scalar(
            select(ExecutionContext).where(ExecutionContext.goal_id == goal.id)
        )
        seven_days_ago = datetime.now(UTC) - timedelta(days=7)
        recent_minutes = (
            self.db.scalar(
                select(func.coalesce(func.sum(FocusSession.actual_minutes), 0)).where(
                    FocusSession.student_id == actor.id,
                    FocusSession.goal_id == goal.id,
                    FocusSession.status == FocusSessionStatus.COMPLETED,
                    FocusSession.ended_at >= seven_days_ago,
                )
            )
            or 0
        )
        risk_input = RiskDetectionInput(
            goal_id=goal.id,
            target_date=goal.target_date,
            progress={
                "activity_progress": latest_progress.activity_progress,
                "milestone_progress": latest_progress.milestone_progress,
                "mastery_progress": latest_progress.mastery_progress,
                "goal_confidence": latest_progress.goal_confidence,
            },
            execution=(
                ExecutionContextSync.model_validate(context) if context else None
            ),
            focus_minutes_last_7_days=int(recent_minutes),
            open_blockers=payload.open_blockers,
            tutor_misconceptions=payload.tutor_misconceptions,
            resource_issue=payload.resource_issue,
            now=datetime.now(UTC).replace(second=0, microsecond=0),
        )
        state_hash = _payload_hash(risk_input.model_dump(mode="json"))
        result = await self.runner.run(
            self.db,
            actor,
            student_id=actor.id,
            goal_id=goal.id,
            agent=self.registry.get("RiskBlockerDetectionAgent"),
            input_data=risk_input,
            idempotency_key=f"risk-scan:{goal.id}:{state_hash}",
        )
        persisted: list[Risk] = []
        for finding in result.findings:
            risk = self.db.scalar(
                select(Risk)
                .where(
                    Risk.goal_id == goal.id,
                    Risk.student_id == actor.id,
                    Risk.fingerprint == finding.fingerprint,
                    Risk.status == RiskStatus.OPEN,
                )
                .with_for_update()
            )
            if risk:
                risk.score = finding.score
                risk.severity = finding.severity
                risk.evidence_refs = finding.evidence_refs
                risk.likely_causes = finding.likely_causes
                risk.intervention = finding.intervention
                risk.requires_admin_review = finding.requires_admin_review
                risk.version += 1
            else:
                risk = Risk(
                    student_id=actor.id,
                    goal_id=goal.id,
                    risk_type=finding.risk_type,
                    severity=finding.severity,
                    status=RiskStatus.OPEN,
                    score=finding.score,
                    evidence_refs=finding.evidence_refs,
                    likely_causes=finding.likely_causes,
                    intervention=finding.intervention,
                    requires_admin_review=finding.requires_admin_review,
                    fingerprint=finding.fingerprint,
                )
                self.db.add(risk)
                self.db.flush()
            persisted.append(risk)
            severity = _enum_value(finding.severity)
            if severity in {"high", "critical"}:
                self._notify(
                    actor.id,
                    "risk_detected",
                    f"{severity.title()} risk detected",
                    finding.intervention,
                    "risk",
                    risk.id,
                )
        self._audit(
            actor,
            "phase4.risk_scan_completed",
            "goal",
            goal.id,
            student_id=actor.id,
            after={
                "risk_count": len(persisted),
                "risk_ids": [str(item.id) for item in persisted],
            },
        )
        self.db.commit()
        for item in persisted:
            self.db.refresh(item)
        return RiskScanResult(
            confidence=result.confidence,
            goal_id=goal.id,
            risks=[RiskRead.model_validate(item) for item in persisted],
            evidence_refs=result.evidence_refs,
            warnings=result.warnings,
            next_actions=result.next_actions,
        )

    def list_risks(self, actor: User, goal_id: uuid.UUID) -> list[RiskRead]:
        goal = self._require_goal(actor, goal_id, student_only=actor.role == Role.STUDENT)
        return [
            RiskRead.model_validate(item)
            for item in self.db.scalars(
                select(Risk)
                .where(Risk.goal_id == goal.id)
                .order_by(Risk.detected_at.desc())
            )
        ]

    async def propose_replan(
        self,
        actor: User,
        goal_id: uuid.UUID,
        payload: ReplanRequest,
    ) -> ReplanProposalRead:
        goal = self._require_goal(actor, goal_id, student_only=True)
        risk = self.db.scalar(
            select(Risk).where(
                Risk.id == payload.risk_id,
                Risk.student_id == actor.id,
                Risk.goal_id == goal.id,
                Risk.status == RiskStatus.OPEN,
            )
        )
        if not risk:
            raise AppError(404, "risk_not_found", "Open risk was not found")
        context = self.db.scalar(
            select(ExecutionContext).where(ExecutionContext.goal_id == goal.id)
        )
        finding = RiskFinding(
            risk_type=risk.risk_type,
            severity=risk.severity,
            score=risk.score,
            evidence_refs=risk.evidence_refs,
            likely_causes=risk.likely_causes,
            intervention=risk.intervention,
            requires_admin_review=risk.requires_admin_review,
            fingerprint=risk.fingerprint,
        )
        result = await self.runner.run(
            self.db,
            actor,
            student_id=actor.id,
            goal_id=goal.id,
            agent=self.registry.get("AdaptiveReplanningAgent"),
            input_data=ReplanAgentInput(
                goal_id=goal.id,
                risk=finding,
                base_plan_ref=payload.base_plan_ref,
                base_plan_version=payload.base_plan_version,
                preserve_completed_work=payload.preserve_completed_work,
                student_constraints=payload.student_constraints,
                execution=(
                    ExecutionContextSync.model_validate(context) if context else None
                ),
            ),
            idempotency_key=(
                f"replan:{risk.id}:{payload.base_plan_ref}:"
                f"{payload.base_plan_version}"
            ),
        )
        existing = self.db.scalar(
            select(ReplanProposal).where(
                ReplanProposal.risk_id == risk.id,
                ReplanProposal.base_plan_ref == payload.base_plan_ref,
                ReplanProposal.base_plan_version == payload.base_plan_version,
                ReplanProposal.status == ReplanStatus.PROPOSED,
            )
        )
        if existing:
            return ReplanProposalRead.model_validate(existing)
        proposal = ReplanProposal(
            student_id=actor.id,
            goal_id=goal.id,
            risk_id=risk.id,
            base_plan_ref=payload.base_plan_ref,
            base_plan_version=payload.base_plan_version,
            status=ReplanStatus.PROPOSED,
            proposed_patch=result.proposed_patch,
            impact_analysis=result.impact_analysis,
            alternatives=result.alternatives,
            preserves_completed_work=result.preserves_completed_work,
            student_approval_required=result.student_approval_required,
            admin_review_required=result.admin_review_required,
        )
        self.db.add(proposal)
        self.db.flush()
        self._notify(
            actor.id,
            "replan_proposed",
            "Plan adjustment proposed",
            "Review the proposed plan changes before they are sent to Phase 3.",
            "replan",
            proposal.id,
        )
        self._audit(
            actor,
            "phase4.replan_proposed",
            "replan",
            proposal.id,
            student_id=actor.id,
            after={
                "risk_id": str(risk.id),
                "base_plan_ref": payload.base_plan_ref,
                "admin_review_required": proposal.admin_review_required,
            },
        )
        self.db.commit()
        self.db.refresh(proposal)
        return ReplanProposalRead.model_validate(proposal)

    def decide_replan(
        self,
        actor: User,
        proposal_id: uuid.UUID,
        payload: ReplanDecision,
    ) -> ReplanProposalRead:
        if actor.role != Role.STUDENT:
            raise AppError(403, "student_required", "A student account is required")
        proposal = self.db.scalar(
            select(ReplanProposal)
            .where(
                ReplanProposal.id == proposal_id,
                ReplanProposal.student_id == actor.id,
            )
            .with_for_update()
        )
        if not proposal:
            raise AppError(404, "replan_not_found", "Replan proposal was not found")
        if proposal.status != ReplanStatus.PROPOSED:
            raise AppError(409, "replan_already_decided", "Replan was already decided")
        if proposal.version != payload.expected_version:
            raise AppError(
                409,
                "version_conflict",
                "Replan was updated by another request",
                {"current_version": proposal.version},
            )
        if payload.decision == "approve" and proposal.admin_review_required:
            raise AppError(
                409,
                "admin_review_required",
                "Admin review must complete before student approval",
            )
        proposal.status = (
            ReplanStatus.APPROVED_PENDING_PHASE3
            if payload.decision == "approve"
            else ReplanStatus.REJECTED
        )
        proposal.decision_reason = payload.reason
        proposal.decided_at = utc_now()
        proposal.version += 1
        self._audit(
            actor,
            f"phase4.replan_{payload.decision}d",
            "replan",
            proposal.id,
            student_id=actor.id,
            after={
                "status": _enum_value(proposal.status),
                "reason": payload.reason,
                "phase3_applied": False,
            },
        )
        self.db.commit()
        self.db.refresh(proposal)
        return ReplanProposalRead.model_validate(proposal)

    def admin_decide_replan(
        self,
        actor: User,
        proposal_id: uuid.UUID,
        payload: ReplanDecision,
    ) -> ReplanProposalRead:
        self._require_admin(actor)
        proposal = self.db.scalar(
            select(ReplanProposal)
            .where(ReplanProposal.id == proposal_id)
            .with_for_update()
        )
        if not proposal:
            raise AppError(404, "replan_not_found", "Replan proposal was not found")
        if proposal.status != ReplanStatus.PROPOSED:
            raise AppError(409, "replan_already_decided", "Replan was already decided")
        if not proposal.admin_review_required:
            raise AppError(409, "admin_review_not_required", "Replan needs student review")
        if proposal.version != payload.expected_version:
            raise AppError(
                409,
                "version_conflict",
                "Replan was updated by another request",
                {"current_version": proposal.version},
            )
        if payload.decision == "approve":
            proposal.admin_review_required = False
            proposal.decision_reason = payload.reason
        else:
            proposal.status = ReplanStatus.REJECTED
            proposal.decided_at = utc_now()
            proposal.decision_reason = payload.reason
        proposal.version += 1
        self._audit(
            actor,
            f"phase4.admin_replan_{payload.decision}d",
            "replan",
            proposal.id,
            student_id=proposal.student_id,
            after={
                "status": _enum_value(proposal.status),
                "admin_review_required": proposal.admin_review_required,
            },
        )
        self.db.commit()
        self.db.refresh(proposal)
        return ReplanProposalRead.model_validate(proposal)

    def list_notifications(
        self, actor: User, *, unread_only: bool = False
    ) -> list[NotificationRead]:
        filters = [Notification.student_id == actor.id]
        if unread_only:
            filters.append(Notification.read_at.is_(None))
        return [
            NotificationRead.model_validate(item)
            for item in self.db.scalars(
                select(Notification)
                .where(*filters)
                .order_by(Notification.created_at.desc())
            )
        ]

    def mark_notification_read(
        self, actor: User, notification_id: uuid.UUID
    ) -> NotificationRead:
        notification = self.db.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.student_id == actor.id,
            )
        )
        if not notification:
            raise AppError(404, "notification_not_found", "Notification was not found")
        if not notification.read_at:
            notification.read_at = utc_now()
            self.db.commit()
            self.db.refresh(notification)
        return NotificationRead.model_validate(notification)

    def list_agent_runs(self, actor: User) -> list[Phase4AgentRun]:
        self._require_admin(actor)
        return list(
            self.db.scalars(
                select(Phase4AgentRun)
                .order_by(Phase4AgentRun.started_at.desc())
                .limit(200)
            )
        )

    def _assessment_from_payload(
        self, actor: User, payload: AssessmentCreate
    ) -> AssessmentDefinition:
        questions = [item.model_dump(mode="json") for item in payload.questions]
        return AssessmentDefinition(
            goal_id=payload.goal_id,
            competency_ref=payload.competency_ref,
            title=payload.title,
            assessment_type=payload.assessment_type,
            instructions=payload.instructions,
            questions=questions,
            rubric=payload.rubric,
            max_score=sum(item.points for item in payload.questions),
            passing_percentage=payload.passing_percentage,
            time_limit_minutes=payload.time_limit_minutes,
            status=AssessmentStatus.DRAFT,
            created_by_user_id=actor.id,
        )

    def _record_verified_evidence_event(self, evidence: EvidenceSubmission) -> None:
        self._progress_event(
            evidence.student_id,
            evidence.goal_id,
            event_type="evidence.verified",
            source_type="evidence",
            source_id=str(evidence.id),
            activity_points=3,
            mastery_signal=evidence.quality_score,
            payload={
                "competency_ref": evidence.competency_ref,
                "quality_score": evidence.quality_score,
                "task_ref": evidence.task_ref,
                "milestone_ref": evidence.milestone_ref,
            },
            idempotency_key=f"progress:evidence:{evidence.id}",
        )

    def _progress_event(
        self,
        student_id: uuid.UUID,
        goal_id: uuid.UUID,
        *,
        event_type: str,
        source_type: str,
        source_id: str,
        activity_points: float,
        mastery_signal: float | None,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> ProgressEvent:
        existing = self.db.scalar(
            select(ProgressEvent).where(
                ProgressEvent.idempotency_key == idempotency_key
            )
        )
        if existing:
            return existing
        event = ProgressEvent(
            student_id=student_id,
            goal_id=goal_id,
            event_type=event_type,
            source_type=source_type,
            source_id=source_id,
            activity_points=activity_points,
            mastery_signal=mastery_signal,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        self.db.add(event)
        return event

    def _notify(
        self,
        student_id: uuid.UUID,
        notification_type: str,
        title: str,
        body: str,
        related_type: str | None,
        related_id: uuid.UUID | str | None,
    ) -> None:
        self.db.add(
            Notification(
                student_id=student_id,
                notification_type=notification_type,
                title=title,
                body=body,
                related_type=related_type,
                related_id=str(related_id) if related_id else None,
            )
        )

    def _require_goal(
        self,
        actor: User,
        goal_id: uuid.UUID,
        *,
        student_only: bool = False,
    ) -> Goal:
        goal = self.db.get(Goal, goal_id)
        if not goal:
            raise AppError(404, "goal_not_found", "Goal was not found")
        if student_only and actor.role != Role.STUDENT:
            raise AppError(403, "student_role_required", "Student role is required")
        if actor.role == Role.STUDENT and goal.student_id != actor.id:
            raise AppError(404, "goal_not_found", "Goal was not found")
        return goal

    @staticmethod
    def _require_admin(actor: User) -> None:
        if actor.role != Role.ADMIN:
            raise AppError(403, "admin_role_required", "Admin role is required")

    def _audit(
        self,
        actor: User,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | str,
        *,
        student_id: uuid.UUID | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.audit or not self.audit_context:
            return
        self.audit_context.actor = actor
        self.audit.record(
            self.db,
            self.audit_context,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            student_id=student_id,
            before=before,
            after=after,
            metadata=metadata,
        )

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
