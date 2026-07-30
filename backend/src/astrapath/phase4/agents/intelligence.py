import hashlib
import json
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import Field

from astrapath.phase4.contracts import (
    AgentOutput,
    CoachingRequest,
    ExecutionContextSync,
    Phase4Model,
)
from astrapath.phase4.enums import (
    AgentExecutionStatus,
    RiskSeverity,
)


class ProgressComputationInput(Phase4Model):
    goal_id: uuid.UUID
    execution: ExecutionContextSync | None = None
    focus_minutes: int = Field(ge=0)
    completed_focus_sessions: int = Field(ge=0)
    verified_evidence_count: int = Field(ge=0)
    evidence_quality_scores: list[float] = Field(default_factory=list)
    assessment_percentages: list[float] = Field(default_factory=list)
    mastery_scores: list[float] = Field(default_factory=list)


class ProgressComputation(AgentOutput):
    activity_progress: float = Field(ge=0, le=100)
    milestone_progress: float = Field(ge=0, le=100)
    mastery_progress: float = Field(ge=0, le=100)
    goal_confidence: float = Field(ge=0, le=100)
    schedule_variance: float
    calculation: dict[str, Any]


class ProgressTrackingAgent:
    name = "ProgressTrackingAgent"
    version = "1.0.0"
    allowed_tools = frozenset(
        {"event_store", "progress_repository", "analytics_engine"}
    )
    model_route = "deterministic-progress-v1"
    prompt_version = "progress-tracking-v1"
    output_type = ProgressComputation

    async def execute(
        self, input_data: ProgressComputationInput
    ) -> ProgressComputation:
        execution = input_data.execution
        if execution and execution.planned_task_count:
            task_ratio = (
                execution.completed_task_count / execution.planned_task_count
            )
            activity = task_ratio * 80 + min(input_data.completed_focus_sessions * 2, 20)
        else:
            activity = min(input_data.focus_minutes / 300 * 100, 100)
        if execution and execution.planned_milestone_count:
            milestone = (
                execution.completed_milestone_count
                / execution.planned_milestone_count
                * 100
            )
        else:
            milestone = min(input_data.verified_evidence_count * 20, 100)

        mastery_signals = [score * 100 for score in input_data.mastery_scores]
        if not mastery_signals:
            mastery_signals.extend(input_data.assessment_percentages)
            mastery_signals.extend(
                score * 100 for score in input_data.evidence_quality_scores
            )
        mastery = (
            sum(mastery_signals) / len(mastery_signals) if mastery_signals else 0
        )
        adherence = execution.schedule_adherence if execution else 1.0
        schedule_variance = round((adherence - 1) * 100, 2)
        confidence = (
            min(activity, 100) * 0.25
            + min(milestone, 100) * 0.25
            + min(mastery, 100) * 0.35
            + adherence * 100 * 0.15
        )
        calculation = {
            "activity_basis": (
                "phase3_task_baseline"
                if execution and execution.planned_task_count
                else "focus_minutes"
            ),
            "milestone_basis": (
                "phase3_milestone_baseline"
                if execution and execution.planned_milestone_count
                else "verified_evidence"
            ),
            "mastery_signal_count": len(mastery_signals),
            "weights": {
                "activity": 0.25,
                "milestone": 0.25,
                "mastery": 0.35,
                "schedule_adherence": 0.15,
            },
        }
        return ProgressComputation(
            confidence=1.0,
            activity_progress=round(min(activity, 100), 2),
            milestone_progress=round(min(milestone, 100), 2),
            mastery_progress=round(min(mastery, 100), 2),
            goal_confidence=round(min(confidence, 100), 2),
            schedule_variance=schedule_variance,
            calculation=calculation,
            evidence_refs=[],
            next_actions=["Run risk detection after meaningful progress changes."],
        )


class MasteryComputationInput(Phase4Model):
    goal_id: uuid.UUID
    competency_ref: str
    assessment_percentages: list[float] = Field(default_factory=list)
    evidence_quality_scores: list[float] = Field(default_factory=list)
    tutor_misconceptions: list[str] = Field(default_factory=list)


class MasteryComputation(AgentOutput):
    score: float = Field(ge=0, le=1)
    confidence_lower: float = Field(ge=0, le=1)
    confidence_upper: float = Field(ge=0, le=1)
    evidence_count: int
    weak_subskills: list[str]
    next_assessment_recommendation: str
    calculation: dict[str, Any]


