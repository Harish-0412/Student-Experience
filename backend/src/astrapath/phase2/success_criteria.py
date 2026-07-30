from datetime import date

from astrapath.models import Goal
from astrapath.phase2.models import GoalTemplate


class SuccessCriteriaGenerator:
    def generate(
        self,
        goal: Goal,
        template: GoalTemplate,
        *,
        target_date: date,
        target_level: int,
    ) -> list[str]:
        criteria = (
            list(goal.success_criteria)
            if goal.success_criteria
            else list(template.success_criteria)
        )
        criteria.extend(
            [
                (
                    f"Reach proficiency level {target_level} in every required "
                    "competency"
                ),
                f"Complete final evidence review by {target_date.isoformat()}",
            ]
        )
        return list(dict.fromkeys(criteria))
