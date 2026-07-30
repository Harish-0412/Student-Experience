from datetime import date, datetime

from pydantic import Field

from astrapath.agents.contracts import (
    AgentContext,
    AgentIdentity,
    AgentResult,
    ContractModel,
)
from astrapath.enums import AgentRunStatus


class DailyActionInput(ContractModel):
    task_id: str
    goal_id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    priority: int
    evidence_description: str | None = None


class DailyActionPlanningInput(ContractModel):
    date: date
    timezone: str
    actions: list[DailyActionInput] = Field(default_factory=list)
    stretch_candidates: list[DailyActionInput] = Field(default_factory=list)
    max_daily_minutes: int = Field(default=180, ge=30, le=480)


class DailyActionPlanningAgent:
    name = "daily-action-planning-agent"
    version = "3.0.0"
    identity = AgentIdentity(
        agent_id="agent-9",
        agent_name=name,
        version=version,
        deployment="phase3-rules",
    )
    allowed_tools = frozenset({"task_repository", "priority_engine"})

    async def execute(
        self,
        context: AgentContext,
        input_data: DailyActionPlanningInput,
    ) -> AgentResult:
        actions = sorted(
            input_data.actions,
            key=lambda item: (item.starts_at, item.priority, item.title),
        )
        total = sum(self._minutes(item) for item in actions)
        minimum: list[DailyActionInput] = []
        if actions:
            minimum = [
                min(
                    actions,
                    key=lambda item: (self._minutes(item), item.priority),
                )
            ]
        stretch = (
            sorted(
                input_data.stretch_candidates,
                key=lambda item: (item.priority, item.starts_at),
            )[0]
            if input_data.stretch_candidates
            else None
        )
        warning = (
            f"Today's scheduled load is {total} minutes, above the "
            f"{input_data.max_daily_minutes}-minute limit."
            if total > input_data.max_daily_minutes
            else None
        )
        return AgentResult(
            agent=self.identity,
            status=AgentRunStatus.COMPLETED,
            confidence=1.0,
            summary=f"Selected {len(actions)} scheduled actions for {input_data.date}.",
            data={
                "actions": [item.model_dump(mode="json") for item in actions],
                "minimum_viable_day": [
                    item.model_dump(mode="json") for item in minimum
                ],
                "stretch_task": stretch.model_dump(mode="json") if stretch else None,
                "total_minutes": total,
                "capacity_warning": warning,
            },
            evidence_refs=[f"schedule:{context.student_id}:{input_data.date}"],
            warnings=[warning] if warning else [],
            next_actions=[item.title for item in actions],
            user_visible_explanation=(
                "Today's list follows the approved schedule and includes one "
                "minimum viable action."
            ),
        )

    @staticmethod
    def _minutes(action: DailyActionInput) -> int:
        return round((action.ends_at - action.starts_at).total_seconds() / 60)
