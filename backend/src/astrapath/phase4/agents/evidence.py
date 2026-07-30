import re
import uuid

from astrapath.phase4.contracts import (
    CriteriaResult,
    EvidenceSubmissionCreate,
    EvidenceVerificationReport,
    Phase4Model,
)
from astrapath.phase4.enums import AgentExecutionStatus, EvidenceStatus


class EvidenceVerificationInput(Phase4Model):
    evidence_id: uuid.UUID
    submission: EvidenceSubmissionCreate
    storage_verified: bool
    scanner_clean: bool


class EvidenceVerificationAgent:
    name = "EvidenceVerificationAgent"
    version = "1.0.0"
    allowed_tools = frozenset(
        {
            "object_storage",
            "malware_scanner",
            "document_parser",
            "sandbox",
            "similarity_service",
        }
    )
    model_route = "deterministic-evidence-v1"
    prompt_version = "evidence-verification-v1"
    output_type = EvidenceVerificationReport

    async def execute(
        self, input_data: EvidenceVerificationInput
    ) -> EvidenceVerificationReport:
        submission = input_data.submission
        integrity_flags: list[str] = []
        if not input_data.storage_verified:
            integrity_flags.append("unverified_storage_object")
        if not input_data.scanner_clean:
            integrity_flags.append("scanner_not_clean")
        if submission.media_type in {
            "application/zip",
            "application/x-executable",
            "application/x-msdownload",
        }:
            integrity_flags.append("sandbox_review_required")

        criteria_results = _criteria_results(
            submission.acceptance_criteria,
            submission.content_text or "",
        )
        quality = (
            round(
                sum(1 for result in criteria_results if result.satisfied)
                / len(criteria_results),
                4,
            )
            if criteria_results
            else 0.0
        )
        if integrity_flags:
            decision = EvidenceStatus.ADMIN_REVIEW_REQUIRED
            status = AgentExecutionStatus.ADMIN_REVIEW_REQUIRED
            feedback = "The artifact requires trusted storage or integrity review."
        elif not submission.content_text:
            decision = EvidenceStatus.ADMIN_REVIEW_REQUIRED
            status = AgentExecutionStatus.ADMIN_REVIEW_REQUIRED
            feedback = "The artifact has no extractable content and needs human review."
        elif quality >= 0.7:
            decision = EvidenceStatus.VERIFIED
            status = AgentExecutionStatus.COMPLETED
            feedback = "The artifact satisfies the stated acceptance criteria."
        elif quality >= 0.4:
            decision = EvidenceStatus.RESUBMISSION_REQUIRED
            status = AgentExecutionStatus.INPUT_REQUIRED
            feedback = "The artifact partially satisfies the criteria; revise and resubmit."
        else:
            decision = EvidenceStatus.REJECTED
            status = AgentExecutionStatus.COMPLETED
            feedback = "The artifact does not yet demonstrate the required outcome."
        return EvidenceVerificationReport(
            status=status,
            confidence=0.95 if not integrity_flags and submission.content_text else 0.55,
            evidence_id=input_data.evidence_id,
            decision=decision,
            quality_score=quality,
            criteria_results=criteria_results,
            integrity_flags=integrity_flags,
            feedback=feedback,
            evidence_refs=[submission.storage_key, submission.sha256],
            warnings=integrity_flags,
            next_actions=(
                ["Wait for admin review"]
                if decision == EvidenceStatus.ADMIN_REVIEW_REQUIRED
                else ["Revise the artifact and submit new evidence"]
                if decision == EvidenceStatus.RESUBMISSION_REQUIRED
                else []
            ),
        )


def _criteria_results(criteria: list[str], content: str) -> list[CriteriaResult]:
    content_tokens = _tokens(content)
    results: list[CriteriaResult] = []
    for criterion in criteria:
        expected = _tokens(criterion)
        coverage = len(content_tokens & expected) / len(expected) if expected else 0
        satisfied = coverage >= 0.5
        results.append(
            CriteriaResult(
                criterion=criterion,
                satisfied=satisfied,
                confidence=round(min(0.55 + coverage * 0.45, 1.0), 4),
                explanation=(
                    f"Matched {len(content_tokens & expected)} of "
                    f"{len(expected)} meaningful criterion terms."
                ),
            )
        )
    return results


def _tokens(value: str) -> set[str]:
    stopwords = {
        "with",
        "from",
        "that",
        "this",
        "into",
        "must",
        "should",
        "have",
        "been",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 3 and token not in stopwords
    }

