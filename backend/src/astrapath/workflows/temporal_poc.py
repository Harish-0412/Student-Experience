from datetime import timedelta
from typing import Any

from temporalio import activity, workflow

with workflow.unsafe.imports_passed_through():
    from astrapath.agents.kernel import calculate_profile_completeness


@activity.defn
async def evaluate_profile_activity(profile: dict[str, Any]) -> dict[str, Any]:
    completeness, missing, warnings = calculate_profile_completeness(profile)
    return {
        "completeness": completeness,
        "missing_fields": missing,
        "warnings": warnings,
    }


@activity.defn
async def prepare_goal_activity(goal: dict[str, Any]) -> dict[str, Any]:
    questions: list[str] = []
    if not goal.get("target_date"):
        questions.append("target_date")
    if not goal.get("success_criteria"):
        questions.append("success_criteria")
    return {
        "goal_id": goal["id"],
        "status": "input_required" if questions else "ready",
        "missing_inputs": questions,
    }


@workflow.defn
class PhaseOneGoalWorkflow:
    @workflow.run
    async def run(self, command: dict[str, Any]) -> dict[str, Any]:
        profile_result = await workflow.execute_activity(
            evaluate_profile_activity,
            command["profile"],
            start_to_close_timeout=timedelta(seconds=15),
        )
        goal_result = await workflow.execute_activity(
            prepare_goal_activity,
            command["goal"],
            start_to_close_timeout=timedelta(seconds=15),
        )
        return {
            "workflow": "phase_one_goal_clarification",
            "profile": profile_result,
            "goal": goal_result,
        }

