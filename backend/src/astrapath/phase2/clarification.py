from datetime import date, timedelta

from astrapath.models import Goal, StudentProfile
from astrapath.phase2.contracts import (
    ClarifiedGoal,
    DecisionCardData,
    GoalClarificationRequest,
    GoalClarificationResult,
)
from astrapath.phase2.models import GoalTemplate
from astrapath.phase2.success_criteria import SuccessCriteriaGenerator


class GoalClarificationEngine:
    def __init__(self) -> None:
        self.success_criteria_generator = SuccessCriteriaGenerator()

    def clarify(
        self,
        goal: Goal,
        profile: StudentProfile | None,
        template: GoalTemplate,
        request: GoalClarificationRequest,
    ) -> GoalClarificationResult:
        assumptions: list[str] = []
        questions: list[str] = []

        target_date = request.target_date or goal.target_date
        if target_date is None:
            target_date = date.today() + timedelta(weeks=template.default_duration_weeks)
            assumptions.append(
                f"A {template.default_duration_weeks}-week target window was assumed"
            )
            questions.append(f"Is the target date {target_date.isoformat()} acceptable?")

        profile_hours = (
            profile.weekly_learning_minutes / 60
            if profile and profile.weekly_learning_minutes > 0
            else None
        )
        weekly_hours = request.weekly_hours or profile_hours
        if weekly_hours is None:
            weekly_hours = 5.0
            assumptions.append("Five learning hours per week were assumed")
            questions.append("Can you reserve five learning hours each week?")

        measurable_outcome = request.desired_outcome or template.measurable_outcome
        if request.desired_outcome is None:
            assumptions.append("The selected template supplied the measurable outcome")

        target_level = request.target_level or template.default_target_level
        success_criteria = self.success_criteria_generator.generate(
            goal,
            template,
            target_date=target_date,
            target_level=target_level,
        )
        confidence = min(
            0.95,
            0.72
            + (0.07 if request.target_date or goal.target_date else 0)
            + (0.07 if request.weekly_hours or profile_hours else 0)
            + (0.05 if request.desired_outcome else 0),
        )
        clarified = ClarifiedGoal(
            goal_id=goal.id,
            measurable_outcome=measurable_outcome,
            category=template.category,
            target_level=target_level,
            target_date=target_date,
            weekly_hours=round(weekly_hours, 2),
            constraints=request.constraints,
            success_criteria=success_criteria,
            template_slug=template.slug,
            assumptions=assumptions,
            clarification_questions=questions,
            confidence=confidence,
        )
        card = DecisionCardData(
            decision_type="clarification",
            decision=f"Structure this goal with the {template.name} template",
            reasons=[
                "The goal language matches this template's outcome and competency map",
                "The template provides measurable success criteria and a prerequisite baseline",
            ],
            evidence=[f"goal:{goal.id}", f"goal_template:{template.slug}"],
            alternatives=[
                "Choose another active goal template",
                "Ask an administrator to create a specialized template",
            ],
            approval_required=bool(assumptions),
            agent_name="goal-clarification-engine",
        )
        return GoalClarificationResult(clarified_goal=clarified, decision_cards=[card])