class MasteryEstimationAgent:
    name = "MasteryEstimationAgent"
    version = "1.0.0"
    allowed_tools = frozenset(
        {
            "mastery_model",
            "bayesian_tracker",
            "evidence_repository",
            "competency_graph",
        }
    )
    model_route = "calibrated-weighted-model-v1"
    prompt_version = "mastery-estimation-v1"
    output_type = MasteryComputation

    async def execute(
        self, input_data: MasteryComputationInput
    ) -> MasteryComputation:
        assessments = [value / 100 for value in input_data.assessment_percentages]
        evidence = input_data.evidence_quality_scores
        observed_count = len(assessments) + len(evidence)
        assessment_mean = sum(assessments) / len(assessments) if assessments else 0.35
        evidence_mean = sum(evidence) / len(evidence) if evidence else 0.35
        misconception_penalty = min(len(input_data.tutor_misconceptions) * 0.04, 0.2)
        observed_score = assessment_mean * 0.65 + evidence_mean * 0.35
        reliability = observed_count / (observed_count + 3)
        score = 0.35 * (1 - reliability) + observed_score * reliability
        score = max(0, min(score - misconception_penalty, 1))
        uncertainty = max(0.08, 0.3 * (1 - reliability))
        lower = max(0, score - uncertainty)
        upper = min(1, score + uncertainty)
        recommendation = (
            "Use a transfer assessment in a new context."
            if score >= 0.8 and observed_count >= 3
            else "Complete another targeted assessment after remediation."
        )
        return MasteryComputation(
            confidence=round(reliability, 4),
            score=round(score, 4),
            confidence_lower=round(lower, 4),
            confidence_upper=round(upper, 4),
            evidence_count=observed_count,
            weak_subskills=input_data.tutor_misconceptions,
            next_assessment_recommendation=recommendation,
            calculation={
                "prior": 0.35,
                "assessment_weight": 0.65,
                "evidence_weight": 0.35,
                "reliability": round(reliability, 4),
                "misconception_penalty": misconception_penalty,
            },
            assumptions=["Signals are independent enough for a weighted estimate."],
            next_actions=[recommendation],
        )


class CoachingAgentInput(Phase4Model):
    coaching_id: uuid.UUID
    request: CoachingRequest
    recent_goal_confidence: float = Field(ge=0, le=100)
    recent_focus_minutes: int = Field(ge=0)


class CoachingDraft(AgentOutput):
    coaching_id: uuid.UUID
    message: str
    reflection_prompt: str
    habit_experiment: str
    notification_adjustment: str | None


class MotivationHabitCoachAgent:
    name = "MotivationHabitCoachAgent"
    version = "1.0.0"
    allowed_tools = frozenset(
        {"reflection_repository", "notification_service", "safety_policy"}
    )
    model_route = "bounded-coaching-v1"
    prompt_version = "motivation-coach-v1"
    output_type = CoachingDraft

    async def execute(self, input_data: CoachingAgentInput) -> CoachingDraft:
        motivation = input_data.request.motivation_level
        if motivation <= 2:
            message = (
                "Reduce today's scope. Completing one small, visible action is enough "
                "to restart momentum."
            )
            experiment = "Schedule one 15-minute session tied to a specific outcome."
        elif input_data.recent_goal_confidence < 50:
            message = (
                "Your effort is present, but the evidence is not yet translating into "
                "confidence. Choose one weak concept and verify it directly."
            )
            experiment = "Replace one broad study block with a focused practice check."
        else:
            message = "Your current rhythm is working. Protect consistency before adding load."
            experiment = "Repeat the most successful session pattern twice this week."
        adjustment = (
            "Use one reminder shortly before the smallest planned session."
            if input_data.request.notification_enabled
            else None
        )
        return CoachingDraft(
            confidence=0.9,
            coaching_id=input_data.coaching_id,
            message=message,
            reflection_prompt="What made the last useful session easier to begin?",
            habit_experiment=experiment,
            notification_adjustment=adjustment,
            next_actions=[experiment],
        )


class RiskDetectionInput(Phase4Model):
    goal_id: uuid.UUID
    target_date: date | None
    progress: dict[str, float]
    execution: ExecutionContextSync | None = None
    focus_minutes_last_7_days: int = Field(ge=0)
    open_blockers: list[str] = Field(default_factory=list)
    tutor_misconceptions: list[str] = Field(default_factory=list)
    resource_issue: str | None = None
    now: datetime


