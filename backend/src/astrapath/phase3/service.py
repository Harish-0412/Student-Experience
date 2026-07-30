import hashlib
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from math import ceil
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from astrapath.agents.contracts import AgentContext
from astrapath.agents.supervisor import Supervisor
from astrapath.audit import AuditContext, AuditService
from astrapath.db import utc_now
from astrapath.enums import Role, WorkflowStatus
from astrapath.errors import AppError
from astrapath.models import StudentProfile, User, WorkflowState
from astrapath.phase2.contracts import ClarifiedGoal, DecisionCardData
from astrapath.phase2.models import DecisionCard
from astrapath.phase2.repository import Phase2Repository
from astrapath.phase3.agents.daily import (
    DailyActionInput,
    DailyActionPlanningAgent,
    DailyActionPlanningInput,
)
from astrapath.phase3.agents.milestone import (
    MilestoneDecompositionAgent,
    MilestoneDecompositionInput,
)
from astrapath.phase3.agents.schedule import (
    ExistingBlock,
    ScheduleTimeBudgetAgent,
    ScheduleTimeBudgetInput,
)
from astrapath.phase3.contracts import (
    ApprovedReplanCommand,
    AvailabilityWindow,
    CalendarRead,
    DailyAction,
    DailyPlanRead,
    MilestoneSpec,
    PlanDecisionRequest,
    PlanGenerationRequest,
    PlanRead,
    TaskEditRequest,
    TaskSpec,
    TaskStatusRequest,
)
from astrapath.phase3.integration import ExecutionContextSink
from astrapath.phase3.models import (
    LearningPlan,
    Milestone,
    Schedule,
    ScheduleBlock,
    Task,
)
from astrapath.phase3.repository import Phase3Repository


