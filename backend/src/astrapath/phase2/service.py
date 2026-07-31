import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from astrapath.audit import AuditContext, AuditService
from astrapath.enums import Role
from astrapath.errors import AppError
from astrapath.models import Goal, User
from astrapath.phase2.agents.feasibility import (
    FeasibilityAgentInput,
    GoalFeasibilityAgent,
)
from astrapath.phase2.agents.learning_path import (
    LearningPathAgentInput,
    LearningPathArchitectAgent,
)
from astrapath.phase2.agents.skill_gap import (
    SkillGapAgentInput,
    SkillGapAnalysisAgent,
)
from astrapath.phase2.clarification import GoalClarificationEngine
from astrapath.phase2.contracts import (
    AgentContext,
    ClarifiedGoal,
    CompetencyCreate,
    CompetencyRead,
    CompetencyUpdate,
    DecisionCardData,
    FeasibilityRequest,
    FeasibilityResult,
    GoalClarificationRequest,
    GoalClarificationResult,
    GoalCompetenciesResult,
    GoalGraphResult,
    GoalTemplateCreate,
    GoalTemplateRead,
    GraphEdgeRead,
    GraphNodeRead,
    SkillGapRequest,
    SkillGapResult,
    SkillGapWorkflowResult,
)
from astrapath.phase2.models import (
    DecisionCard,
    GoalGraphEdge,
    GoalGraphNode,
    GoalIntelligenceState,
)
from astrapath.phase2.repository import Phase2Repository


