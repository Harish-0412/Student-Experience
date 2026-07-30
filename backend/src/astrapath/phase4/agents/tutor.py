import uuid

from astrapath.phase4.contracts import (
    Phase4Model,
    ResourceRead,
    TutorCitation,
    TutorMessageRequest,
    TutorResponse,
)
from astrapath.phase4.enums import (
    AcademicIntegrityMode,
    AgentExecutionStatus,
    TutorMode,
)


class TutorAgentInput(Phase4Model):
    thread_id: uuid.UUID
    request: TutorMessageRequest
    sources: list[ResourceRead]
    recent_messages: list[dict[str, str]]


class ContextualTutorAgent:
    name = "ContextualTutorAgent"
    version = "1.0.0"
    allowed_tools = frozenset(
        {"vector_retriever", "resource_catalog", "policy_engine"}
    )
    model_route = "grounded-template-v1"
    prompt_version = "contextual-tutor-v1"
    output_type = TutorResponse

    async def execute(self, input_data: TutorAgentInput) -> TutorResponse:
        request = input_data.request
        citations = [
            TutorCitation(
                resource_id=source.id,
                title=source.title,
                url=str(source.url),
                excerpt=source.content_excerpt[:300],
            )
            for source in input_data.sources[:3]
        ]
        if request.integrity_mode == AcademicIntegrityMode.GRADED:
            response = (
                "I cannot provide a submission-ready answer for graded work. "
                f"Start by identifying the rule or concept in '{request.message}'. "
                "Explain your first step, and I will check the reasoning."
            )
            follow_ups = [
                "What have you tried so far?",
                "Which step is uncertain?",
            ]
            boundary = True
        elif not citations:
            response = (
                "I do not have an approved source for this competency yet. "
                "I can help frame the question, but the factual explanation needs "
                "a curated resource first."
            )
            follow_ups = ["What exact concept or error message are you working with?"]
            boundary = False
        else:
            source_summary = " ".join(item.excerpt for item in citations)
            response = _mode_response(request.mode, request.message, source_summary)
            follow_ups = _follow_ups(request.mode)
            boundary = False
        return TutorResponse(
            status=(
                AgentExecutionStatus.COMPLETED
                if citations or boundary
                else AgentExecutionStatus.INPUT_REQUIRED
            ),
            confidence=0.9 if citations else 0.45,
            thread_id=input_data.thread_id,
            response=response,
            mode=request.mode,
            citations=citations,
            follow_up_questions=follow_ups,
            integrity_boundary_applied=boundary,
            evidence_refs=[str(item.resource_id) for item in citations],
            warnings=[] if citations else ["No approved retrieval source was available."],
            next_actions=["Answer a follow-up question or attempt the next step."],
        )


def _mode_response(mode: TutorMode, question: str, source_summary: str) -> str:
    context = source_summary[:900].strip()
    if mode == TutorMode.HINT:
        return (
            f"Hint for '{question}': identify the smallest relevant concept, then apply "
            f"this source-grounded clue: {context}"
        )
    if mode == TutorMode.QUIZ:
        return (
            f"Quick check based on the approved material: after reading '{context}', "
            f"how would you apply it to '{question}'?"
        )
    if mode == TutorMode.DEBUG:
        return (
            f"Debug this in three passes: reproduce the issue, compare the failing step "
            f"with this approved guidance, then test one change. Guidance: {context}"
        )
    return (
        f"For '{question}', the approved material supports this explanation: {context} "
        "Restate it in your own words before applying it."
    )


def _follow_ups(mode: TutorMode) -> list[str]:
    if mode == TutorMode.DEBUG:
        return ["What is the smallest reproducible failure?", "What changed most recently?"]
    if mode == TutorMode.QUIZ:
        return ["What answer would you choose, and why?"]
    return ["Can you explain the idea back in one sentence?", "Where would you apply it?"]
