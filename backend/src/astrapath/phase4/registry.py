import hashlib
import json
import uuid
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from astrapath.db import utc_now
from astrapath.errors import AppError
from astrapath.models import User
from astrapath.phase4.agents import (
    AdaptiveReplanningAgent,
    AssessmentGenerationAgent,
    ContextualTutorAgent,
    EvidenceVerificationAgent,
    FocusSessionCoachAgent,
    MasteryEstimationAgent,
    MotivationHabitCoachAgent,
    ProgressTrackingAgent,
    ResourceCurationAgent,
    RiskBlockerDetectionAgent,
)
from astrapath.phase4.agents.base import AgentDescriptor, Phase4Agent
from astrapath.phase4.contracts import AgentOutput
from astrapath.phase4.enums import AgentExecutionStatus
from astrapath.phase4.models import Phase4AgentRun


def _hash(value: Any) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


class Phase4Registry:
    def __init__(self, agents: list[Phase4Agent[Any, Any]]) -> None:
        self._agents = {agent.name: agent for agent in agents}
        if len(self._agents) != len(agents):
            raise ValueError("Phase 4 agent names must be unique")

    def get(self, name: str) -> Phase4Agent[Any, Any]:
        agent = self._agents.get(name)
        if not agent:
            raise AppError(404, "phase4_agent_not_found", f"Agent '{name}' is not registered")
        return agent

    def descriptors(self) -> list[AgentDescriptor]:
        return [
            AgentDescriptor(
                name=agent.name,
                version=agent.version,
                allowed_tools=sorted(agent.allowed_tools),
                model_route=agent.model_route,
                prompt_version=agent.prompt_version,
                output_schema=agent.output_type.model_json_schema(),
            )
            for agent in sorted(self._agents.values(), key=lambda item: item.name)
        ]


class Phase4AgentRunner:
    policy_version = "phase4-isolated-v1"

    async def run[InputT: BaseModel, OutputT: AgentOutput](
        self,
        db: Session,
        actor: User,
        *,
        student_id: uuid.UUID | None,
        goal_id: uuid.UUID | None,
        agent: Phase4Agent[InputT, OutputT],
        input_data: InputT,
        idempotency_key: str,
    ) -> OutputT:
        input_hash = _hash(input_data.model_dump(mode="json"))
        existing = db.scalar(
            select(Phase4AgentRun).where(
                Phase4AgentRun.idempotency_key == idempotency_key
            )
        )
        if existing:
            if existing.input_hash != input_hash:
                raise AppError(
                    409,
                    "agent_idempotency_conflict",
                    "Agent idempotency key was reused with different input",
                )
            if existing.output_data:
                return agent.output_type.model_validate(existing.output_data)
            raise AppError(
                409,
                "agent_run_in_progress",
                "An agent run with this idempotency key is already in progress",
            )
        run = Phase4AgentRun(
            student_id=student_id,
            goal_id=goal_id,
            actor_id=actor.id,
            agent_name=agent.name,
            agent_version=agent.version,
            status=AgentExecutionStatus.RUNNING,
            idempotency_key=idempotency_key,
            prompt_version=agent.prompt_version,
            model_route=agent.model_route,
            policy_version=self.policy_version,
            input_hash=input_hash,
        )
        db.add(run)
        db.flush()
        try:
            output = await agent.execute(input_data)
        except Exception:
            run.status = AgentExecutionStatus.FAILED
            run.error_code = "phase4_agent_execution_failed"
            run.completed_at = utc_now()
            raise
        output_data = output.model_dump(mode="json")
        run.status = output.status
        run.output_hash = _hash(output_data)
        run.output_data = output_data
        run.completed_at = utc_now()
        return output


def build_phase4_registry() -> Phase4Registry:
    return Phase4Registry(
        [
            ResourceCurationAgent(),
            FocusSessionCoachAgent(),
            ContextualTutorAgent(),
            AssessmentGenerationAgent(),
            EvidenceVerificationAgent(),
            ProgressTrackingAgent(),
            MasteryEstimationAgent(),
            MotivationHabitCoachAgent(),
            RiskBlockerDetectionAgent(),
            AdaptiveReplanningAgent(),
        ]
    )
