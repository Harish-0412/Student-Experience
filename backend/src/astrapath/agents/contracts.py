import uuid
from datetime import datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from astrapath.enums import AgentRunStatus, Role


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentIdentity(ContractModel):
    agent_id: str
    agent_name: str
    version: str
    deployment: str = "local"
    a2a_card_hash: str | None = None


class AgentBudget(ContractModel):
    max_runtime_seconds: int = Field(default=45, ge=1, le=300)
    max_model_requests: int = Field(default=4, ge=0, le=20)
    max_tool_calls: int = Field(default=8, ge=0, le=40)
    max_input_tokens: int = Field(default=24_000, ge=100, le=200_000)
    max_output_tokens: int = Field(default=4_000, ge=100, le=50_000)


class AgentContext(ContractModel):
    workflow_id: uuid.UUID
    correlation_id: str
    causation_id: str | None = None
    actor_id: uuid.UUID
    actor_role: Role
    student_id: uuid.UUID
    goal_id: uuid.UUID | None = None
    plan_version: int | None = None
    policy_version: str
    consent_scopes: set[str] = Field(default_factory=set)
    locale: str = "en-IN"
    timezone: str = "Asia/Kolkata"
    request_time: datetime
    budget: AgentBudget = Field(default_factory=AgentBudget)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PatchOperation(ContractModel):
    op: Literal["add", "replace", "remove"]
    path: str
    value: Any = None


class StatePatch(ContractModel):
    aggregate_type: str
    aggregate_id: str
    expected_version: int
    operations: list[PatchOperation]


class AgentResult(ContractModel):
    agent: AgentIdentity
    status: AgentRunStatus
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    data: dict[str, Any]
    assumptions: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    proposed_patches: list[StatePatch] = Field(default_factory=list)
    user_visible_explanation: str


class AgentProtocol[InputT: BaseModel, OutputT: BaseModel](Protocol):
    name: str
    version: str
    identity: AgentIdentity
    allowed_tools: frozenset[str]

    async def execute(self, context: AgentContext, input_data: InputT) -> AgentResult: ...
