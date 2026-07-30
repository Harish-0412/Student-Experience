from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import Field

from astrapath.agents.contracts import (
    AgentContext,
    AgentIdentity,
    AgentResult,
    ContractModel,
)
from astrapath.enums import AgentRunStatus
from astrapath.phase3.contracts import (
    AvailabilityWindow,
    FixedCommitment,
    ScheduleBlockSpec,
    ScheduleConflict,
    SchedulingConstraints,
    TaskSpec,
)


class ExistingBlock(ContractModel):
    starts_at: datetime
    ends_at: datetime
    goal_id: str
    goal_title: str
    goal_target_date: date


class ScheduleTimeBudgetInput(ContractModel):
    timezone: str
    starts_on: date
    target_date: date
    weekly_budget_minutes: int = Field(gt=0, le=10080)
    tasks: list[TaskSpec]
    availability: dict[str, list[AvailabilityWindow]]
    constraints: SchedulingConstraints
    fixed_commitments: list[FixedCommitment] = Field(default_factory=list)
    existing_blocks: list[ExistingBlock] = Field(default_factory=list)


class _Slot:
    def __init__(
        self,
        starts_at: datetime,
        ends_at: datetime,
        energy_level: str,
    ) -> None:
        self.starts_at = starts_at
        self.ends_at = ends_at
        self.energy_level = energy_level
        self.used = False

    @property
    def minutes(self) -> int:
        return round((self.ends_at - self.starts_at).total_seconds() / 60)


