from datetime import date
from typing import Any

from pydantic import Field

from astrapath.agents.contracts import (
    AgentContext,
    AgentIdentity,
    AgentResult,
    ContractModel,
    PatchOperation,
    StatePatch,
)
from astrapath.enums import AgentRunStatus


class StudentProfileInput(ContractModel):
    profile_id: str
    profile_version: int
    profile: dict[str, Any]


class GoalClarificationInput(ContractModel):
    goal_id: str
    goal_version: int
    title: str
    raw_statement: str
    description: str | None = None
    target_date: date | None = None
    priority: int = Field(ge=1, le=5)
    success_criteria: list[str] = Field(default_factory=list)
    profile_summary: dict[str, Any] = Field(default_factory=dict)


class SupervisorGovernanceInput(ContractModel):
    requested_agent: str
    preceding_statuses: list[AgentRunStatus]
    requested_patch_count: int = Field(ge=0)
    high_impact: bool = False


def calculate_profile_completeness(profile: dict[str, Any]) -> tuple[float, list[str], list[str]]:
    required = {
        "display_name": profile.get("display_name"),
        "timezone": profile.get("timezone"),
        "locale": profile.get("locale"),
        "education_level": profile.get("education_level"),
        "weekly_learning_minutes": profile.get("weekly_learning_minutes"),
        "availability": profile.get("availability"),
        "device_access": profile.get("device_access"),
    }
    missing = [name for name, value in required.items() if value in (None, "", [], {})]
    completeness = round((len(required) - len(missing)) / len(required), 2)
    warnings = []
    if profile.get("weekly_learning_minutes", 0) == 0:
        warnings.append("No weekly learning time is currently available.")
    if not profile.get("consent_scopes"):
        warnings.append("Optional integrations will remain disabled until consent is granted.")
    return completeness, missing, warnings


def clarification_questions(input_data: GoalClarificationInput) -> list[str]:
    questions: list[str] = []
    if input_data.target_date is None:
        questions.append("By what date do you want to achieve this goal?")
    if not input_data.success_criteria:
        questions.append("What observable result will prove that this goal is achieved?")
    if len(input_data.raw_statement.split()) < 5:
        questions.append("What specific outcome do you want, beyond the short goal title?")
    if not input_data.profile_summary.get("availability"):
        questions.append("Which days and times can you consistently dedicate to this goal?")
    return questions


class StudentProfileAgent:
    name = "StudentProfileAgent"
    version = "1.0.0"
    identity = AgentIdentity(
        agent_id="agent-01",
        agent_name=name,
        version=version,
    )
    allowed_tools = frozenset({"profile_repository", "policy_engine"})

    async def execute(
        self, context: AgentContext, input_data: StudentProfileInput
    ) -> AgentResult:
        completeness, missing, warnings = calculate_profile_completeness(input_data.profile)
        ready = completeness >= 0.7 and bool(input_data.profile.get("availability"))
        return AgentResult(
            agent=self.identity,
            status=(
                AgentRunStatus.COMPLETED if ready else AgentRunStatus.INPUT_REQUIRED
            ),
            confidence=1.0,
            summary="Student profile completeness was evaluated.",
            data={
                "profile_snapshot": input_data.profile,
                "completeness": completeness,
                "missing_fields": missing,
                "ready_for_goal_planning": ready,
            },
            warnings=warnings,
            next_actions=(
                ["Continue to goal clarification"]
                if ready
                else ["Complete the missing profile fields"]
            ),
            user_visible_explanation=(
                "Your profile is ready for goal planning."
                if ready
                else "A few profile details are needed for reliable planning."
            ),
        )


class GoalClarificationAgent:
    name = "GoalClarificationAgent"
    version = "1.0.0"
    identity = AgentIdentity(
        agent_id="agent-02",
        agent_name=name,
        version=version,
    )
    allowed_tools = frozenset({"policy_engine", "date_calculator"})

    async def execute(
        self, context: AgentContext, input_data: GoalClarificationInput
    ) -> AgentResult:
        questions = clarification_questions(input_data)
        confidence = max(0.45, round(0.95 - len(questions) * 0.12, 2))
        status = (
            AgentRunStatus.INPUT_REQUIRED if questions else AgentRunStatus.COMPLETED
        )
        patches: list[StatePatch] = []
        if input_data.description is None and not questions:
            patches.append(
                StatePatch(
                    aggregate_type="goal",
                    aggregate_id=input_data.goal_id,
                    expected_version=input_data.goal_version,
                    operations=[
                        PatchOperation(
                            op="add",
                            path="/description",
                            value=input_data.raw_statement.strip(),
                        )
                    ],
                )
            )
        return AgentResult(
            agent=self.identity,
            status=status,
            confidence=confidence,
            summary=(
                "The goal has enough detail for feasibility analysis."
                if not questions
                else "The goal needs clarification before feasibility analysis."
            ),
            data={
                "goal_definition": {
                    "title": input_data.title,
                    "statement": input_data.raw_statement,
                    "target_date": (
                        input_data.target_date.isoformat()
                        if input_data.target_date
                        else None
                    ),
                    "priority": input_data.priority,
                },
                "success_criteria": input_data.success_criteria,
                "clarification_questions": questions,
            },
            assumptions=[],
            warnings=[],
            next_actions=(
                ["Continue to feasibility analysis"]
                if not questions
                else ["Answer the clarification questions"]
            ),
            proposed_patches=patches,
            user_visible_explanation=(
                "Your goal is specific enough to analyze."
                if not questions
                else "Please answer the clarification questions before planning begins."
            ),
        )


class SupervisorGovernanceAgent:
    name = "SupervisorGovernanceAgent"
    version = "1.0.0"
    identity = AgentIdentity(
        agent_id="agent-20",
        agent_name=name,
        version=version,
    )
    allowed_tools = frozenset(
        {"agent_registry", "policy_engine", "workflow_store", "audit_service"}
    )

    async def execute(
        self, context: AgentContext, input_data: SupervisorGovernanceInput
    ) -> AgentResult:
        blocked_statuses = {
            AgentRunStatus.FAILED,
            AgentRunStatus.BLOCKED,
            AgentRunStatus.ADMIN_REVIEW_REQUIRED,
        }
        blocked = any(status in blocked_statuses for status in input_data.preceding_statuses)
        approval_required = input_data.high_impact or input_data.requested_patch_count > 0
        if blocked:
            status = AgentRunStatus.BLOCKED
            route = "stop"
        elif approval_required:
            status = AgentRunStatus.STUDENT_APPROVAL_REQUIRED
            route = "student_approval"
        else:
            status = AgentRunStatus.COMPLETED
            route = "continue"
        return AgentResult(
            agent=self.identity,
            status=status,
            confidence=1.0,
            summary=f"Governance selected the '{route}' route.",
            data={
                "route": route,
                "requested_agent": input_data.requested_agent,
                "approval_required": approval_required,
            },
            next_actions=[route],
            user_visible_explanation=(
                "A proposed change needs your approval."
                if approval_required
                else "The workflow passed governance checks."
            ),
        )