class RiskFinding(Phase4Model):
    risk_type: str
    severity: RiskSeverity
    score: float = Field(ge=0, le=1)
    evidence_refs: list[str]
    likely_causes: list[str]
    intervention: str
    requires_admin_review: bool = False
    fingerprint: str


class RiskDetectionOutput(AgentOutput):
    findings: list[RiskFinding]


class RiskBlockerDetectionAgent:
    name = "RiskBlockerDetectionAgent"
    version = "1.0.0"
    allowed_tools = frozenset(
        {"risk_rules_engine", "anomaly_detector", "event_store", "deadline_calculator"}
    )
    model_route = "deterministic-risk-v1"
    prompt_version = "risk-detection-v1"
    output_type = RiskDetectionOutput

    async def execute(self, input_data: RiskDetectionInput) -> RiskDetectionOutput:
        findings: list[RiskFinding] = []
        goal_confidence = input_data.progress.get("goal_confidence", 0)
        mastery = input_data.progress.get("mastery_progress", 0)
        activity = input_data.progress.get("activity_progress", 0)
        if input_data.target_date:
            days_left = (input_data.target_date - input_data.now.date()).days
            if days_left <= 14 and goal_confidence < 60:
                score = 0.9 if days_left <= 7 else 0.75
                findings.append(
                    _finding(
                        "deadline",
                        score,
                        [f"days_left:{days_left}", f"goal_confidence:{goal_confidence}"],
                        ["Deadline is close relative to verified progress."],
                        "Create a minimal replan that protects essential outcomes.",
                    )
                )
        execution = input_data.execution
        if (
            execution
            and execution.weekly_capacity_minutes
            and execution.planned_weekly_minutes
            > execution.weekly_capacity_minutes * 1.15
        ):
            overload = (
                execution.planned_weekly_minutes
                / execution.weekly_capacity_minutes
                - 1
            )
            findings.append(
                _finding(
                    "overload",
                    min(0.55 + overload, 0.95),
                    [
                        f"planned_weekly_minutes:{execution.planned_weekly_minutes}",
                        f"capacity_minutes:{execution.weekly_capacity_minutes}",
                    ],
                    ["Planned workload exceeds declared capacity."],
                    "Reduce or defer nonessential plan items.",
                )
            )
        if activity - mastery >= 30:
            findings.append(
                _finding(
                    "stagnation",
                    min(0.6 + (activity - mastery) / 200, 0.9),
                    [f"activity:{activity}", f"mastery:{mastery}"],
                    ["Activity is not producing comparable mastery evidence."],
                    "Switch from passive activity to targeted assessment and remediation.",
                )
            )
        if input_data.focus_minutes_last_7_days == 0:
            findings.append(
                _finding(
                    "low_engagement",
                    0.65,
                    ["focus_minutes_last_7_days:0"],
                    ["No completed focus session was recorded in seven days."],
                    "Use one small recovery session and a coaching check-in.",
                )
            )
        if input_data.open_blockers:
            findings.append(
                _finding(
                    "blocker",
                    min(0.55 + len(input_data.open_blockers) * 0.08, 0.9),
                    input_data.open_blockers,
                    ["Open blockers remain unresolved."],
                    "Route concept blockers to tutoring and technical blockers to admin review.",
                    requires_admin_review=any(
                        "technical" in blocker.lower()
                        for blocker in input_data.open_blockers
                    ),
                )
            )
        if input_data.tutor_misconceptions:
            findings.append(
                _finding(
                    "missing_prerequisite",
                    min(0.5 + len(input_data.tutor_misconceptions) * 0.05, 0.85),
                    input_data.tutor_misconceptions,
                    ["Repeated tutor misconceptions indicate a prerequisite gap."],
                    "Add a short prerequisite remediation block before advancing.",
                )
            )
        if input_data.resource_issue:
            findings.append(
                _finding(
                    "resource_mismatch",
                    0.6,
                    [input_data.resource_issue],
                    ["The selected resource does not fit the learner or task."],
                    "Request a replacement resource bundle.",
                )
            )
        return RiskDetectionOutput(
            confidence=0.92,
            findings=findings,
            evidence_refs=[
                ref for finding in findings for ref in finding.evidence_refs
            ],
            next_actions=[
                "Review high-severity risks and request a replan when needed."
            ],
        )


