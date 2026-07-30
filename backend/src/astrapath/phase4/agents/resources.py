import re
import uuid

from astrapath.phase4.contracts import (
    Phase4Model,
    RankedResource,
    ResourceBundle,
    ResourceRead,
    ResourceRecommendationRequest,
)


class ResourceCurationInput(Phase4Model):
    goal_id: uuid.UUID
    request: ResourceRecommendationRequest
    candidates: list[ResourceRead]


class ResourceCurationAgent:
    name = "ResourceCurationAgent"
    version = "1.0.0"
    allowed_tools = frozenset(
        {
            "resource_catalog",
            "link_validator",
            "license_checker",
            "vector_retriever",
        }
    )
    model_route = "deterministic-ranking-v1"
    prompt_version = "resource-curation-v1"
    output_type = ResourceBundle

    async def execute(self, input_data: ResourceCurationInput) -> ResourceBundle:
        request = input_data.request
        query_tokens = _tokens(request.query or "")
        scored: list[tuple[float, ResourceRead, list[str]]] = []
        for resource in input_data.candidates:
            if resource.status.value != "approved":
                continue
            if request.max_cost is not None and resource.cost_amount > request.max_cost:
                continue
            score = resource.quality_score * 0.4
            reasons = [f"quality {resource.quality_score:.2f}"]
            difficulty_match = 1 - min(abs(resource.difficulty - request.difficulty), 4) / 4
            score += difficulty_match * 0.25
            if resource.language.lower() == request.language.lower():
                score += 0.15
                reasons.append("language match")
            if not request.preferred_types or resource.resource_type in request.preferred_types:
                score += 0.1
                reasons.append("preferred format")
            if query_tokens:
                searchable = _tokens(
                    f"{resource.title} {resource.content_excerpt} {resource.provider}"
                )
                overlap = len(query_tokens & searchable) / len(query_tokens)
                score += overlap * 0.1
                if overlap:
                    reasons.append("query match")
            scored.append((min(round(score, 4), 1.0), resource, reasons))
        scored.sort(key=lambda item: (-item[0], -item[1].quality_score, item[1].title))
        ranked = [
            RankedResource(
                resource=resource,
                rank=index,
                relevance_score=score,
                selection_reason=", ".join(reasons),
            )
            for index, (score, resource, reasons) in enumerate(
                scored[: request.limit], start=1
            )
        ]
        return ResourceBundle(
            confidence=0.95 if ranked else 0.2,
            goal_id=input_data.goal_id,
            competency_ref=request.competency_ref,
            resources=ranked,
            evidence_refs=[str(item.resource.id) for item in ranked],
            warnings=[] if ranked else ["No approved resource matched the constraints."],
            next_actions=(
                ["Start with the first resource and replace it if it is unsuitable."]
                if ranked
                else ["Ask an admin to curate a suitable resource."]
            ),
        )


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2}