class ScheduleTimeBudgetAgent:
    name = "schedule-time-budget-agent"
    version = "3.0.0"
    identity = AgentIdentity(
        agent_id="agent-8",
        agent_name=name,
        version=version,
        deployment="phase3-constraint-solver",
    )
    allowed_tools = frozenset(
        {"constraint_solver", "time_zone_service", "effort_estimator"}
    )

    async def execute(
        self,
        context: AgentContext,
        input_data: ScheduleTimeBudgetInput,
    ) -> AgentResult:
        zone = ZoneInfo(input_data.timezone)
        blockers = self._blockers(input_data, zone)
        slots = self._build_slots(input_data, zone, blockers)
        block_specs: list[ScheduleBlockSpec] = []
        conflicts: list[ScheduleConflict] = []
        total_required = sum(task.estimated_minutes for task in input_data.tasks)
        unscheduled_total = 0
        not_before = datetime.combine(
            input_data.starts_on, time.min, tzinfo=zone
        )

        for task in sorted(input_data.tasks, key=lambda item: item.sequence_number):
            remaining = task.estimated_minutes
            due_end = datetime.combine(task.due_date, time.max, tzinfo=zone)
            candidates = [
                slot
                for slot in slots
                if (
                    not slot.used
                    and slot.starts_at >= not_before
                    and slot.starts_at <= due_end
                )
            ]
            candidates.sort(
                key=lambda slot: (
                    slot.starts_at.date(),
                    self._energy_rank(task.task_type, slot.energy_level),
                    slot.starts_at,
                )
            )
            task_ends: list[datetime] = []
            for slot in candidates:
                if remaining <= 0:
                    break
                minutes = min(remaining, slot.minutes)
                if minutes <= 0:
                    continue
                ends_at = slot.starts_at + timedelta(minutes=minutes)
                block_specs.append(
                    ScheduleBlockSpec(
                        task_key=task.key,
                        starts_at=slot.starts_at,
                        ends_at=ends_at,
                        block_type=(
                            "review" if task.task_type == "review" else "study"
                        ),
                        energy_level=slot.energy_level,
                    )
                )
                slot.used = True
                remaining -= minutes
                task_ends.append(ends_at)
            if task_ends:
                not_before = max(task_ends)
            if remaining > 0:
                unscheduled_total += remaining
                conflicts.append(
                    ScheduleConflict(
                        code="deadline_capacity_shortfall",
                        severity="blocking",
                        message=(
                            f"{remaining} minutes of '{task.title}' cannot be placed "
                            f"before {task.due_date.isoformat()}."
                        ),
                        task_key=task.key,
                        unscheduled_minutes=remaining,
                        evidence=[
                            f"task:{task.key}",
                            f"deadline:{task.due_date.isoformat()}",
                            "student_availability",
                        ],
                    )
                )

        if input_data.existing_blocks and unscheduled_total:
            nearest = min(
                input_data.existing_blocks,
                key=lambda item: item.goal_target_date,
            )
            conflicts.append(
                ScheduleConflict(
                    code="cross_goal_deadline_conflict",
                    severity="blocking",
                    message=(
                        f"Existing work for '{nearest.goal_title}' reserves capacity "
                        f"before its {nearest.goal_target_date.isoformat()} deadline."
                    ),
                    unscheduled_minutes=unscheduled_total,
                    evidence=[
                        f"goal:{nearest.goal_id}",
                        f"goal:{context.goal_id}",
                    ],
                )
            )
        if not slots:
            conflicts.append(
                ScheduleConflict(
                    code="no_usable_availability",
                    severity="blocking",
                    message=(
                        "No usable study windows remain after fixed commitments "
                        "and scheduling limits."
                    ),
                    unscheduled_minutes=total_required,
                    evidence=["student_availability", "fixed_commitments"],
                )
            )

        allocated = sum(
            round((block.ends_at - block.starts_at).total_seconds() / 60)
            for block in block_specs
        )
        weeks = max(
            1, ((input_data.target_date - input_data.starts_on).days // 7) + 1
        )
        usable_slot_minutes = sum(slot.minutes for slot in slots)
        average_usable_weekly = round(usable_slot_minutes / weeks)
        effective_weekly_capacity = min(
            input_data.weekly_budget_minutes,
            round(
                average_usable_weekly
                / max(0.01, 1 - input_data.constraints.buffer_ratio)
            ),
        )
        reserved_buffer = round(
            weeks
            * effective_weekly_capacity
            * input_data.constraints.buffer_ratio
        )
        health = max(
            0.0,
            min(
                1.0,
                0.95
                - (unscheduled_total / max(total_required, 1)) * 0.75
                - (0.1 if input_data.existing_blocks and unscheduled_total else 0),
            ),
        )
        alternatives: list[str] = []
        if unscheduled_total:
            extra_weeks = max(
                1,
                round(
                    unscheduled_total
                    / max(
                        1,
                        input_data.weekly_budget_minutes
                        * (1 - input_data.constraints.buffer_ratio),
                    )
                ),
            )
            alternatives.extend(
                [
                    f"Extend the deadline by about {extra_weeks} weeks",
                    "Increase availability without reducing protected commitments",
                    "Defer optional scope or reduce task effort with student approval",
                ]
            )
        else:
            alternatives.append("Approve this schedule and preserve the reserved buffer")

        status = (
            AgentRunStatus.STUDENT_APPROVAL_REQUIRED
            if conflicts
            else AgentRunStatus.COMPLETED
        )
        return AgentResult(
            agent=self.identity,
            status=status,
            confidence=0.94,
            summary=(
                f"Scheduled {allocated} of {total_required} required minutes "
                f"with {len(conflicts)} conflicts."
            ),
            data={
                "blocks": [item.model_dump(mode="json") for item in block_specs],
                "conflicts": [item.model_dump(mode="json") for item in conflicts],
                "alternatives": alternatives,
                "weekly_capacity_minutes": effective_weekly_capacity,
                "allocated_minutes": allocated,
                "buffer_minutes": reserved_buffer,
                "schedule_health_score": round(health, 2),
            },
            assumptions=[
                "Availability repeats weekly through the target date",
                "Fixed commitments and existing goal blocks cannot be overwritten",
                "Reserved buffer remains intentionally unscheduled",
            ],
            evidence_refs=[
                "student_availability",
                "fixed_commitments",
                "existing_schedule_blocks",
            ],
            warnings=[item.message for item in conflicts],
            next_actions=alternatives,
            user_visible_explanation=(
                "The schedule fits tasks only into declared availability, preserves "
                "buffer time, and leaves conflicting commitments unchanged."
            ),
        )

    def _build_slots(
        self,
        input_data: ScheduleTimeBudgetInput,
        zone: ZoneInfo,
        blockers: list[tuple[datetime, datetime]],
    ) -> list[_Slot]:
        slots: list[_Slot] = []
        day = input_data.starts_on
        usable_weekly = max(
            15,
            round(
                input_data.weekly_budget_minutes
                * (1 - input_data.constraints.buffer_ratio)
            ),
        )
        weekly_used: dict[tuple[int, int], int] = {}
        while day <= input_data.target_date:
            weekday = day.strftime("%A").lower()
            windows = input_data.availability.get(weekday, [])
            daily_used = 0
            iso = day.isocalendar()
            week_key = (iso.year, iso.week)
            weekly_used.setdefault(week_key, 0)
            for window in windows:
                cursor = datetime.combine(day, window.start, tzinfo=zone)
                window_end = datetime.combine(day, window.end, tzinfo=zone)
                while cursor < window_end:
                    blocker = next(
                        (
                            item
                            for item in blockers
                            if item[0] < window_end
                            and item[1] > cursor
                        ),
                        None,
                    )
                    if blocker and blocker[0] <= cursor:
                        cursor = blocker[1] + timedelta(
                            minutes=input_data.constraints.minimum_break_minutes
                        )
                        continue
                    limit = min(
                        window_end,
                        cursor
                        + timedelta(minutes=input_data.constraints.max_session_minutes),
                        blocker[0] if blocker else window_end,
                    )
                    minutes = round((limit - cursor).total_seconds() / 60)
                    daily_remaining = (
                        input_data.constraints.max_daily_minutes - daily_used
                    )
                    weekly_remaining = usable_weekly - weekly_used[week_key]
                    minutes = min(minutes, daily_remaining, weekly_remaining)
                    if minutes < 15:
                        break
                    slot_end = cursor + timedelta(minutes=minutes)
                    slots.append(_Slot(cursor, slot_end, window.energy))
                    daily_used += minutes
                    weekly_used[week_key] += minutes
                    if (
                        daily_used >= input_data.constraints.max_daily_minutes
                        or weekly_used[week_key] >= usable_weekly
                    ):
                        break
                    cursor = slot_end + timedelta(
                        minutes=input_data.constraints.minimum_break_minutes
                    )
            day += timedelta(days=1)
        return slots

    @staticmethod
    def _blockers(
        input_data: ScheduleTimeBudgetInput,
        zone: ZoneInfo,
    ) -> list[tuple[datetime, datetime]]:
        values = [
            (item.starts_at, item.ends_at)
            for item in [
                *input_data.fixed_commitments,
                *input_data.constraints.do_not_disturb,
            ]
        ]
        values.extend(
            (item.starts_at, item.ends_at) for item in input_data.existing_blocks
        )
        normalized = [
            (
                ScheduleTimeBudgetAgent._aware(start, zone),
                ScheduleTimeBudgetAgent._aware(end, zone),
            )
            for start, end in values
        ]
        return sorted(normalized, key=lambda item: item[0])

    @staticmethod
    def _aware(value: datetime, zone: ZoneInfo) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=zone)
        return value.astimezone(zone)

    @staticmethod
    def _energy_rank(task_type: str, energy_level: str) -> int:
        if task_type in {"practice", "apply"}:
            return {"high": 0, "medium": 1, "low": 2}[energy_level]
        return {"medium": 0, "low": 1, "high": 2}[energy_level]