class ReplanAgentInput(Phase4Model):
    goal_id: uuid.UUID
    risk: RiskFinding
    base_plan_ref: str
    base_plan_version: int
    preserve_completed_work: bool
    student_constraints: dict[str, Any]
    execution: ExecutionContextSync | None = None


class ReplanDraft(AgentOutput):
    proposed_patch: list[dict[str, Any]]
    impact_analysis: dict[str, Any]
    alternatives: list[dict[str, Any]]
    preserves_completed_work: bool
    student_approval_required: bool
    admin_review_required: bool


class AdaptiveReplanningAgent:
    name = "AdaptiveReplanningAgent"
    version = "1.0.0"
    allowed_tools = frozenset(
        {
            "plan_version_repository",
            "constraint_solver",
            "path_optimizer",
            "schedule_tool",
        }
    )
    model_route = "minimal-plan-diff-v1"
    prompt_version = "adaptive-replanning-v1"
    output_type = ReplanDraft

    async def execute(self, input_data: ReplanAgentInput) -> ReplanDraft:
        risk_type = input_data.risk.risk_type
        operations: list[dict[str, Any]] = []
        alternatives: list[dict[str, Any]] = []
        if risk_type == "overload":
            operations.append(
                {
                    "op": "reduce_weekly_load",
                    "target": input_data.base_plan_ref,
                    "percentage": 20,
                    "preserve_completed": True,
                }
            )
            alternatives.append({"option": "extend_deadline", "days": 14})
        elif risk_type == "deadline":
            operations.append(
                {
                    "op": "prioritize_essential_outcomes",
                    "target": input_data.base_plan_ref,
                    "defer_optional": True,
                    "preserve_completed": True,
                }
            )
            alternatives.append({"option": "extend_deadline", "days": 7})
        elif risk_type in {"missing_prerequisite", "stagnation"}:
            operations.append(
                {
                    "op": "insert_remediation_block",
                    "before_next_incomplete_task": True,
                    "duration_minutes": 90,
                    "preserve_completed": True,
                }
            )
            alternatives.append({"option": "targeted_assessment_first"})
        elif risk_type == "resource_mismatch":
            operations.append(
                {
                    "op": "replace_resource",
                    "retain_task_and_deadline": True,
                    "preserve_completed": True,
                }
            )
        else:
            operations.append(
                {
                    "op": "split_next_task",
                    "maximum_minutes": 30,
                    "preserve_completed": True,
                }
            )
        admin_review = input_data.risk.requires_admin_review
        return ReplanDraft(
            status=(
                AgentExecutionStatus.ADMIN_REVIEW_REQUIRED
                if admin_review
                else AgentExecutionStatus.STUDENT_APPROVAL_REQUIRED
            ),
            confidence=0.9,
            proposed_patch=operations,
            impact_analysis={
                "risk_type": risk_type,
                "base_plan_version": input_data.base_plan_version,
                "completed_work_changed": False,
                "phase3_apply_required": True,
            },
            alternatives=alternatives,
            preserves_completed_work=input_data.preserve_completed_work,
            student_approval_required=True,
            admin_review_required=admin_review,
            evidence_refs=input_data.risk.evidence_refs,
            warnings=["Proposal is not applied until Phase 3 validates the plan diff."],
            next_actions=["Student approves or rejects the proposal."],
        )


def _finding(
    risk_type: str,
    score: float,
    evidence_refs: list[str],
    causes: list[str],
    intervention: str,
    *,
    requires_admin_review: bool = False,
) -> RiskFinding:
    severity = (
        RiskSeverity.CRITICAL
        if score >= 0.9
        else RiskSeverity.HIGH
        if score >= 0.7
        else RiskSeverity.MEDIUM
        if score >= 0.45
        else RiskSeverity.LOW
    )
    fingerprint_payload = json.dumps(
        {"risk_type": risk_type, "evidence": sorted(evidence_refs)},
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(fingerprint_payload.encode()).hexdigest()
    return RiskFinding(
        risk_type=risk_type,
        severity=severity,
        score=round(score, 4),
        evidence_refs=evidence_refs,
        likely_causes=causes,
        intervention=intervention,
        requires_admin_review=requires_admin_review or severity == RiskSeverity.CRITICAL,
        fingerprint=fingerprint,
    )

