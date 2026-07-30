import re

from pydantic import Field

from astrapath.phase4.contracts import (
    AgentOutput,
    AssessmentCreate,
    AssessmentGenerateRequest,
    AssessmentQuestionInput,
    Phase4Model,
)


class GeneratedAssessment(AgentOutput):
    definition: AssessmentCreate


class AssessmentScoreInput(Phase4Model):
    questions: list[AssessmentQuestionInput]
    answers: dict[str, str | bool]


class AssessmentScoreOutput(AgentOutput):
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    percentage: float = Field(ge=0, le=100)
    feedback: list[dict[str, object]]
    review_required: bool


class AssessmentGenerationAgent:
    name = "AssessmentGenerationAgent"
    version = "1.0.0"
    allowed_tools = frozenset(
        {"assessment_bank", "rubric_engine", "policy_engine"}
    )
    model_route = "deterministic-assessment-v1"
    prompt_version = "assessment-generation-v1"
    output_type = GeneratedAssessment

    async def execute(
        self, input_data: AssessmentGenerateRequest
    ) -> GeneratedAssessment:
        questions: list[AssessmentQuestionInput] = []
        facts = input_data.source_facts
        for index in range(input_data.question_count):
            fact = facts[index % len(facts)].strip()
            keywords = _keywords(fact)
            outcome = input_data.learning_outcomes[index % len(input_data.learning_outcomes)]
            questions.append(
                AssessmentQuestionInput(
                    id=f"q{index + 1}",
                    prompt=f"Explain how this fact supports '{outcome}': {fact}",
                    kind="short_answer",
                    expected_keywords=keywords[:5] or ["concept"],
                    points=1,
                    explanation=f"A strong answer connects the fact to {outcome}.",
                )
            )
        definition = AssessmentCreate(
            goal_id=input_data.goal_id,
            competency_ref=input_data.competency_ref,
            title=input_data.title,
            assessment_type="quiz",
            instructions=(
                "Answer in your own words. Each response must connect the supplied "
                "fact to the named learning outcome."
            ),
            questions=questions,
            rubric=[
                {
                    "criterion": "conceptual_accuracy",
                    "weight": 0.7,
                },
                {
                    "criterion": "application_reasoning",
                    "weight": 0.3,
                },
            ],
            passing_percentage=input_data.passing_percentage,
            time_limit_minutes=max(10, input_data.question_count * 3),
        )
        return GeneratedAssessment(
            confidence=0.85,
            definition=definition,
            assumptions=[
                "Source facts were approved before assessment generation.",
            ],
            evidence_refs=[],
            next_actions=["Admin reviews and publishes the generated assessment."],
        )

    async def score(self, input_data: AssessmentScoreInput) -> AssessmentScoreOutput:
        score = 0.0
        max_score = sum(question.points for question in input_data.questions)
        feedback: list[dict[str, object]] = []
        review_required = False
        for question in input_data.questions:
            answer = input_data.answers.get(question.id)
            awarded = 0.0
            correct = False
            if answer is not None and question.kind in {"multiple_choice", "boolean"}:
                correct = str(answer).strip().lower() == str(
                    question.correct_answer
                ).strip().lower()
                awarded = question.points if correct else 0
            elif answer is not None:
                answer_tokens = set(_keywords(str(answer)))
                expected = set(keyword.lower() for keyword in question.expected_keywords)
                coverage = len(answer_tokens & expected) / len(expected) if expected else 0
                awarded = round(question.points * coverage, 4)
                correct = coverage >= 0.7
                review_required = review_required or 0.3 < coverage < 0.7
            score += awarded
            feedback.append(
                {
                    "question_id": question.id,
                    "awarded": awarded,
                    "maximum": question.points,
                    "correct": correct,
                    "explanation": question.explanation,
                }
            )
        percentage = round((score / max_score) * 100, 2)
        return AssessmentScoreOutput(
            confidence=1.0 if not review_required else 0.72,
            score=round(score, 4),
            max_score=round(max_score, 4),
            percentage=percentage,
            feedback=feedback,
            review_required=review_required,
            warnings=(
                ["A borderline short-answer result requires admin review."]
                if review_required
                else []
            ),
        )


def _keywords(value: str) -> list[str]:
    stopwords = {"this", "that", "with", "from", "into", "have", "will", "your"}
    return [
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 3 and token not in stopwords
    ]

