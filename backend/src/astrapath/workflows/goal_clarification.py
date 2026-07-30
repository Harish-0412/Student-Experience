from datetime import UTC, datetime
from operator import add
from typing import Annotated, Any, TypedDict, cast

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from astrapath.agents.contracts import AgentBudget, AgentContext, AgentResult
from astrapath.agents.kernel import (
    GoalClarificationInput,
    StudentProfileInput,
    SupervisorGovernanceInput,
)
from astrapath.agents.supervisor import Supervisor
from astrapath.audit import AuditContext, AuditService
from astrapath.enums import AgentRunStatus, WorkflowStatus
from astrapath.models import Goal, StudentProfile, User, WorkflowState
from astrapath.schemas import StudentProfileRead


class GoalWorkflowGraphState(TypedDict, total=False):
    profile_result: dict[str, Any]
    clarification_result: dict[str, Any]
    governance_result: dict[str, Any]
    messages: Annotated[list[dict[str, Any]], add]


async def run_goal_clarification_workflow(
    db: Session,
    student: User,
    profile: StudentProfile,
    goal: Goal,
    *,
    correlation_id: str,
    supervisor: Supervisor,
    audit: AuditService,
    audit_context: AuditContext,
) -> tuple[WorkflowState, AgentResult]:
    workflow = WorkflowState(
        workflow_type="goal_clarification",
        student_id=student.id,
        goal_id=goal.id,
        status=WorkflowStatus.RUNNING,
        current_step="profile",
        correlation_id=correlation_id,
        state_data={},
    )
    db.add(workflow)
    db.flush()
    audit.record(
        db,
        audit_context,
        action="workflow.started",
        resource_type="workflow",
        resource_id=workflow.id,
        student_id=student.id,
        after={"workflow_type": workflow.workflow_type, "goal_id": str(goal.id)},
    )
    context = AgentContext(
        workflow_id=workflow.id,
        correlation_id=correlation_id,
        actor_id=student.id,
        actor_role=student.role,
        student_id=student.id,
        goal_id=goal.id,
        policy_version="phase1.1",
        consent_scopes=set(profile.consent_scopes),
        locale=profile.locale,
        timezone=profile.timezone,
        request_time=datetime.now(UTC),
        budget=AgentBudget(),
    )
    profile_data = StudentProfileRead.model_validate(profile).model_dump(mode="json")
    async def profile_node(_state: GoalWorkflowGraphState) -> GoalWorkflowGraphState:
        result = await supervisor.invoke(
            db,
            workflow,
            context,
            agent_name="StudentProfileAgent",
            input_data=StudentProfileInput(
                profile_id=str(profile.id),
                profile_version=profile.version,
                profile=profile_data,
            ),
            idempotency_key=f"{workflow.id}:profile:{profile.version}",
            audit_context=audit_context,
        )
        workflow.current_step = "clarification"
        return {
            "profile_result": result.model_dump(mode="json"),
            "messages": [{"agent": result.agent.agent_name, "summary": result.summary}],
        }

    async def clarification_node(
        state: GoalWorkflowGraphState,
    ) -> GoalWorkflowGraphState:
        result = await supervisor.invoke(
            db,
            workflow,
            context,
            agent_name="GoalClarificationAgent",
            input_data=GoalClarificationInput(
                goal_id=str(goal.id),
                goal_version=goal.version,
                title=goal.title,
                raw_statement=goal.raw_statement,
                description=goal.description,
                target_date=goal.target_date,
                priority=goal.priority,
                success_criteria=goal.success_criteria,
                profile_summary=profile_data,
            ),
            idempotency_key=f"{workflow.id}:clarify:{goal.version}",
            audit_context=audit_context,
        )
        workflow.current_step = "governance"
        return {
            "clarification_result": result.model_dump(mode="json"),
            "messages": [{"agent": result.agent.agent_name, "summary": result.summary}],
        }

    async def governance_node(state: GoalWorkflowGraphState) -> GoalWorkflowGraphState:
        clarification = AgentResult.model_validate(state["clarification_result"])
        result = await supervisor.invoke(
            db,
            workflow,
            context,
            agent_name="SupervisorGovernanceAgent",
            input_data=SupervisorGovernanceInput(
                requested_agent="GoalFeasibilityAgent",
                preceding_statuses=[
                    AgentResult.model_validate(state["profile_result"]).status,
                    clarification.status,
                ],
                requested_patch_count=len(clarification.proposed_patches),
                high_impact=False,
            ),
            idempotency_key=f"{workflow.id}:governance:{goal.version}",
            audit_context=audit_context,
        )
        return {
            "governance_result": result.model_dump(mode="json"),
            "messages": [{"agent": result.agent.agent_name, "summary": result.summary}],
        }

    builder = StateGraph(GoalWorkflowGraphState)
    builder.add_node("profile", cast(Any, profile_node))
    builder.add_node("clarification", cast(Any, clarification_node))
    builder.add_node("governance", cast(Any, governance_node))
    builder.add_edge(START, "profile")
    builder.add_edge("profile", "clarification")
    builder.add_edge("clarification", "governance")
    builder.add_edge("governance", END)
    graph = builder.compile()
    state = await graph.ainvoke({"messages": []})

    clarification = AgentResult.model_validate(state["clarification_result"])
    governance = AgentResult.model_validate(state["governance_result"])
    if clarification.status == AgentRunStatus.INPUT_REQUIRED:
        workflow.status = WorkflowStatus.INPUT_REQUIRED
        workflow.current_step = "student_input"
    elif governance.status == AgentRunStatus.STUDENT_APPROVAL_REQUIRED:
        workflow.status = WorkflowStatus.APPROVAL_REQUIRED
        workflow.current_step = "student_approval"
    else:
        workflow.status = WorkflowStatus.COMPLETED
        workflow.current_step = "phase_2_feasibility"
        workflow.completed_at = datetime.now(UTC)
    workflow.version += 1
    workflow.state_data = state
    audit.record(
        db,
        audit_context,
        action=(
            "workflow.completed"
            if workflow.status == WorkflowStatus.COMPLETED
            else "workflow.paused"
        ),
        resource_type="workflow",
        resource_id=workflow.id,
        student_id=student.id,
        after={
            "status": workflow.status.value,
            "current_step": workflow.current_step,
        },
    )
    db.commit()
    db.refresh(workflow)
    return workflow, clarification
