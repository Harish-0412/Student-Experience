import hashlib
import json
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from astrapath.agents.contracts import AgentContext, AgentResult
from astrapath.agents.registry import AgentRegistry
from astrapath.audit import AuditContext, AuditService
from astrapath.db import utc_now
from astrapath.enums import AgentRunStatus
from astrapath.models import AgentRun, WorkflowState


def _hash_payload(payload: Any) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class Supervisor:
    def __init__(self, registry: AgentRegistry, audit: AuditService) -> None:
        self.registry = registry
        self.audit = audit

    async def invoke(
        self,
        db: Session,
        workflow: WorkflowState,
        context: AgentContext,
        *,
        agent_name: str,
        input_data: BaseModel,
        idempotency_key: str,
        audit_context: AuditContext,
    ) -> AgentResult:
        existing = db.scalar(
            select(AgentRun).where(AgentRun.idempotency_key == idempotency_key)
        )
        if existing and existing.output_data:
            return AgentResult.model_validate(existing.output_data)

        agent = self.registry.get(agent_name)
        input_hash = _hash_payload(input_data.model_dump(mode="json"))
        run = AgentRun(
            workflow_id=workflow.id,
            agent_name=agent.name,
            agent_version=agent.version,
            status=AgentRunStatus.RUNNING,
            idempotency_key=idempotency_key,
            actor_id=context.actor_id,
            prompt_version="deterministic-v1",
            model_route="none",
            policy_version=context.policy_version,
            input_hash=input_hash,
        )
        db.add(run)
        db.flush()
        try:
            result = await agent.execute(context, input_data)
        except Exception:
            run.status = AgentRunStatus.FAILED
            run.completed_at = utc_now()
            run.error_code = "agent_execution_failed"
            raise
        output = result.model_dump(mode="json")
        run.status = result.status
        run.output_hash = _hash_payload(output)
        run.output_data = output
        run.completed_at = utc_now()
        self.audit.record(
            db,
            audit_context,
            action="agent.invoked",
            resource_type="agent_run",
            resource_id=run.id,
            student_id=context.student_id,
            after={
                "agent": agent.name,
                "version": agent.version,
                "status": result.status.value,
                "input_hash": input_hash,
                "output_hash": run.output_hash,
            },
            metadata={
                "workflow_id": str(workflow.id),
                "idempotency_key": idempotency_key,
            },
        )
        return result

