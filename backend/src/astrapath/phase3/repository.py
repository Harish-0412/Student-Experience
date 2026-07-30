import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from astrapath.errors import AppError
from astrapath.models import Goal
from astrapath.phase2.models import DecisionCard
from astrapath.phase3.contracts import (
    CalendarRead,
    MilestoneRead,
    MilestoneSpec,
    PlanRead,
    ScheduleBlockRead,
    ScheduleConflict,
    ScheduleRead,
    TaskRead,
    TaskSpec,
)
from astrapath.phase3.models import (
    LearningPlan,
    Milestone,
    PlanDecision,
    Schedule,
    ScheduleBlock,
    Task,
)


class Phase3Repository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_goal(self, goal_id: uuid.UUID) -> Goal:
        goal = self.db.get(Goal, goal_id)
        if not goal:
            raise AppError(404, "goal_not_found", "Goal was not found")
        return goal

    def next_plan_version(self, goal_id: uuid.UUID) -> int:
        latest = self.db.scalar(
            select(func.max(LearningPlan.version)).where(
                LearningPlan.goal_id == goal_id
            )
        )
        return int(latest or 0) + 1

    def create_plan(
        self,
        goal: Goal,
        *,
        starts_on: date,
        target_date: date,
        total_estimated_minutes: int,
        generation_constraints: dict[str, Any],
    ) -> LearningPlan:
        plan = LearningPlan(
            goal_id=goal.id,
            student_id=goal.student_id,
            version=self.next_plan_version(goal.id),
            starts_on=starts_on,
            target_date=target_date,
            total_estimated_minutes=total_estimated_minutes,
            generation_constraints=generation_constraints,
        )
        self.db.add(plan)
        self.db.flush()
        return plan

    def persist_work(
        self,
        plan: LearningPlan,
        milestone_specs: list[MilestoneSpec],
        task_specs: list[TaskSpec],
    ) -> tuple[list[Milestone], list[Task], dict[str, Task]]:
        milestones = [
            Milestone(
                plan_id=plan.id,
                goal_id=plan.goal_id,
                graph_node_id=spec.graph_node_id,
                title=spec.title,
                description=spec.description,
                target_date=spec.target_date,
                acceptance_criteria=spec.acceptance_criteria,
                evidence_requirements=spec.evidence_requirements,
                sequence_number=spec.sequence_number,
                estimated_minutes=spec.estimated_minutes,
                buffer_minutes=spec.buffer_minutes,
            )
            for spec in milestone_specs
        ]
        self.db.add_all(milestones)
        self.db.flush()
        milestone_by_key = {
            spec.key: milestone
            for spec, milestone in zip(milestone_specs, milestones, strict=True)
        }
        for spec, milestone in zip(milestone_specs, milestones, strict=True):
            milestone.dependency_ids = [
                str(milestone_by_key[key].id) for key in spec.dependency_keys
            ]
        tasks = [
            Task(
                plan_id=plan.id,
                goal_id=plan.goal_id,
                student_id=plan.student_id,
                milestone_id=milestone_by_key[spec.milestone_key].id,
                competency_id=spec.competency_id,
                title=spec.title,
                description=spec.description,
                task_type=spec.task_type,
                priority=spec.priority,
                estimated_minutes=spec.estimated_minutes,
                evidence_required=spec.evidence_required,
                evidence_description=spec.evidence_description,
                sequence_number=spec.sequence_number,
                task_metadata={
                    "task_key": spec.key,
                    "due_date": spec.due_date.isoformat(),
                },
            )
            for spec in task_specs
        ]
        self.db.add_all(tasks)
        self.db.flush()
        return (
            milestones,
            tasks,
            {
                spec.key: task
                for spec, task in zip(task_specs, tasks, strict=True)
            },
        )

    def replace_schedule(
        self,
        plan: LearningPlan,
        *,
        timezone: str,
        starts_on: date,
        ends_on: date,
        weekly_capacity_minutes: int,
        allocated_minutes: int,
        buffer_minutes: int,
        schedule_health_score: float,
        conflicts: list[dict[str, Any]],
        alternatives: list[str],
        constraints: dict[str, Any],
        block_specs: list[dict[str, Any]],
        task_by_key: dict[str, Task],
    ) -> tuple[Schedule, list[ScheduleBlock]]:
        existing = self.db.scalar(
            select(Schedule).where(Schedule.plan_id == plan.id)
        )
        if existing:
            self.db.execute(
                delete(ScheduleBlock).where(
                    ScheduleBlock.schedule_id == existing.id
                )
            )
            self.db.delete(existing)
            self.db.flush()
        tasks = list(
            self.db.scalars(select(Task).where(Task.plan_id == plan.id)).all()
        )
        for task in tasks:
            task.scheduled_start = None
            task.scheduled_end = None
        schedule = Schedule(
            plan_id=plan.id,
            student_id=plan.student_id,
            timezone=timezone,
            starts_on=starts_on,
            ends_on=ends_on,
            weekly_capacity_minutes=weekly_capacity_minutes,
            allocated_minutes=allocated_minutes,
            buffer_minutes=buffer_minutes,
            schedule_health_score=schedule_health_score,
            conflicts=conflicts,
            alternatives=alternatives,
            constraints=constraints,
        )
        self.db.add(schedule)
        self.db.flush()
        blocks: list[ScheduleBlock] = []
        task_times: dict[uuid.UUID, list[datetime]] = {}
        for spec in block_specs:
            task = task_by_key[spec["task_key"]]
            starts_at = datetime.fromisoformat(spec["starts_at"])
            ends_at = datetime.fromisoformat(spec["ends_at"])
            block = ScheduleBlock(
                schedule_id=schedule.id,
                plan_id=plan.id,
                task_id=task.id,
                student_id=plan.student_id,
                starts_at=starts_at,
                ends_at=ends_at,
                block_type=spec["block_type"],
                energy_level=spec["energy_level"],
            )
            blocks.append(block)
            task_times.setdefault(task.id, []).extend([starts_at, ends_at])
        self.db.add_all(blocks)
        for task in tasks:
            values = task_times.get(task.id)
            if values:
                task.scheduled_start = min(values)
                task.scheduled_end = max(values)
                task.status = "ready"
        self.db.flush()
        return schedule, blocks

    def active_blocks_for_other_goals(
        self,
        student_id: uuid.UUID,
        goal_id: uuid.UUID,
        starts_on: date,
        ends_on: date,
    ) -> list[tuple[ScheduleBlock, Goal]]:
        start_dt = datetime.combine(starts_on, datetime.min.time())
        end_dt = datetime.combine(ends_on, datetime.max.time())
        rows = self.db.execute(
            select(ScheduleBlock, Goal)
            .join(LearningPlan, LearningPlan.id == ScheduleBlock.plan_id)
            .join(Goal, Goal.id == LearningPlan.goal_id)
            .join(Schedule, Schedule.id == ScheduleBlock.schedule_id)
            .where(
                ScheduleBlock.student_id == student_id,
                LearningPlan.goal_id != goal_id,
                LearningPlan.status.in_(["proposed", "approved"]),
                Schedule.status.in_(["proposed", "approved"]),
                ScheduleBlock.status == "planned",
                ScheduleBlock.starts_at <= end_dt,
                ScheduleBlock.ends_at >= start_dt,
            )
            .order_by(ScheduleBlock.starts_at)
        ).all()
        return [(row[0], row[1]) for row in rows]

    def latest_plan(
        self,
        goal_id: uuid.UUID,
        *,
        include_rejected: bool = False,
    ) -> LearningPlan:
        query = select(LearningPlan).where(LearningPlan.goal_id == goal_id)
        if not include_rejected:
            query = query.where(LearningPlan.status != "rejected")
        plan = self.db.scalar(
            query.order_by(LearningPlan.version.desc()).limit(1)
        )
        if not plan:
            raise AppError(404, "plan_not_found", "No generated plan was found")
        return plan

    def get_plan(self, plan_id: uuid.UUID) -> LearningPlan:
        plan = self.db.get(LearningPlan, plan_id)
        if not plan:
            raise AppError(404, "plan_not_found", "Learning plan was not found")
        return plan

    def plan_tasks(self, plan_id: uuid.UUID) -> list[Task]:
        return list(
            self.db.scalars(
                select(Task)
                .where(Task.plan_id == plan_id)
                .order_by(Task.sequence_number)
            ).all()
        )

    def plan_milestones(self, plan_id: uuid.UUID) -> list[Milestone]:
        return list(
            self.db.scalars(
                select(Milestone)
                .where(Milestone.plan_id == plan_id)
                .order_by(Milestone.sequence_number)
            ).all()
        )

    def plan_schedule(
        self, plan_id: uuid.UUID
    ) -> tuple[Schedule, list[ScheduleBlock]]:
        schedule = self.db.scalar(
            select(Schedule).where(Schedule.plan_id == plan_id)
        )
        if not schedule:
            raise AppError(404, "schedule_not_found", "Plan schedule was not found")
        blocks = list(
            self.db.scalars(
                select(ScheduleBlock)
                .where(ScheduleBlock.schedule_id == schedule.id)
                .order_by(ScheduleBlock.starts_at)
            ).all()
        )
        return schedule, blocks

    def record_decision(
        self,
        plan: LearningPlan,
        actor_id: uuid.UUID,
        decision: str,
        reason: str,
        changes: dict[str, Any] | None = None,
    ) -> PlanDecision:
        record = PlanDecision(
            plan_id=plan.id,
            actor_id=actor_id,
            decision=decision,
            reason=reason,
            changes=changes or {},
        )
        self.db.add(record)
        self.db.flush()
        return record

    def supersede_other_plans(self, plan: LearningPlan) -> None:
        others = self.db.scalars(
            select(LearningPlan).where(
                LearningPlan.goal_id == plan.goal_id,
                LearningPlan.id != plan.id,
                LearningPlan.status.in_(["proposed", "approved"]),
            )
        ).all()
        for other in others:
            other.status = "superseded"
            schedule = self.db.scalar(
                select(Schedule).where(Schedule.plan_id == other.id)
            )
            if schedule:
                schedule.status = "superseded"

    def plan_read(self, plan: LearningPlan) -> PlanRead:
        milestones = self.plan_milestones(plan.id)
        tasks = self.plan_tasks(plan.id)
        schedule, blocks = self.plan_schedule(plan.id)
        cards = list(
            self.db.scalars(
                select(DecisionCard)
                .where(
                    DecisionCard.goal_id == plan.goal_id,
                    DecisionCard.decision_type == "phase3_plan",
                )
                .order_by(DecisionCard.created_at)
            ).all()
        )
        return PlanRead(
            id=plan.id,
            goal_id=plan.goal_id,
            student_id=plan.student_id,
            version=plan.version,
            status=plan.status,
            starts_on=plan.starts_on,
            target_date=plan.target_date,
            total_estimated_minutes=plan.total_estimated_minutes,
            generation_constraints=plan.generation_constraints,
            milestones=[MilestoneRead.model_validate(item) for item in milestones],
            tasks=[TaskRead.model_validate(item) for item in tasks],
            schedule=ScheduleRead(
                id=schedule.id,
                timezone=schedule.timezone,
                starts_on=schedule.starts_on,
                ends_on=schedule.ends_on,
                weekly_capacity_minutes=schedule.weekly_capacity_minutes,
                allocated_minutes=schedule.allocated_minutes,
                buffer_minutes=schedule.buffer_minutes,
                schedule_health_score=schedule.schedule_health_score,
                status=schedule.status,
                conflicts=[
                    ScheduleConflict.model_validate(item)
                    for item in schedule.conflicts
                ],
                alternatives=schedule.alternatives,
                constraints=schedule.constraints,
                blocks=[
                    ScheduleBlockRead.model_validate(item) for item in blocks
                ],
            ),
            decision_cards=[
                {
                    "id": str(card.id),
                    "decision": card.decision,
                    "reasons": card.reasons,
                    "evidence": card.evidence,
                    "alternatives": card.alternatives,
                    "approval_required": card.approval_required,
                    "status": card.status,
                    "agent_name": card.agent_name,
                }
                for card in cards
            ],
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )

    def calendar(
        self,
        plan: LearningPlan,
        starts_on: date,
        ends_on: date,
    ) -> CalendarRead:
        schedule, _ = self.plan_schedule(plan.id)
        start_dt = datetime.combine(starts_on, datetime.min.time())
        end_dt = datetime.combine(ends_on, datetime.max.time())
        blocks = list(
            self.db.scalars(
                select(ScheduleBlock)
                .where(
                    ScheduleBlock.schedule_id == schedule.id,
                    ScheduleBlock.starts_at <= end_dt,
                    ScheduleBlock.ends_at >= start_dt,
                )
                .order_by(ScheduleBlock.starts_at)
            ).all()
        )
        total = sum(
            round((item.ends_at - item.starts_at).total_seconds() / 60)
            for item in blocks
        )
        return CalendarRead(
            student_id=plan.student_id,
            starts_on=starts_on,
            ends_on=ends_on,
            blocks=[ScheduleBlockRead.model_validate(item) for item in blocks],
            total_scheduled_minutes=total,
        )
