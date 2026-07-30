import uuid

from astrapath.phase4.contracts import (
    FocusCoachOutput,
    FocusSessionComplete,
    FocusSessionStart,
    Phase4Model,
)


class FocusCoachInput(Phase4Model):
    session_id: uuid.UUID
    start: FocusSessionStart
    completion: FocusSessionComplete | None = None


class FocusSessionCoachAgent:
    name = "FocusSessionCoachAgent"
    version = "1.0.0"
    allowed_tools = frozenset(
        {"timer_service", "session_repository", "notification_service"}
    )
    model_route = "deterministic-coach-v1"
    prompt_version = "focus-coach-v1"
    output_type = FocusCoachOutput

    async def execute(self, input_data: FocusCoachInput) -> FocusCoachOutput:
        if input_data.completion is None:
            return FocusCoachOutput(
                confidence=1.0,
                session_id=input_data.session_id,
                opening_prompt=(
                    f"Work only on: {input_data.start.objective}. "
                    "Keep blockers in the session notes instead of switching tasks."
                ),
                recommended_break_minutes=_break_length(input_data.start.planned_minutes),
                blocker_detected=False,
                next_actions=["Start the timer"],
            )
        completion = input_data.completion
        blocker_detected = bool(completion.blocker_notes)
        if completion.accomplished:
            feedback = "Session complete. Record the result and take the planned break."
        elif blocker_detected:
            feedback = (
                "The blocker is recorded. Ask the tutor or run a risk scan before retrying."
            )
        else:
            feedback = "Reduce the next session scope to one observable outcome."
        return FocusCoachOutput(
            confidence=1.0,
            session_id=input_data.session_id,
            opening_prompt=f"Session objective: {input_data.start.objective}",
            completion_feedback=feedback,
            recommended_break_minutes=_break_length(completion.actual_minutes),
            blocker_detected=blocker_detected,
            evidence_refs=[str(input_data.session_id)],
            next_actions=(
                ["Ask the contextual tutor about the blocker"]
                if blocker_detected
                else ["Continue with the next planned action"]
            ),
        )


def _break_length(minutes: int) -> int:
    if minutes >= 90:
        return 15
    if minutes >= 45:
        return 10
    return 5

