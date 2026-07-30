from datetime import date, timedelta
from typing import Any

from pydantic import Field

from astrapath.agents.contracts import (
    AgentContext,
    AgentIdentity,
    AgentResult,
    ContractModel,
)
from astrapath.enums import AgentRunStatus
from astrapath.phase3.contracts import MilestoneSpec, TaskSpec
from astrapath.phase3.effort import EffortEstimator


class MilestoneDecompositionInput(ContractModel):
    target_date: date
    starts_on: date
    graph_nodes: list[dict[str, Any]]
    core_path: list[str]
    optional_branches: list[str] = Field(default_factory=list)
    include_optional: bool = False
    buffer_ratio: float = Field(ge=0.05, le=0.5)


class MilestoneDecompositionAgent:
    name = "milestone-decomposition-agent"
    version = "3.0.0"
    identity = AgentIdentity(
        agent_id="agent-6",
        agent_name=name,
        version=version,
        deployment="phase3-rules",
    )
    allowed_tools = frozenset({"effort_estimator", "dependency_validator"})

    def __init__(self) -> None:
        self.estimator = EffortEstimator()

    async def execute(
        self,
        context: AgentContext,
        input_data: MilestoneDecompositionInput,
    ) -> AgentResult:
        selected = [
            node
            for node in input_data.graph_nodes
            if node["node_type"] == "competency"
            and float(node["estimated_hours"]) > 0
            and (
                node["metadata"]["slug"] in input_data.core_path
                or (
                    input_data.include_optional
                    and node["metadata"]["slug"] in input_data.optional_branches
                )
            )
        ]
        selected.sort(key=lambda node: node["sequence_order"])
        if not selected:
            return AgentResult(
                agent=self.identity,
                status=AgentRunStatus.BLOCKED,
                confidence=1.0,
                summary="No remaining competency effort is available for planning.",
                data={"milestones": [], "tasks": []},
                warnings=["The learning graph has no incomplete competency nodes."],
                next_actions=["Review the goal competency graph"],
                user_visible_explanation=(
                    "There is no remaining graph effort to turn into milestones."
                ),
            )

        total_minutes = sum(
            max(60, round(float(node["estimated_hours"]) * 60)) for node in selected
        )
        available_days = max(1, (input_data.target_date - input_data.starts_on).days)
        cumulative = 0
        milestones: list[MilestoneSpec] = []
        tasks: list[TaskSpec] = []
        previous_key: str | None = None
        task_sequence = 1

        for milestone_sequence, node in enumerate(selected, start=1):
            slug = node["metadata"]["slug"]
            key = f"milestone:{slug}"
            estimated = max(60, round(float(node["estimated_hours"]) * 60))
            cumulative += estimated
            target_offset = max(
                1, round(available_days * cumulative / max(total_minutes, 1))
            )
            milestone_target = min(
                input_data.target_date,
                input_data.starts_on + timedelta(days=target_offset),
            )
            buffer_minutes = round(estimated * input_data.buffer_ratio)
            milestone = MilestoneSpec(
                key=key,
                graph_node_id=node["id"],
                competency_id=node["competency_id"],
                title=f"Demonstrate {node['title']}",
                description=(
                    f"Reach proficiency level {node['required_level']} in {node['title']} "
                    "through learning, practice, application, and review."
                ),
                target_date=milestone_target,
                acceptance_criteria=[
                    (
                        f"Independently apply {node['title']} at proficiency "
                        f"level {node['required_level']}"
                    ),
                    "Complete the planned practice and application tasks",
                    "Submit the required review evidence",
                ],
                evidence_requirements=[
                    f"Practice artifact for {node['title']}",
                    f"Short reflection explaining the use of {node['title']}",
                ],
                dependency_keys=[previous_key] if previous_key else [],
                sequence_number=milestone_sequence,
                estimated_minutes=estimated,
                buffer_minutes=buffer_minutes,
            )
            milestones.append(milestone)
            for task_type, minutes in self.estimator.task_efforts(estimated):
                evidence_required = task_type in {"apply", "review"}
                tasks.append(
                    TaskSpec(
                        key=f"task:{slug}:{task_type}",
                        milestone_key=key,
                        competency_id=node["competency_id"],
                        title=self._task_title(task_type, node["title"]),
                        description=self._task_description(task_type, node["title"]),
                        task_type=task_type,
                        priority=1 if milestone_sequence == 1 else min(5, milestone_sequence),
                        estimated_minutes=minutes,
                        evidence_required=evidence_required,
                        evidence_description=(
                            f"Upload or link the {task_type} artifact for {node['title']}"
                            if evidence_required
                            else None
                        ),
                        sequence_number=task_sequence,
                        due_date=milestone_target,
                    )
                )
                task_sequence += 1
            previous_key = key

        return AgentResult(
            agent=self.identity,
            status=AgentRunStatus.COMPLETED,
            confidence=0.92,
            summary=(
                f"Created {len(milestones)} evidence-backed milestones "
                f"and {len(tasks)} tasks."
            ),
            data={
                "milestones": [item.model_dump(mode="json") for item in milestones],
                "tasks": [item.model_dump(mode="json") for item in tasks],
                "total_estimated_minutes": total_minutes,
            },
            assumptions=[
                "Graph effort estimates are used as planning ranges",
                "Each competency includes learning, practice, application, and review",
            ],
            evidence_refs=[
                f"goal_graph:{context.goal_id}",
                "phase3_effort_distribution:v1",
            ],
            next_actions=["Generate a constraint-aware schedule"],
            user_visible_explanation=(
                "The learning path was converted into observable milestones with "
                "practice and evidence tasks."
            ),
        )

    @staticmethod
    def _task_title(task_type: str, competency: str) -> str:
        verbs = {
            "learn": "Learn",
            "practice": "Practice",
            "apply": "Apply",
            "review": "Review",
        }
        return f"{verbs[task_type]} {competency}"

    @staticmethod
    def _task_description(task_type: str, competency: str) -> str:
        descriptions = {
            "learn": f"Study the essential concepts and examples for {competency}.",
            "practice": f"Complete guided and independent exercises for {competency}.",
            "apply": f"Use {competency} in a small authentic application.",
            "review": f"Review errors, recall key ideas, and record evidence for {competency}.",
        }
        return descriptions[task_type]