class PlanningService:
    def __init__(
        self,
        audit: AuditService,
        supervisor: Supervisor,
        execution_sink: ExecutionContextSink | None = None,
    ) -> None:
        self.audit = audit
        self.supervisor = supervisor
        self.execution_sink = execution_sink

    async def generate_plan(
        self,
        db: Session,
        actor: User,
        goal_id: uuid.UUID,
        payload: PlanGenerationRequest,
        *,
        audit_context: AuditContext,
        correlation_id: str,
    ) -> PlanRead:
        repository = Phase3Repository(db)
        phase2 = Phase2Repository(db)
        goal = repository.get_goal(goal_id)
        self._require_goal_access(goal.student_id, actor)
        profile = self._profile(db, goal.student_id)
        state = phase2.get_state(goal.id)
        if not state or not state.graph_summary or not state.skill_gap:
            raise AppError(
                409,
                "phase2_graph_required",
                "Complete Phase 2 skill-gap and graph generation before planning",
            )
        clarified = ClarifiedGoal.model_validate(state.clarification)
        starts_on = payload.starts_on or date.today()
        if starts_on > clarified.target_date:
            raise AppError(
                422,
                "plan_start_after_deadline",
                "Plan start date must not be after the goal target date",
            )
        availability = self._availability(profile, payload)
        graph_nodes, _ = phase2.get_graph(goal.id)
        workflow = self._workflow(
            db,
            goal.student_id,
            goal.id,
            "phase3_plan_generation",
            correlation_id,
        )
        context = self._context(workflow, actor, goal.id, goal.version)
        milestone_input = MilestoneDecompositionInput(
            target_date=clarified.target_date,
            starts_on=starts_on,
            graph_nodes=[
                {
                    "id": node.id,
                    "competency_id": node.competency_id,
                    "node_type": node.node_type,
                    "title": node.title,
                    "required_level": node.required_level,
                    "current_level": node.current_level,
                    "estimated_hours": node.estimated_hours,
                    "sequence_order": node.sequence_order,
                    "is_optional": node.is_optional,
                    "metadata": node.node_metadata,
                }
                for node in graph_nodes
            ],
            core_path=state.graph_summary["core_path"],
            optional_branches=state.graph_summary["optional_branches"],
            include_optional=payload.include_optional,
            buffer_ratio=payload.constraints.buffer_ratio,
        )
        milestone_result = await self.supervisor.invoke(
            db,
            workflow,
            context,
            agent_name=MilestoneDecompositionAgent.name,
            input_data=milestone_input,
            idempotency_key=(
                f"phase3:{goal.id}:{goal.version}:"
                f"{repository.next_plan_version(goal.id)}:milestones"
            ),
            audit_context=audit_context,
        )
        if not milestone_result.data.get("milestones"):
            workflow.status = WorkflowStatus.FAILED
            workflow.current_step = "milestone_generation_blocked"
            db.commit()
            raise AppError(
                409,
                "no_remaining_plan_work",
                "The Phase 2 graph has no remaining competency effort to schedule",
            )
        milestone_specs = [
            self._milestone_spec(item)
            for item in milestone_result.data["milestones"]
        ]
        task_specs = [
            TaskSpec.model_validate(item) for item in milestone_result.data["tasks"]
        ]
        plan = repository.create_plan(
            goal,
            starts_on=starts_on,
            target_date=clarified.target_date,
            total_estimated_minutes=milestone_result.data[
                "total_estimated_minutes"
            ],
            generation_constraints=payload.model_dump(mode="json"),
        )
        _, _, task_by_key = repository.persist_work(
            plan, milestone_specs, task_specs
        )
        workflow.current_step = "schedule_generation"
        schedule_result = await self._invoke_schedule(
            db,
            repository,
            workflow,
            context,
            plan,
            profile,
            availability,
            payload,
            task_specs,
            audit_context,
        )
        repository.replace_schedule(
            plan,
            timezone=profile.timezone,
            starts_on=starts_on,
            ends_on=clarified.target_date,
            weekly_capacity_minutes=schedule_result[
                "weekly_capacity_minutes"
            ],
            allocated_minutes=schedule_result["allocated_minutes"],
            buffer_minutes=schedule_result["buffer_minutes"],
            schedule_health_score=schedule_result["schedule_health_score"],
            conflicts=schedule_result["conflicts"],
            alternatives=schedule_result["alternatives"],
            constraints=payload.constraints.model_dump(mode="json"),
            block_specs=schedule_result["blocks"],
            task_by_key=task_by_key,
        )
        self._replace_plan_cards(
            phase2,
            goal.id,
            plan,
            schedule_result["conflicts"],
            schedule_result["alternatives"],
        )
        workflow.status = WorkflowStatus.APPROVAL_REQUIRED
        workflow.current_step = "student_plan_approval"
        workflow.state_data = {
            "plan_id": str(plan.id),
            "plan_version": plan.version,
            "conflict_count": len(schedule_result["conflicts"]),
        }
        self.audit.record(
            db,
            audit_context,
            action="phase3.plan_generated",
            resource_type="learning_plan",
            resource_id=plan.id,
            student_id=goal.student_id,
            after={
                "version": plan.version,
                "milestone_count": len(milestone_specs),
                "task_count": len(task_specs),
                "conflict_count": len(schedule_result["conflicts"]),
            },
            metadata={"phase": 3, "workflow_id": str(workflow.id)},
        )
        self._sync_execution_context(db, plan, actor, audit_context)
        db.commit()
        return repository.plan_read(plan)

    def get_plan(
        self, db: Session, actor: User, goal_id: uuid.UUID
    ) -> PlanRead:
        repository = Phase3Repository(db)
        goal = repository.get_goal(goal_id)
        self._require_goal_access(goal.student_id, actor)
        return repository.plan_read(
            repository.latest_plan(goal.id, include_rejected=True)
        )

    async def regenerate_schedule(
        self,
        db: Session,
        actor: User,
        goal_id: uuid.UUID,
        payload: PlanGenerationRequest,
        *,
        audit_context: AuditContext,
        correlation_id: str,
    ) -> PlanRead:
        repository = Phase3Repository(db)
        goal = repository.get_goal(goal_id)
        self._require_goal_access(goal.student_id, actor)
        plan = repository.latest_plan(goal.id)
        if plan.status != "proposed":
            raise AppError(
                409,
                "proposed_plan_required",
                "Only a proposed plan can be rescheduled",
            )
        profile = self._profile(db, goal.student_id)
        availability = self._availability(profile, payload)
        tasks = repository.plan_tasks(plan.id)
        task_specs = self._task_specs(repository, plan, tasks)
        workflow = self._workflow(
            db,
            goal.student_id,
            goal.id,
            "phase3_schedule_regeneration",
            correlation_id,
        )
        context = self._context(workflow, actor, goal.id, goal.version)
        schedule_result = await self._invoke_schedule(
            db,
            repository,
            workflow,
            context,
            plan,
            profile,
            availability,
            payload,
            task_specs,
            audit_context,
        )
        task_by_key = {
            str(task.task_metadata["task_key"]): task for task in tasks
        }
        repository.replace_schedule(
            plan,
            timezone=profile.timezone,
            starts_on=plan.starts_on,
            ends_on=plan.target_date,
            weekly_capacity_minutes=schedule_result[
                "weekly_capacity_minutes"
            ],
            allocated_minutes=schedule_result["allocated_minutes"],
            buffer_minutes=schedule_result["buffer_minutes"],
            schedule_health_score=schedule_result["schedule_health_score"],
            conflicts=schedule_result["conflicts"],
            alternatives=schedule_result["alternatives"],
            constraints=payload.constraints.model_dump(mode="json"),
            block_specs=schedule_result["blocks"],
            task_by_key=task_by_key,
        )
        plan.generation_constraints = payload.model_dump(mode="json")
        self._replace_plan_cards(
            Phase2Repository(db),
            goal.id,
            plan,
            schedule_result["conflicts"],
            schedule_result["alternatives"],
        )
        workflow.status = WorkflowStatus.APPROVAL_REQUIRED
        workflow.current_step = "student_plan_approval"
        workflow.state_data = {
            "plan_id": str(plan.id),
            "conflict_count": len(schedule_result["conflicts"]),
        }
        self.audit.record(
            db,
            audit_context,
            action="phase3.schedule_regenerated",
            resource_type="learning_plan",
            resource_id=plan.id,
            student_id=plan.student_id,
            after={"conflict_count": len(schedule_result["conflicts"])},
            metadata={"phase": 3},
        )
        self._sync_execution_context(db, plan, actor, audit_context)
        db.commit()
        return repository.plan_read(plan)

    async def edit_task(
        self,
        db: Session,
        actor: User,
        goal_id: uuid.UUID,
        task_id: uuid.UUID,
        payload: TaskEditRequest,
        *,
        audit_context: AuditContext,
        correlation_id: str,
    ) -> PlanRead:
        repository = Phase3Repository(db)
        goal = repository.get_goal(goal_id)
        self._require_goal_access(goal.student_id, actor)
        plan = repository.latest_plan(goal.id)
        if plan.status != "proposed":
            raise AppError(
                409, "proposed_plan_required", "Only a proposed plan can be edited"
            )
        task = db.get(Task, task_id)
        if not task or task.plan_id != plan.id:
            raise AppError(404, "task_not_found", "Task was not found in this plan")
        before = {
            "title": task.title,
            "priority": task.priority,
            "estimated_minutes": task.estimated_minutes,
        }
        changes = payload.model_dump(exclude={"reason"}, exclude_unset=True)
        for field, value in changes.items():
            setattr(task, field, value)
        plan.total_estimated_minutes = sum(
            item.estimated_minutes for item in repository.plan_tasks(plan.id)
        )
        repository.record_decision(
            plan, actor.id, "edited", payload.reason, changes
        )
        db.flush()
        schedule_payload = PlanGenerationRequest.model_validate(
            plan.generation_constraints
        )
        result = await self.regenerate_schedule(
            db,
            actor,
            goal_id,
            schedule_payload,
            audit_context=audit_context,
            correlation_id=correlation_id,
        )
        self.audit.record(
            db,
            audit_context,
            action="phase3.task_edited",
            resource_type="task",
            resource_id=task.id,
            student_id=goal.student_id,
            before=before,
            after=changes,
            metadata={"phase": 3, "reason": payload.reason},
        )
        db.commit()
        return result

    def update_task_status(
        self,
        db: Session,
        actor: User,
        goal_id: uuid.UUID,
        task_id: uuid.UUID,
        payload: TaskStatusRequest,
        *,
        audit_context: AuditContext,
    ) -> PlanRead:
        repository = Phase3Repository(db)
        goal = repository.get_goal(goal_id)
        self._require_goal_access(goal.student_id, actor)
        plan = repository.latest_plan(goal.id)
        if plan.status != "approved":
            raise AppError(
                409,
                "approved_plan_required",
                "Task execution requires an approved plan",
            )
        task = db.get(Task, task_id)
        if not task or task.plan_id != plan.id:
            raise AppError(404, "task_not_found", "Task was not found in this plan")
        if task.status != payload.expected_status:
            raise AppError(
                409,
                "task_status_conflict",
                "Task status changed before this request was applied",
                {"current_status": task.status},
            )
        transitions = {
            "planned": {"ready", "in_progress", "completed", "blocked"},
            "ready": {"in_progress", "completed", "blocked"},
            "in_progress": {"ready", "completed", "blocked"},
            "blocked": {"ready", "in_progress", "completed"},
            "completed": set(),
        }
        if payload.status not in transitions.get(task.status, set()):
            raise AppError(
                409,
                "invalid_task_transition",
                f"Task cannot move from {task.status} to {payload.status}",
            )
        previous_status = task.status
        task.status = payload.status
        if payload.status == "completed":
            for block in db.scalars(
                select(ScheduleBlock).where(ScheduleBlock.task_id == task.id)
            ):
                block.status = "completed"

        milestone = db.get(Milestone, task.milestone_id)
        if milestone:
            sibling_statuses = [
                item.status
                for item in repository.plan_tasks(plan.id)
                if item.milestone_id == milestone.id
            ]
            if sibling_statuses and all(
                status == "completed" for status in sibling_statuses
            ):
                milestone.status = "completed"
            elif any(status in {"in_progress", "completed"} for status in sibling_statuses):
                milestone.status = "in_progress"
            elif any(status == "blocked" for status in sibling_statuses):
                milestone.status = "blocked"
            else:
                milestone.status = "planned"

        self.audit.record(
            db,
            audit_context,
            action="phase3.task_status_changed",
            resource_type="task",
            resource_id=task.id,
            student_id=goal.student_id,
            before={"status": previous_status},
            after={"status": task.status},
            metadata={"phase": 3, "reason": payload.reason},
        )
        self._sync_execution_context(db, plan, actor, audit_context)
        db.commit()
        return repository.plan_read(plan)

    def decide_plan(
        self,
        db: Session,
        actor: User,
        goal_id: uuid.UUID,
        payload: PlanDecisionRequest,
        *,
        audit_context: AuditContext,
    ) -> PlanRead:
        repository = Phase3Repository(db)
        goal = repository.get_goal(goal_id)
        self._require_goal_access(goal.student_id, actor)
        plan = repository.latest_plan(goal.id, include_rejected=True)
        if plan.status != "proposed":
            raise AppError(
                409,
                "plan_already_decided",
                "Only a proposed plan can be approved or rejected",
            )
        schedule, _ = repository.plan_schedule(plan.id)
        if payload.decision == "approve":
            blocking = [
                item
                for item in schedule.conflicts
                if item.get("severity") == "blocking"
            ]
            if blocking:
                raise AppError(
                    409,
                    "schedule_conflicts_require_resolution",
                    "Resolve blocking schedule conflicts before approving the plan",
                    {"conflicts": blocking},
                )
            plan.status = "approved"
            plan.approved_at = utc_now()
            schedule.status = "approved"
            repository.supersede_other_plans(plan)
            card_status = "accepted"
        else:
            plan.status = "rejected"
            plan.rejected_at = utc_now()
            schedule.status = "rejected"
            card_status = "rejected"
        repository.record_decision(
            plan,
            actor.id,
            "approved" if payload.decision == "approve" else "rejected",
            payload.reason,
        )
        cards = db.scalars(
            select(DecisionCard).where(
                DecisionCard.goal_id == goal.id,
                DecisionCard.decision_type == "phase3_plan",
            )
        ).all()
        for card in cards:
            card.status = card_status
        self.audit.record(
            db,
            audit_context,
            action=f"phase3.plan_{payload.decision}d",
            resource_type="learning_plan",
            resource_id=plan.id,
            student_id=goal.student_id,
            after={"status": plan.status, "reason": payload.reason},
            metadata={"phase": 3},
        )
        self._sync_execution_context(db, plan, actor, audit_context)
        db.commit()
        return repository.plan_read(plan)

    async def apply_approved_replan(
        self,
        db: Session,
        actor: User,
        goal_id: uuid.UUID,
        payload: ApprovedReplanCommand,
        *,
        audit_context: AuditContext,
        correlation_id: str,
    ) -> PlanRead:
        repository = Phase3Repository(db)
        goal = repository.get_goal(goal_id)
        self._require_goal_access(goal.student_id, actor)
        source = repository.get_plan(payload.source_plan_id)
        if (
            source.goal_id != goal.id
            or source.student_id != actor.id
            or source.version != payload.source_plan_version
        ):
            raise AppError(
                409,
                "replan_base_conflict",
                "The approved replan does not match the current plan contract",
            )
        if source.status != "approved":
            raise AppError(
                409,
                "approved_plan_required",
                "A Phase 4 replan can only derive from an approved Phase 3 plan",
            )

        source_milestones = repository.plan_milestones(source.id)
        source_tasks = repository.plan_tasks(source.id)
        milestone_keys = {
            milestone.id: f"milestone:{milestone.id}"
            for milestone in source_milestones
        }
        milestone_specs = [
            MilestoneSpec(
                key=milestone_keys[milestone.id],
                graph_node_id=milestone.graph_node_id,
                competency_id=None,
                title=milestone.title,
                description=milestone.description,
                target_date=milestone.target_date,
                acceptance_criteria=milestone.acceptance_criteria,
                evidence_requirements=milestone.evidence_requirements,
                dependency_keys=[
                    milestone_keys[uuid.UUID(dependency_id)]
                    for dependency_id in milestone.dependency_ids
                    if uuid.UUID(dependency_id) in milestone_keys
                ],
                sequence_number=milestone.sequence_number,
                estimated_minutes=milestone.estimated_minutes,
                buffer_minutes=milestone.buffer_minutes,
            )
            for milestone in source_milestones
        ]
        task_specs = [
            TaskSpec(
                key=str(task.task_metadata["task_key"]),
                milestone_key=milestone_keys[task.milestone_id],
                competency_id=task.competency_id,
                title=task.title,
                description=task.description,
                task_type=task.task_type,
                priority=task.priority,
                estimated_minutes=task.estimated_minutes,
                evidence_required=task.evidence_required,
                evidence_description=task.evidence_description,
                sequence_number=task.sequence_number,
                due_date=next(
                    item.target_date
                    for item in source_milestones
                    if item.id == task.milestone_id
                ),
            )
            for task in source_tasks
        ]
        source_statuses = {
            str(task.task_metadata["task_key"]): task.status for task in source_tasks
        }
        plan_payload = PlanGenerationRequest.model_validate(
            source.generation_constraints
        )
        task_specs, source_statuses, plan_payload = self._apply_replan_operations(
            task_specs,
            source_statuses,
            plan_payload,
            payload.operations,
        )
        plan_payload = plan_payload.model_copy(
            update={
                "integration_metadata": {
                    **plan_payload.integration_metadata,
                    "source": "phase4_replan",
                    "source_plan_id": str(source.id),
                    "source_plan_version": source.version,
                    "operations": payload.operations,
                }
            }
        )
        plan = repository.create_plan(
            goal,
            starts_on=max(source.starts_on, date.today()),
            target_date=source.target_date,
            total_estimated_minutes=sum(
                item.estimated_minutes for item in task_specs
            ),
            generation_constraints=plan_payload.model_dump(mode="json"),
        )
        milestones, tasks, task_by_key = repository.persist_work(
            plan, milestone_specs, task_specs
        )
        milestone_statuses = {
            milestone.sequence_number: milestone.status
            for milestone in source_milestones
        }
        for milestone in milestones:
            milestone.status = milestone_statuses.get(
                milestone.sequence_number, "planned"
            )
        for task in tasks:
            key = str(task.task_metadata["task_key"])
            task.status = source_statuses.get(key, "planned")

        schedulable_specs = [
            item
            for item in task_specs
            if source_statuses.get(item.key, "planned")
            not in {"completed", "dropped"}
        ]
        profile = self._profile(db, goal.student_id)
        availability = self._availability(profile, plan_payload)
        workflow = self._workflow(
            db,
            goal.student_id,
            goal.id,
            "phase3_phase4_replan_application",
            correlation_id,
        )
        context = self._context(workflow, actor, goal.id, plan.version)
        schedule_result = await self._invoke_schedule(
            db,
            repository,
            workflow,
            context,
            plan,
            profile,
            availability,
            plan_payload,
            schedulable_specs,
            audit_context,
        )
        blocking = [
            item
            for item in schedule_result["conflicts"]
            if item.get("severity") == "blocking"
        ]
        if blocking:
            db.rollback()
            raise AppError(
                409,
                "replan_schedule_conflict",
                "The approved replan cannot be scheduled safely",
                {"conflicts": blocking},
            )
        schedule, _ = repository.replace_schedule(
            plan,
            timezone=profile.timezone,
            starts_on=plan.starts_on,
            ends_on=plan.target_date,
            weekly_capacity_minutes=schedule_result[
                "weekly_capacity_minutes"
            ],
            allocated_minutes=schedule_result["allocated_minutes"],
            buffer_minutes=schedule_result["buffer_minutes"],
            schedule_health_score=schedule_result["schedule_health_score"],
            conflicts=schedule_result["conflicts"],
            alternatives=schedule_result["alternatives"],
            constraints=plan_payload.constraints.model_dump(mode="json"),
            block_specs=schedule_result["blocks"],
            task_by_key=task_by_key,
        )
        for task in tasks:
            key = str(task.task_metadata["task_key"])
            preserved_status = source_statuses.get(key)
            if preserved_status in {"completed", "dropped"}:
                task.status = preserved_status
        plan.status = "approved"
        plan.approved_at = utc_now()
        schedule.status = "approved"
        repository.supersede_other_plans(plan)
        repository.record_decision(
            plan,
            actor.id,
            "approved",
            payload.reason,
            {"phase4_operations": payload.operations},
        )
        self._replace_plan_cards(
            Phase2Repository(db),
            goal.id,
            plan,
            schedule_result["conflicts"],
            schedule_result["alternatives"],
        )
        for card in db.scalars(
            select(DecisionCard).where(
                DecisionCard.goal_id == goal.id,
                DecisionCard.decision_type == "phase3_plan",
            )
        ):
            card.status = "accepted"
        workflow.status = WorkflowStatus.COMPLETED
        workflow.current_step = "phase4_replan_applied"
        workflow.state_data = {
            "source_plan_id": str(source.id),
            "plan_id": str(plan.id),
            "plan_version": plan.version,
        }
        self.audit.record(
            db,
            audit_context,
            action="phase3.phase4_replan_applied",
            resource_type="learning_plan",
            resource_id=plan.id,
            student_id=goal.student_id,
            before={"plan_id": str(source.id), "version": source.version},
            after={"plan_id": str(plan.id), "version": plan.version},
            metadata={"phase": 3, "phase4_operations": payload.operations},
        )
        self._sync_execution_context(db, plan, actor, audit_context)
        db.commit()
        return repository.plan_read(plan)

    def calendar(
        self,
        db: Session,
        actor: User,
        goal_id: uuid.UUID,
        starts_on: date,
        ends_on: date,
    ) -> CalendarRead:
        if ends_on < starts_on:
            raise AppError(
                422, "invalid_calendar_range", "Calendar end must be after start"
            )
        repository = Phase3Repository(db)
        goal = repository.get_goal(goal_id)
        self._require_goal_access(goal.student_id, actor)
        return repository.calendar(
            repository.latest_plan(goal.id), starts_on, ends_on
        )

    async def daily_plan(
        self,
        db: Session,
        actor: User,
        plan_date: date,
        *,
        audit_context: AuditContext,
        correlation_id: str,
    ) -> DailyPlanRead:
        profile = self._profile(db, actor.id)
        start_dt = datetime.combine(plan_date, datetime.min.time())
        end_dt = datetime.combine(plan_date, datetime.max.time())
        tomorrow_end = end_dt + timedelta(days=1)
        rows = db.execute(
            select(ScheduleBlock, Task)
            .join(Task, Task.id == ScheduleBlock.task_id)
            .join(LearningPlan, LearningPlan.id == ScheduleBlock.plan_id)
            .join(Schedule, Schedule.id == ScheduleBlock.schedule_id)
            .where(
                ScheduleBlock.student_id == actor.id,
                LearningPlan.status == "approved",
                Schedule.status == "approved",
                ScheduleBlock.status == "planned",
                ScheduleBlock.starts_at <= tomorrow_end,
                ScheduleBlock.ends_at >= start_dt,
            )
            .order_by(ScheduleBlock.starts_at)
        ).all()
        today_actions: list[DailyActionInput] = []
        stretch_actions: list[DailyActionInput] = []
        for block, task in rows:
            item = DailyActionInput(
                task_id=str(task.id),
                goal_id=str(task.goal_id),
                title=task.title,
                starts_at=block.starts_at,
                ends_at=block.ends_at,
                priority=task.priority,
                evidence_description=task.evidence_description,
            )
            if block.starts_at.date() == plan_date:
                today_actions.append(item)
            elif block.starts_at.date() == plan_date + timedelta(days=1):
                stretch_actions.append(item)
        workflow = self._workflow(
            db,
            actor.id,
            None,
            "phase3_daily_plan",
            correlation_id,
        )
        context = self._context(workflow, actor, None, None)
        result = await self.supervisor.invoke(
            db,
            workflow,
            context,
            agent_name=DailyActionPlanningAgent.name,
            input_data=DailyActionPlanningInput(
                date=plan_date,
                timezone=profile.timezone,
                actions=today_actions,
                stretch_candidates=stretch_actions,
            ),
            idempotency_key=f"phase3:daily:{actor.id}:{plan_date.isoformat()}",
            audit_context=audit_context,
        )
        workflow.status = WorkflowStatus.COMPLETED
        workflow.current_step = "daily_plan_created"
        workflow.state_data = {"date": plan_date.isoformat()}
        db.commit()
        return DailyPlanRead(
            date=plan_date,
            timezone=profile.timezone,
            daily_plan=[
                self._daily_action(item)
                for item in result.data["actions"]
            ],
            minimum_viable_day=[
                self._daily_action(item)
                for item in result.data["minimum_viable_day"]
            ],
            stretch_task=(
                self._daily_action(result.data["stretch_task"])
                if result.data["stretch_task"]
                else None
            ),
            total_minutes=result.data["total_minutes"],
            capacity_warning=result.data["capacity_warning"],
        )

    @staticmethod
    def _apply_replan_operations(
        task_specs: list[TaskSpec],
        statuses: dict[str, str],
        plan_payload: PlanGenerationRequest,
        operations: list[dict[str, Any]],
    ) -> tuple[list[TaskSpec], dict[str, str], PlanGenerationRequest]:
        specs = list(task_specs)
        task_statuses = dict(statuses)
        supported = {
            "reduce_weekly_load",
            "prioritize_essential_outcomes",
            "insert_remediation_block",
            "replace_resource",
            "split_next_task",
        }
        for operation in operations:
            operation_name = str(operation.get("op", ""))
            if operation_name not in supported:
                raise AppError(
                    422,
                    "unsupported_replan_operation",
                    f"Unsupported Phase 4 replan operation: {operation_name}",
                )
            if operation_name == "reduce_weekly_load":
                percentage = max(
                    1,
                    min(int(operation.get("percentage", 20)), 80),
                )
                current_daily = plan_payload.constraints.max_daily_minutes
                constraints = plan_payload.constraints.model_copy(
                    update={
                        "max_daily_minutes": max(
                            30,
                            round(current_daily * (1 - percentage / 100)),
                        )
                    }
                )
                plan_payload = plan_payload.model_copy(
                    update={"constraints": constraints}
                )
            elif operation_name == "prioritize_essential_outcomes":
                specs = [
                    item.model_copy(
                        update={"priority": max(1, item.priority - 1)}
                    )
                    if item.evidence_required
                    and task_statuses.get(item.key) not in {"completed", "dropped"}
                    else item
                    for item in specs
                ]
            elif operation_name == "insert_remediation_block":
                target = next(
                    (
                        item
                        for item in sorted(
                            specs, key=lambda value: value.sequence_number
                        )
                        if task_statuses.get(item.key) not in {"completed", "dropped"}
                    ),
                    None,
                )
                if target:
                    specs = [
                        item.model_copy(
                            update={
                                "sequence_number": item.sequence_number + 1
                            }
                        )
                        if item.sequence_number >= target.sequence_number
                        else item
                        for item in specs
                    ]
                    remediation_key = f"phase4-remediation:{uuid.uuid4()}"
                    specs.append(
                        TaskSpec(
                            key=remediation_key,
                            milestone_key=target.milestone_key,
                            competency_id=target.competency_id,
                            title=f"Remediation: {target.title}",
                            description=(
                                "Resolve the prerequisite gap identified by "
                                "Phase 4 before continuing."
                            ),
                            task_type="learn",
                            priority=1,
                            estimated_minutes=max(
                                15,
                                min(
                                    int(operation.get("duration_minutes", 90)),
                                    2400,
                                ),
                            ),
                            evidence_required=False,
                            evidence_description=None,
                            sequence_number=target.sequence_number,
                            due_date=target.due_date,
                        )
                    )
                    task_statuses[remediation_key] = "planned"
            elif operation_name == "split_next_task":
                target = next(
                    (
                        item
                        for item in sorted(
                            specs, key=lambda value: value.sequence_number
                        )
                        if task_statuses.get(item.key) not in {"completed", "dropped"}
                        and item.estimated_minutes > 30
                    ),
                    None,
                )
                if target:
                    first_minutes = ceil(target.estimated_minutes / 2)
                    second_minutes = target.estimated_minutes - first_minutes
                    first_key = f"{target.key}:part-1"
                    second_key = f"{target.key}:part-2"
                    replacement = [
                        target.model_copy(
                            update={
                                "key": first_key,
                                "title": f"{target.title} (part 1)",
                                "estimated_minutes": first_minutes,
                            }
                        ),
                        target.model_copy(
                            update={
                                "key": second_key,
                                "title": f"{target.title} (part 2)",
                                "estimated_minutes": second_minutes,
                                "sequence_number": target.sequence_number + 1,
                            }
                        ),
                    ]
                    specs = [
                        item.model_copy(
                            update={
                                "sequence_number": item.sequence_number + 1
                            }
                        )
                        if item.sequence_number > target.sequence_number
                        else item
                        for item in specs
                        if item.key != target.key
                    ]
                    specs.extend(replacement)
                    task_statuses.pop(target.key, None)
                    task_statuses[first_key] = "planned"
                    task_statuses[second_key] = "planned"
            # Resource replacement belongs to Phase 4; Phase 3 records the
            # operation in integration metadata and preserves the task plan.
        return (
            sorted(specs, key=lambda value: value.sequence_number),
            task_statuses,
            plan_payload,
        )

    async def _invoke_schedule(
        self,
        db: Session,
        repository: Phase3Repository,
        workflow: WorkflowState,
        context: AgentContext,
        plan: LearningPlan,
        profile: StudentProfile,
        availability: dict[str, list[AvailabilityWindow]],
        payload: PlanGenerationRequest,
        task_specs: list[TaskSpec],
        audit_context: AuditContext,
    ) -> dict[str, Any]:
        existing = repository.active_blocks_for_other_goals(
            plan.student_id, plan.goal_id, plan.starts_on, plan.target_date
        )
        schedule_input = ScheduleTimeBudgetInput(
            timezone=profile.timezone,
            starts_on=plan.starts_on,
            target_date=plan.target_date,
            weekly_budget_minutes=profile.weekly_learning_minutes,
            tasks=task_specs,
            availability=availability,
            constraints=payload.constraints,
            fixed_commitments=payload.fixed_commitments,
            existing_blocks=[
                ExistingBlock(
                    starts_at=block.starts_at,
                    ends_at=block.ends_at,
                    goal_id=str(goal.id),
                    goal_title=goal.title,
                    goal_target_date=goal.target_date or plan.target_date,
                )
                for block, goal in existing
            ],
        )
        input_hash = hashlib.sha256(
            json.dumps(
                schedule_input.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()[:16]
        result = await self.supervisor.invoke(
            db,
            workflow,
            context,
            agent_name=ScheduleTimeBudgetAgent.name,
            input_data=schedule_input,
            idempotency_key=f"phase3:{plan.id}:schedule:{input_hash}",
            audit_context=audit_context,
        )
        return result.data

    def _sync_execution_context(
        self,
        db: Session,
        plan: LearningPlan,
        actor: User,
        audit_context: AuditContext,
    ) -> None:
        if not self.execution_sink:
            return
        db.flush()
        self.execution_sink.sync_plan(
            db,
            plan,
            actor=actor,
            audit_context=audit_context,
        )

    @staticmethod
    def _task_specs(
        repository: Phase3Repository,
        plan: LearningPlan,
        tasks: list[Task],
    ) -> list[TaskSpec]:
        milestones = {
            item.id: item for item in repository.plan_milestones(plan.id)
        }
        return [
            TaskSpec(
                key=str(task.task_metadata["task_key"]),
                milestone_key=f"milestone:{task.milestone_id}",
                competency_id=task.competency_id,
                title=task.title,
                description=task.description,
                task_type=task.task_type,
                priority=task.priority,
                estimated_minutes=task.estimated_minutes,
                evidence_required=task.evidence_required,
                evidence_description=task.evidence_description,
                sequence_number=task.sequence_number,
                due_date=milestones[task.milestone_id].target_date,
            )
            for task in tasks
        ]

    @staticmethod
    def _milestone_spec(value: dict[str, Any]) -> MilestoneSpec:
        return MilestoneSpec.model_validate(value)

    @staticmethod
    def _profile(db: Session, student_id: uuid.UUID) -> StudentProfile:
        profile = db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == student_id)
        )
        if not profile:
            raise AppError(
                409,
                "student_profile_required",
                "Complete onboarding before generating a plan",
            )
        if profile.weekly_learning_minutes <= 0:
            raise AppError(
                422,
                "weekly_capacity_required",
                "Weekly learning capacity must be greater than zero",
            )
        return profile

    @staticmethod
    def _availability(
        profile: StudentProfile,
        payload: PlanGenerationRequest,
    ) -> dict[str, list[AvailabilityWindow]]:
        source = payload.constraints.availability or profile.availability
        availability = {
            day.lower(): [
                item
                if isinstance(item, AvailabilityWindow)
                else AvailabilityWindow.model_validate(item)
                for item in windows
            ]
            for day, windows in source.items()
        }
        if not any(availability.values()):
            raise AppError(
                422,
                "availability_required",
                "At least one weekly availability window is required",
            )
        return availability

    @staticmethod
    def _workflow(
        db: Session,
        student_id: uuid.UUID,
        goal_id: uuid.UUID | None,
        workflow_type: str,
        correlation_id: str,
    ) -> WorkflowState:
        workflow = WorkflowState(
            workflow_type=workflow_type,
            student_id=student_id,
            goal_id=goal_id,
            status=WorkflowStatus.RUNNING,
            current_step="created",
            correlation_id=correlation_id,
        )
        db.add(workflow)
        db.flush()
        return workflow

    @staticmethod
    def _context(
        workflow: WorkflowState,
        actor: User,
        goal_id: uuid.UUID | None,
        plan_version: int | None,
    ) -> AgentContext:
        return AgentContext(
            workflow_id=workflow.id,
            correlation_id=workflow.correlation_id,
            actor_id=actor.id,
            actor_role=actor.role,
            student_id=workflow.student_id,
            goal_id=goal_id,
            plan_version=plan_version,
            policy_version="phase1.1",
            request_time=datetime.now(UTC),
            metadata={"phase": 3},
        )

    @staticmethod
    def _replace_plan_cards(
        phase2: Phase2Repository,
        goal_id: uuid.UUID,
        plan: LearningPlan,
        conflicts: list[dict[str, Any]],
        alternatives: list[str],
    ) -> None:
        cards = [
            DecisionCardData(
                decision_type="phase3_plan",
                decision=f"Review learning plan version {plan.version}",
                reasons=[
                    "Milestones follow the approved prerequisite graph",
                    "Tasks include learning, practice, application, and review",
                ],
                evidence=[
                    f"goal_graph:{goal_id}",
                    f"learning_plan:{plan.id}",
                ],
                alternatives=["Edit task effort or regenerate the schedule"],
                approval_required=True,
                agent_name=MilestoneDecompositionAgent.name,
            )
        ]
        if conflicts:
            cards.append(
                DecisionCardData(
                    decision_type="phase3_plan",
                    decision="Resolve schedule conflicts before approving the plan",
                    reasons=[item["message"] for item in conflicts[:5]],
                    evidence=[
                        evidence
                        for item in conflicts
                        for evidence in item.get("evidence", [])
                    ],
                    alternatives=alternatives,
                    approval_required=True,
                    agent_name=ScheduleTimeBudgetAgent.name,
                )
            )
        phase2.replace_decision_cards(goal_id, "phase3_plan", cards)

    @staticmethod
    def _require_goal_access(student_id: uuid.UUID, actor: User) -> None:
        if actor.role == Role.ADMIN:
            return
        if actor.role != Role.STUDENT or actor.id != student_id:
            raise AppError(403, "forbidden", "Students can access only their own goals")

    @staticmethod
    def _daily_action(value: dict[str, Any]) -> DailyAction:
        starts_at = datetime.fromisoformat(value["starts_at"])
        ends_at = datetime.fromisoformat(value["ends_at"])
        return DailyAction(
            task_id=uuid.UUID(value["task_id"]),
            goal_id=uuid.UUID(value["goal_id"]),
            title=value["title"],
            starts_at=starts_at,
            ends_at=ends_at,
            estimated_minutes=round((ends_at - starts_at).total_seconds() / 60),
            priority=value["priority"],
            reason="Scheduled now because it is the next prerequisite-aware action",
            completion_evidence=value.get("evidence_description"),
        )