class GoalIntelligenceService:
    def __init__(
        self,
        db: Session,
        *,
        audit: AuditService | None = None,
        audit_context: AuditContext | None = None,
    ) -> None:
        self.db = db
        self.audit = audit
        self.audit_context = audit_context
        self.repository = Phase2Repository(db)
        self.clarification_engine = GoalClarificationEngine()
        self.feasibility_agent = GoalFeasibilityAgent()
        self.skill_gap_agent = SkillGapAnalysisAgent()
        self.learning_path_agent = LearningPathArchitectAgent()

    async def clarify(
        self,
        goal_id: uuid.UUID,
        actor: User,
        payload: GoalClarificationRequest,
    ) -> GoalClarificationResult:
        goal = self.repository.get_goal(goal_id)
        self._require_goal_access(goal, actor)
        self.repository.seed_catalog()
        raw_goal = payload.raw_goal or goal.raw_statement
        template = self.repository.get_template(raw_goal, payload.template_slug)
        profile = self.repository.get_profile(goal.student_id)
        result = self.clarification_engine.clarify(
            goal, profile, template, payload
        )
        records = self.repository.replace_decision_cards(
            goal.id, "clarification", result.decision_cards
        )
        result.decision_cards = self._cards(records)
        self.repository.save_state(
            goal.id,
            template_id=template.id,
            clarification=result.clarified_goal,
        )
        self._commit(
            actor,
            action="phase2.goal_clarified",
            resource_type="goal_intelligence",
            resource_id=goal.id,
            student_id=goal.student_id,
            after={
                "template_slug": template.slug,
                "confidence": result.clarified_goal.confidence,
            },
        )
        return result

    async def feasibility(
        self,
        goal_id: uuid.UUID,
        actor: User,
        payload: FeasibilityRequest,
    ) -> FeasibilityResult:
        goal = self.repository.get_goal(goal_id)
        self._require_goal_access(goal, actor)
        state = self._require_state(goal_id, "clarification")
        clarified = ClarifiedGoal.model_validate(state.clarification)
        template = self.repository.get_template_by_id(state.template_id)
        requirements = list(template.requirements)
        known_slugs = {item["competency_slug"] for item in requirements}
        excluded = set(payload.excluded_competencies)
        unknown_exclusions = sorted(excluded - known_slugs)
        required_exclusions = sorted(
            item["competency_slug"]
            for item in requirements
            if item["required"] and item["competency_slug"] in excluded
        )
        if unknown_exclusions:
            raise AppError(
                422,
                "unknown_excluded_competencies",
                "Excluded competencies must belong to the selected goal template",
                {"slugs": unknown_exclusions},
            )
        if required_exclusions:
            raise AppError(
                422,
                "required_competencies_cannot_be_excluded",
                "Only optional competencies may be excluded from feasibility analysis",
                {"slugs": required_exclusions},
            )
        competencies = self.repository.get_competencies_by_slugs(
            [item["competency_slug"] for item in requirements]
        )
        student_records = self.repository.get_student_competencies(
            goal.student_id, [item.id for item in competencies.values()]
        )
        current_levels = {
            slug: student_records[competency.id].proficiency_level
            for slug, competency in competencies.items()
            if competency.id in student_records
        }
        agent_result = await self.feasibility_agent.execute(
            self._context(goal, actor, "feasibility"),
            FeasibilityAgentInput(
                clarified_goal=clarified,
                requirements=requirements,
                current_levels=current_levels,
                request=payload,
            ),
        )
        result = FeasibilityResult.model_validate(agent_result.data)
        records = self.repository.replace_decision_cards(
            goal.id, "feasibility", result.decision_cards
        )
        result.decision_cards = self._cards(records)
        self.repository.save_state(goal.id, feasibility=result)
        self._commit(
            actor,
            action="phase2.feasibility_assessed",
            resource_type="goal_intelligence",
            resource_id=goal.id,
            student_id=goal.student_id,
            after={
                "category": result.category.value,
                "confidence": result.confidence,
            },
        )
        return result

    async def skill_gap(
        self,
        goal_id: uuid.UUID,
        actor: User,
        payload: SkillGapRequest,
    ) -> SkillGapWorkflowResult:
        goal = self.repository.get_goal(goal_id)
        self._require_goal_access(goal, actor)
        state = self._require_state(goal_id, "feasibility")
        clarified = ClarifiedGoal.model_validate(state.clarification)
        template = self.repository.get_template_by_id(state.template_id)
        requirements = list(template.requirements)
        self.repository.upsert_student_competencies(
            goal.student_id, payload.competency_evidence
        )
        competency_map = self.repository.get_competencies_by_slugs(
            [item["competency_slug"] for item in requirements]
        )
        student_records = self.repository.get_student_competencies(
            goal.student_id, [item.id for item in competency_map.values()]
        )
        student_levels: dict[str, dict[str, Any]] = {}
        for slug, competency in competency_map.items():
            record = student_records.get(competency.id)
            if record:
                student_levels[slug] = {
                    "proficiency_level": record.proficiency_level,
                    "confidence": record.confidence,
                    "source": record.source,
                    "evidence_refs": record.evidence_refs,
                }
        competency_data = {
            slug: {"id": competency.id, "name": competency.name}
            for slug, competency in competency_map.items()
        }
        gap_agent_result = await self.skill_gap_agent.execute(
            self._context(goal, actor, "skill-gap"),
            SkillGapAgentInput(
                requirements=requirements,
                competencies=competency_data,
                student_levels=student_levels,
            ),
        )
        gap_result = SkillGapResult.model_validate(gap_agent_result.data)
        path_agent_result = await self.learning_path_agent.execute(
            self._context(goal, actor, "learning-path"),
            LearningPathAgentInput(
                clarified_goal=clarified,
                requirements=requirements,
                gaps=gap_result.required_competencies,
                competency_ids={
                    slug: competency.id for slug, competency in competency_map.items()
                },
            ),
        )
        nodes, edges = self.repository.replace_graph(
            goal.id,
            path_agent_result.data["node_specs"],
            path_agent_result.data["edge_specs"],
        )
        path_cards = [
            DecisionCardData.model_validate(item)
            for item in path_agent_result.data["decision_cards"]
        ]
        all_cards = gap_result.decision_cards + path_cards
        card_records = self.repository.replace_decision_cards(
            goal.id, "learning_path", all_cards
        )
        gap_result.decision_cards = self._cards(card_records)
        graph = self._graph_result(
            goal.id,
            nodes,
            edges,
            path_agent_result.data["core_path"],
            path_agent_result.data["optional_branches"],
            path_agent_result.data["estimated_duration_weeks"],
            self._cards(card_records),
        )
        self.repository.save_state(
            goal.id,
            skill_gap=gap_result,
            graph_summary={
                "core_path": graph.core_path,
                "optional_branches": graph.optional_branches,
                "estimated_duration_weeks": graph.estimated_duration_weeks,
            },
        )
        self._commit(
            actor,
            action="phase2.skill_gap_and_graph_created",
            resource_type="goal_intelligence",
            resource_id=goal.id,
            student_id=goal.student_id,
            after={
                "competency_count": len(gap_result.required_competencies),
                "graph_node_count": len(graph.nodes),
                "graph_edge_count": len(graph.edges),
            },
        )
        return SkillGapWorkflowResult(skill_gap=gap_result, graph=graph)

    def competencies(
        self, goal_id: uuid.UUID, actor: User
    ) -> GoalCompetenciesResult:
        goal = self.repository.get_goal(goal_id)
        self._require_goal_access(goal, actor)
        state = self._require_state(goal_id, "skill_gap")
        result = SkillGapResult.model_validate(state.skill_gap)
        template = self.repository.get_template_by_id(state.template_id)
        return GoalCompetenciesResult(
            goal_id=goal.id,
            template_slug=template.slug,
            competencies=result.required_competencies,
        )

    def graph(self, goal_id: uuid.UUID, actor: User) -> GoalGraphResult:
        goal = self.repository.get_goal(goal_id)
        self._require_goal_access(goal, actor)
        state = self._require_state(goal_id, "graph")
        nodes, edges = self.repository.get_graph(goal.id)
        cards = self._cards(
            self.repository.list_decision_cards(goal.id, "learning_path")
        )
        summary = state.graph_summary or {}
        return self._graph_result(
            goal.id,
            nodes,
            edges,
            summary.get("core_path", []),
            summary.get("optional_branches", []),
            summary.get("estimated_duration_weeks", 0),
            cards,
        )

    def create_competency(
        self, actor: User, payload: CompetencyCreate
    ) -> CompetencyRead:
        self._require_admin(actor)
        self.repository.seed_catalog()
        record = self.repository.create_competency(payload)
        self._commit(
            actor,
            action="phase2.competency_created",
            resource_type="competency",
            resource_id=record.id,
            after={"slug": record.slug, "version": record.version},
        )
        return CompetencyRead.model_validate(record)

    def update_competency(
        self,
        competency_id: uuid.UUID,
        actor: User,
        payload: CompetencyUpdate,
    ) -> CompetencyRead:
        self._require_admin(actor)
        record = self.repository.update_competency(competency_id, payload)
        self._commit(
            actor,
            action="phase2.competency_updated",
            resource_type="competency",
            resource_id=record.id,
            after={"slug": record.slug, "version": record.version},
        )
        return CompetencyRead.model_validate(record)

    def create_template(
        self, actor: User, payload: GoalTemplateCreate
    ) -> GoalTemplateRead:
        self._require_admin(actor)
        self.repository.seed_catalog()
        record = self.repository.create_template(payload)
        self._commit(
            actor,
            action="phase2.goal_template_created",
            resource_type="goal_template",
            resource_id=record.id,
            after={"slug": record.slug, "version": record.version},
        )
        return GoalTemplateRead.model_validate(record)

    def list_templates(self) -> list[GoalTemplateRead]:
        self.repository.seed_catalog()
        self.db.commit()
        return [
            GoalTemplateRead.model_validate(record)
            for record in self.repository.list_templates()
        ]

    @staticmethod
    def _require_admin(actor: User) -> None:
        if actor.role != Role.ADMIN:
            raise AppError(403, "forbidden", "This operation requires the admin role")

    @staticmethod
    def _require_goal_access(goal: Goal, actor: User) -> None:
        if actor.role == Role.ADMIN:
            return
        if actor.role != Role.STUDENT or actor.id != goal.student_id:
            raise AppError(403, "forbidden", "Students can access only their own goals")

    def _require_state(
        self, goal_id: uuid.UUID, required_step: str
    ) -> GoalIntelligenceState:
        state = self.repository.get_state(goal_id)
        missing = (
            state is None
            or (required_step == "clarification" and not state.clarification)
            or (required_step == "feasibility" and not state.feasibility)
            or (required_step == "skill_gap" and not state.skill_gap)
            or (required_step == "graph" and not state.graph_summary)
        )
        if missing:
            previous = {
                "clarification": "clarify",
                "feasibility": "feasibility",
                "skill_gap": "skill-gap",
                "graph": "skill-gap",
            }[required_step]
            raise AppError(
                409,
                "goal_intelligence_step_required",
                f"Complete the {previous} step before this operation",
            )
        assert state is not None
        return state

    @staticmethod
    def _context(
        goal: Goal, actor: User, step: str
    ) -> AgentContext:
        correlation_id = f"phase2:{goal.id}:{goal.version}"
        return AgentContext(
            workflow_id=uuid.uuid5(
                uuid.NAMESPACE_URL, f"astrapath:goal-intelligence:{goal.id}"
            ),
            correlation_id=correlation_id,
            causation_id=f"{correlation_id}:{step}",
            actor_id=actor.id,
            actor_role=actor.role,
            student_id=goal.student_id,
            goal_id=goal.id,
            plan_version=goal.version,
            policy_version="phase1.1",
            request_time=datetime.now(UTC),
            metadata={"phase": 2, "step": step},
        )

    def _commit(
        self,
        actor: User,
        *,
        action: str,
        resource_type: str,
        resource_id: str | uuid.UUID,
        student_id: uuid.UUID | None = None,
        after: dict[str, Any] | None = None,
    ) -> None:
        if self.audit and self.audit_context:
            self.audit.record(
                self.db,
                self.audit_context,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                student_id=student_id,
                after=after,
                metadata={"phase": 2, "actor_role": actor.role.value},
            )
        self.db.commit()

    @staticmethod
    def _cards(records: list[DecisionCard]) -> list[DecisionCardData]:
        return [
            DecisionCardData(
                id=record.id,
                decision_type=record.decision_type,
                decision=record.decision,
                reasons=record.reasons,
                evidence=record.evidence,
                alternatives=record.alternatives,
                approval_required=record.approval_required,
                status=record.status,
                agent_name=record.agent_name,
            )
            for record in records
        ]

    @staticmethod
    def _graph_result(
        goal_id: uuid.UUID,
        nodes: list[GoalGraphNode],
        edges: list[GoalGraphEdge],
        core_path: list[str],
        optional_branches: list[str],
        estimated_duration_weeks: float,
        cards: list[DecisionCardData],
    ) -> GoalGraphResult:
        return GoalGraphResult(
            goal_id=goal_id,
            nodes=[
                GraphNodeRead(
                    id=node.id,
                    competency_id=node.competency_id,
                    node_type=node.node_type,
                    title=node.title,
                    required_level=node.required_level,
                    current_level=node.current_level,
                    estimated_hours=node.estimated_hours,
                    sequence_order=node.sequence_order,
                    is_optional=node.is_optional,
                    metadata=node.node_metadata,
                )
                for node in nodes
            ],
            edges=[
                GraphEdgeRead(
                    id=edge.id,
                    source_node_id=edge.source_node_id,
                    target_node_id=edge.target_node_id,
                    relationship_type=edge.relationship_type,
                    reason=edge.reason,
                )
                for edge in edges
            ],
            core_path=core_path,
            optional_branches=optional_branches,
            estimated_duration_weeks=estimated_duration_weeks,
            decision_cards=cards,
        )
