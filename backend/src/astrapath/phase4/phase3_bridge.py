import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from astrapath.audit import AuditContext, AuditService
from astrapath.db import utc_now
from astrapath.errors import AppError
from astrapath.models import User
from astrapath.phase3.contracts import ApprovedReplanCommand
from astrapath.phase3.models import (
    LearningPlan,
    Milestone,
    Schedule,
    ScheduleBlock,
    Task,
)
from astrapath.phase3.service import PlanningService
from astrapath.phase4.contracts import ReplanProposalRead
from astrapath.phase4.enums import ReplanStatus
from astrapath.phase4.models import ExecutionContext, ReplanProposal


class Phase3Phase4Bridge:
    """Transactional adapter between planning and adaptive learning."""

    def __init__(
        self,
        audit: AuditService,
        planning: PlanningService,
    ) -> None:
        self.audit = audit
        self.planning = planning

    def sync_plan(
        self,
        db: Session,
        plan: LearningPlan,
        *,
        actor: User,
        audit_context: AuditContext,
    ) -> None:
        db.flush()
        schedule = db.scalar(
            select(Schedule).where(Schedule.plan_id == plan.id)
        )
        tasks = list(
            db.scalars(select(Task).where(Task.plan_id == plan.id))
        )
        milestones = list(
            db.scalars(select(Milestone).where(Milestone.plan_id == plan.id))
        )
        now = datetime.now(UTC)
        past_block_count = 0
        completed_block_count = 0
        if schedule:
            past_block_count = int(
                db.scalar(
                    select(func.count(ScheduleBlock.id)).where(
                        ScheduleBlock.schedule_id == schedule.id,
                        ScheduleBlock.ends_at <= now,
                    )
                )
                or 0
            )
            completed_block_count = int(
                db.scalar(
                    select(func.count(ScheduleBlock.id)).where(
                        ScheduleBlock.schedule_id == schedule.id,
                        ScheduleBlock.ends_at <= now,
                        ScheduleBlock.status == "completed",
                    )
                )
                or 0
            )
        adherence = (
            completed_block_count / past_block_count
            if past_block_count
            else 1.0
        )
        active_tasks = [item for item in tasks if item.status != "dropped"]
        active_milestones = [
            item for item in milestones if item.status != "dropped"
        ]
        duration_days = max((plan.target_date - plan.starts_on).days + 1, 1)
        duration_weeks = max(duration_days / 7, 1)
        planned_weekly_minutes = round(
            (schedule.allocated_minutes if schedule else plan.total_estimated_minutes)
            / duration_weeks
        )
        values = {
            "student_id": plan.student_id,
            "plan_ref": str(plan.id),
            "plan_version": plan.version,
            "planned_task_count": len(active_tasks),
            "completed_task_count": sum(
                item.status == "completed" for item in active_tasks
            ),
            "planned_milestone_count": len(active_milestones),
            "completed_milestone_count": sum(
                item.status == "completed" for item in active_milestones
            ),
            "planned_weekly_minutes": planned_weekly_minutes,
            "weekly_capacity_minutes": (
                schedule.weekly_capacity_minutes if schedule else 0
            ),
            "schedule_adherence": round(adherence, 4),
            "source_updated_at": max(
                [
                    self._aware(plan.updated_at),
                    *(self._aware(item.updated_at) for item in tasks),
                    *(self._aware(item.updated_at) for item in milestones),
                    *(
                        [self._aware(schedule.updated_at)]
                        if schedule
                        else []
                    ),
                ]
            ),
        }
        context = db.scalar(
            select(ExecutionContext)
            .where(ExecutionContext.goal_id == plan.goal_id)
            .with_for_update()
        )
        before = None
        if context:
            comparable = {
                key: getattr(context, key)
                for key in values
                if key != "source_updated_at"
            }
            if comparable == {
                key: value
                for key, value in values.items()
                if key != "source_updated_at"
            }:
                return
            before = {
                "plan_ref": context.plan_ref,
                "plan_version": context.plan_version,
                "completed_task_count": context.completed_task_count,
                "completed_milestone_count": context.completed_milestone_count,
            }
            for key, value in values.items():
                setattr(context, key, value)
            context.version += 1
        else:
            context = ExecutionContext(goal_id=plan.goal_id, **values)
            db.add(context)
        db.flush()
        self.audit.record(
            db,
            audit_context,
            action="phase4.execution_context_synced_from_phase3",
            resource_type="execution_context",
            resource_id=context.id,
            student_id=plan.student_id,
            before=before,
            after={
                "plan_ref": context.plan_ref,
                "plan_version": context.plan_version,
                "completed_task_count": context.completed_task_count,
                "completed_milestone_count": context.completed_milestone_count,
                "version": context.version,
            },
            metadata={"phase": 4, "source_phase": 3},
        )

    async def apply_pending_replan(
        self,
        db: Session,
        actor: User,
        proposal_id: uuid.UUID,
        *,
        audit_context: AuditContext,
        correlation_id: str,
    ) -> ReplanProposalRead:
        proposal = db.scalar(
            select(ReplanProposal)
            .where(
                ReplanProposal.id == proposal_id,
                ReplanProposal.student_id == actor.id,
            )
            .with_for_update()
        )
        if not proposal:
            raise AppError(404, "replan_not_found", "Replan proposal was not found")
        if proposal.status == ReplanStatus.APPLIED:
            return ReplanProposalRead.model_validate(proposal)
        if proposal.status != ReplanStatus.APPROVED_PENDING_PHASE3:
            raise AppError(
                409,
                "replan_not_approved",
                "The replan must be approved before Phase 3 can apply it",
            )
        try:
            source_plan_id = uuid.UUID(proposal.base_plan_ref)
        except ValueError as exc:
            raise AppError(
                409,
                "invalid_phase3_plan_ref",
                "The replan does not reference a valid Phase 3 plan",
            ) from exc

        plan = await self.planning.apply_approved_replan(
            db,
            actor,
            proposal.goal_id,
            ApprovedReplanCommand(
                source_plan_id=source_plan_id,
                source_plan_version=proposal.base_plan_version,
                operations=proposal.proposed_patch,
                reason=proposal.decision_reason or "Student approved Phase 4 replan",
            ),
            audit_context=audit_context,
            correlation_id=correlation_id,
        )
        proposal = db.scalar(
            select(ReplanProposal)
            .where(ReplanProposal.id == proposal_id)
            .with_for_update()
        )
        assert proposal is not None
        proposal.status = ReplanStatus.APPLIED
        proposal.applied_plan_ref = str(plan.id)
        proposal.applied_plan_version = plan.version
        proposal.applied_at = utc_now()
        proposal.version += 1
        self.audit.record(
            db,
            audit_context,
            action="phase4.replan_applied_to_phase3",
            resource_type="replan",
            resource_id=proposal.id,
            student_id=proposal.student_id,
            after={
                "phase3_plan_ref": proposal.applied_plan_ref,
                "phase3_plan_version": proposal.applied_plan_version,
            },
            metadata={"phase": 4, "target_phase": 3},
        )
        db.commit()
        db.refresh(proposal)
        return ReplanProposalRead.model_validate(proposal)

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)
