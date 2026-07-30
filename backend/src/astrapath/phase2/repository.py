import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from astrapath.db import utc_now
from astrapath.errors import AppError
from astrapath.models import Goal, StudentProfile
from astrapath.phase2.catalog import COMPETENCY_CATALOG, GOAL_TEMPLATE_CATALOG
from astrapath.phase2.contracts import (
    CompetencyCreate,
    CompetencyUpdate,
    DecisionCardData,
    GoalTemplateCreate,
    StudentCompetencyInput,
)
from astrapath.phase2.models import (
    Competency,
    DecisionCard,
    GoalGraphEdge,
    GoalGraphNode,
    GoalIntelligenceState,
    GoalTemplate,
    StudentCompetency,
)


def as_json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


class Phase2Repository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_goal(self, goal_id: uuid.UUID) -> Goal:
        goal = self.db.get(Goal, goal_id)
        if not goal:
            raise AppError(404, "goal_not_found", "Goal was not found")
        return goal

    def get_profile(self, student_id: uuid.UUID) -> StudentProfile | None:
        return self.db.scalar(
            select(StudentProfile).where(StudentProfile.user_id == student_id)
        )

    def get_state(self, goal_id: uuid.UUID) -> GoalIntelligenceState | None:
        return self.db.get(GoalIntelligenceState, goal_id)

    def save_state(
        self,
        goal_id: uuid.UUID,
        *,
        template_id: uuid.UUID | None = None,
        clarification: Any | None = None,
        feasibility: Any | None = None,
        skill_gap: Any | None = None,
        graph_summary: Any | None = None,
    ) -> GoalIntelligenceState:
        state = self.get_state(goal_id)
        if state is None:
            state = GoalIntelligenceState(goal_id=goal_id, template_id=template_id)
            self.db.add(state)
        else:
            state.version += 1
            if template_id is not None:
                state.template_id = template_id
        if clarification is not None:
            state.clarification = as_json(clarification)
        if feasibility is not None:
            state.feasibility = as_json(feasibility)
        if skill_gap is not None:
            state.skill_gap = as_json(skill_gap)
        if graph_summary is not None:
            state.graph_summary = as_json(graph_summary)
        self.db.flush()
        return state

    def seed_catalog(self) -> None:
        existing_competencies = set(
            self.db.scalars(select(Competency.slug)).all()
        )
        for item in COMPETENCY_CATALOG:
            if item["slug"] not in existing_competencies:
                self.db.add(Competency(**item))
        self.db.flush()

        existing_templates = set(self.db.scalars(select(GoalTemplate.slug)).all())
        for item in GOAL_TEMPLATE_CATALOG:
            if item["slug"] not in existing_templates:
                self.db.add(GoalTemplate(**item))
        self.db.flush()

    def get_template(
        self, raw_goal: str, explicit_slug: str | None = None
    ) -> GoalTemplate:
        if explicit_slug:
            template = self.db.scalar(
                select(GoalTemplate).where(
                    GoalTemplate.slug == explicit_slug,
                    GoalTemplate.active.is_(True),
                )
            )
            if not template:
                raise AppError(
                    422,
                    "goal_template_not_found",
                    f"Active goal template '{explicit_slug}' was not found",
                )
            return template

        templates = self.db.scalars(
            select(GoalTemplate).where(GoalTemplate.active.is_(True))
        ).all()
        normalized = raw_goal.casefold()
        scored = [
            (
                sum(
                    max(1, len(term.split()))
                    for term in template.matching_terms
                    if term.casefold() in normalized
                ),
                template,
            )
            for template in templates
        ]
        score, template = max(scored, key=lambda item: item[0], default=(0, None))
        if score == 0 or template is None:
            raise AppError(
                422,
                "goal_needs_clarification",
                "No goal template matches this goal yet",
                {
                    "suggestion": (
                        "Add a more specific subject or choose an admin-managed template"
                    ),
                    "available_templates": [item.slug for item in templates],
                },
            )
        return template

    def get_template_by_id(self, template_id: uuid.UUID | None) -> GoalTemplate:
        template = self.db.get(GoalTemplate, template_id) if template_id else None
        if not template or not template.active:
            raise AppError(
                409,
                "goal_template_unavailable",
                "The goal's selected template is no longer available",
            )
        return template

    def get_competencies_by_slugs(
        self, slugs: Iterable[str], *, active_only: bool = True
    ) -> dict[str, Competency]:
        unique_slugs = list(dict.fromkeys(slugs))
        if not unique_slugs:
            return {}
        query = select(Competency).where(Competency.slug.in_(unique_slugs))
        if active_only:
            query = query.where(Competency.active.is_(True))
        return {item.slug: item for item in self.db.scalars(query).all()}

    def get_student_competencies(
        self, student_id: uuid.UUID, competency_ids: Iterable[uuid.UUID] | None = None
    ) -> dict[uuid.UUID, StudentCompetency]:
        query = select(StudentCompetency).where(
            StudentCompetency.student_id == student_id
        )
        if competency_ids is not None:
            ids = list(competency_ids)
            if not ids:
                return {}
            query = query.where(StudentCompetency.competency_id.in_(ids))
        return {
            item.competency_id: item for item in self.db.scalars(query).all()
        }

    def upsert_student_competencies(
        self,
        student_id: uuid.UUID,
        evidence: list[StudentCompetencyInput],
    ) -> None:
        if not evidence:
            return
        competency_map = self.get_competencies_by_slugs(
            [item.competency_slug for item in evidence]
        )
        missing = sorted(
            {item.competency_slug for item in evidence} - set(competency_map)
        )
        if missing:
            raise AppError(
                422,
                "unknown_competencies",
                "Some competency evidence refers to unknown competencies",
                {"slugs": missing},
            )
        current = self.get_student_competencies(
            student_id, [item.id for item in competency_map.values()]
        )
        for item in evidence:
            competency = competency_map[item.competency_slug]
            record = current.get(competency.id)
            if record is None:
                record = StudentCompetency(
                    student_id=student_id,
                    competency_id=competency.id,
                )
                self.db.add(record)
            record.proficiency_level = item.proficiency_level
            record.confidence = item.confidence
            record.source = item.source
            record.evidence_refs = item.evidence_refs
            record.last_evaluated_at = utc_now()
        self.db.flush()

    def replace_decision_cards(
        self,
        goal_id: uuid.UUID,
        decision_type: str,
        cards: list[DecisionCardData],
    ) -> list[DecisionCard]:
        self.db.execute(
            delete(DecisionCard).where(
                DecisionCard.goal_id == goal_id,
                DecisionCard.decision_type == decision_type,
            )
        )
        records = [
            DecisionCard(
                goal_id=goal_id,
                decision_type=decision_type,
                decision=card.decision,
                reasons=card.reasons,
                evidence=card.evidence,
                alternatives=card.alternatives,
                approval_required=card.approval_required,
                status=card.status,
                agent_name=card.agent_name,
            )
            for card in cards
        ]
        self.db.add_all(records)
        self.db.flush()
        return records

    def list_decision_cards(
        self, goal_id: uuid.UUID, decision_type: str | None = None
    ) -> list[DecisionCard]:
        query = select(DecisionCard).where(DecisionCard.goal_id == goal_id)
        if decision_type:
            query = query.where(DecisionCard.decision_type == decision_type)
        return list(self.db.scalars(query.order_by(DecisionCard.created_at)).all())

    def replace_graph(
        self,
        goal_id: uuid.UUID,
        node_specs: list[dict[str, Any]],
        edge_specs: list[dict[str, str]],
    ) -> tuple[list[GoalGraphNode], list[GoalGraphEdge]]:
        old_node_ids = list(
            self.db.scalars(
                select(GoalGraphNode.id).where(GoalGraphNode.goal_id == goal_id)
            ).all()
        )
        self.db.execute(delete(GoalGraphEdge).where(GoalGraphEdge.goal_id == goal_id))
        if old_node_ids:
            self.db.execute(
                delete(GoalGraphNode).where(GoalGraphNode.id.in_(old_node_ids))
            )
        nodes = [
            GoalGraphNode(
                goal_id=goal_id,
                competency_id=spec.get("competency_id"),
                node_type=spec["node_type"],
                title=spec["title"],
                required_level=spec.get("required_level"),
                current_level=spec.get("current_level"),
                estimated_hours=spec["estimated_hours"],
                sequence_order=spec["sequence_order"],
                is_optional=spec["is_optional"],
                node_metadata=spec.get("metadata", {}),
            )
            for spec in node_specs
        ]
        self.db.add_all(nodes)
        self.db.flush()
        by_key = {
            spec["key"]: node for spec, node in zip(node_specs, nodes, strict=True)
        }
        edges = [
            GoalGraphEdge(
                goal_id=goal_id,
                source_node_id=by_key[spec["source"]].id,
                target_node_id=by_key[spec["target"]].id,
                relationship_type=spec["relationship_type"],
                reason=spec["reason"],
            )
            for spec in edge_specs
        ]
        self.db.add_all(edges)
        self.db.flush()
        return nodes, edges

    def get_graph(
        self, goal_id: uuid.UUID
    ) -> tuple[list[GoalGraphNode], list[GoalGraphEdge]]:
        nodes = list(
            self.db.scalars(
                select(GoalGraphNode)
                .where(GoalGraphNode.goal_id == goal_id)
                .order_by(GoalGraphNode.sequence_order, GoalGraphNode.title)
            ).all()
        )
        edges = list(
            self.db.scalars(
                select(GoalGraphEdge)
                .where(GoalGraphEdge.goal_id == goal_id)
                .order_by(GoalGraphEdge.created_at, GoalGraphEdge.id)
            ).all()
        )
        return nodes, edges

    def create_competency(self, payload: CompetencyCreate) -> Competency:
        if self.db.scalar(select(Competency).where(Competency.slug == payload.slug)):
            raise AppError(409, "competency_slug_exists", "Competency slug already exists")
        self._validate_prerequisite_slugs(payload.slug, payload.prerequisite_slugs)
        competency = Competency(**payload.model_dump())
        self.db.add(competency)
        self.db.flush()
        return competency

    def update_competency(
        self, competency_id: uuid.UUID, payload: CompetencyUpdate
    ) -> Competency:
        competency = self.db.get(Competency, competency_id)
        if not competency:
            raise AppError(404, "competency_not_found", "Competency was not found")
        changes = payload.model_dump(exclude_unset=True)
        prerequisites = changes.get("prerequisite_slugs")
        if prerequisites is not None:
            self._validate_prerequisite_slugs(competency.slug, prerequisites)
            self._validate_ontology_acyclic(competency.slug, prerequisites)
        for field, value in changes.items():
            setattr(competency, field, value)
        competency.version += 1
        self.db.flush()
        return competency

    def create_template(self, payload: GoalTemplateCreate) -> GoalTemplate:
        if self.db.scalar(select(GoalTemplate).where(GoalTemplate.slug == payload.slug)):
            raise AppError(409, "goal_template_slug_exists", "Goal template slug already exists")
        requirements = [item.model_dump() for item in payload.requirements]
        self._validate_template_requirements(requirements)
        template = GoalTemplate(
            **payload.model_dump(exclude={"requirements"}),
            requirements=requirements,
        )
        self.db.add(template)
        self.db.flush()
        return template

    def _validate_prerequisite_slugs(
        self, competency_slug: str, prerequisite_slugs: list[str]
    ) -> None:
        if competency_slug in prerequisite_slugs:
            raise AppError(
                422,
                "invalid_prerequisite",
                "A competency cannot be its own prerequisite",
            )
        found = self.get_competencies_by_slugs(prerequisite_slugs)
        missing = sorted(set(prerequisite_slugs) - set(found))
        if missing:
            raise AppError(
                422,
                "unknown_prerequisites",
                "Prerequisite competencies must exist and be active",
                {"slugs": missing},
            )

    def _validate_template_requirements(
        self, requirements: list[dict[str, Any]]
    ) -> None:
        slugs = [item["competency_slug"] for item in requirements]
        if len(slugs) != len(set(slugs)):
            raise AppError(
                422,
                "duplicate_template_competency",
                "A template cannot contain duplicate competency requirements",
            )
        competencies = self.get_competencies_by_slugs(slugs)
        missing = sorted(set(slugs) - set(competencies))
        if missing:
            raise AppError(
                422,
                "unknown_template_competencies",
                "Template competencies must exist and be active",
                {"slugs": missing},
            )
        requirement_slugs = set(slugs)
        for item in requirements:
            missing_prerequisites = set(item["prerequisite_slugs"]) - requirement_slugs
            if missing_prerequisites:
                raise AppError(
                    422,
                    "template_prerequisite_missing",
                    "Every prerequisite must also be a template requirement",
                    {
                        "competency": item["competency_slug"],
                        "missing": sorted(missing_prerequisites),
                    },
                )
        topological_order(requirements)

    def _validate_ontology_acyclic(
        self, changed_slug: str, prerequisite_slugs: list[str]
    ) -> None:
        competencies = list(self.db.scalars(select(Competency)).all())
        requirements = [
            {
                "competency_slug": competency.slug,
                "prerequisite_slugs": (
                    prerequisite_slugs
                    if competency.slug == changed_slug
                    else competency.prerequisite_slugs
                ),
            }
            for competency in competencies
        ]
        try:
            topological_order(requirements)
        except AppError as exc:
            raise AppError(
                422,
                "cyclic_competency_graph",
                "Competency prerequisites must remain acyclic",
            ) from exc


def topological_order(requirements: list[dict[str, Any]]) -> list[str]:
    slugs = [item["competency_slug"] for item in requirements]
    incoming = {slug: 0 for slug in slugs}
    children: dict[str, list[str]] = {slug: [] for slug in slugs}
    for item in requirements:
        for prerequisite in item["prerequisite_slugs"]:
            if prerequisite not in incoming:
                continue
            incoming[item["competency_slug"]] += 1
            children[prerequisite].append(item["competency_slug"])
    queue = sorted(slug for slug, count in incoming.items() if count == 0)
    order: list[str] = []
    while queue:
        current = queue.pop(0)
        order.append(current)
        for child in sorted(children[current]):
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
                queue.sort()
    if len(order) != len(slugs):
        raise AppError(
            422,
            "cyclic_template_graph",
            "Goal template prerequisites contain a cycle",
        )
    return order
