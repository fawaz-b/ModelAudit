"""Deterministic PROBAST+AI question-level assessment assembly."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.probast_schemas import (
    ProbastApplicabilityFinding,
    ProbastAssessment,
    ProbastDomainSummary,
    ProbastQuestionFinding,
    ProbastStudyContext,
)
from app.probast_verify import verify_probast_finding


def build_probast_assessment(
    framework: dict[str, Any],
    document_id: str,
    context: ProbastStudyContext,
    findings: Sequence[ProbastQuestionFinding],
    source_chunks: Sequence[Any],
    model_identifier: str | None = None,
) -> ProbastAssessment:
    verified = [verify_probast_finding(f, source_chunks) for f in findings]
    domain_summaries = []
    for domain in framework["domains"]:
        domain_summaries.append(
            ProbastDomainSummary(
                domain_id=domain["id"],
                included_questions=domain["included_question_ids"],
                official_question_count=domain["coverage"]["official"],
                coverage_complete=False,
                risk_of_bias_judgement="not_assessed",
                rationale=(
                    f"ModelAudit assessed {domain['coverage']['included']} of "
                    f"{domain['coverage']['official']} official questions. "
                    "No official domain judgement is generated from this subset."
                ),
            )
        )
    applicability = [
        ProbastApplicabilityFinding(
            domain_id=domain_id,
            judgement="not_assessed",
            picots_supplied=context.picots.supplied,
            rationale=(
                "Reviewer-supplied PICOTS context is present, but applicability "
                "is not automatically rated by this MVP."
                if context.picots.supplied
                else "Applicability requires reviewer-supplied PICOTS/intended-use context."
            ),
        )
        for domain_id in ("D1", "D2", "D3")
    ]
    has_unassessed = any(f.assessment_state == "not_assessed" for f in verified)
    has_review = any(
        f.flags or f.reviewer_status == "pending" or f.response == "no_information"
        for f in verified
    )
    limitations = [
        "This is an eight-question subset of the PROBAST+AI model-evaluation branch, not the complete tool.",
        "Official domain-level and overall risk-of-bias judgements are not generated.",
        "Applicability is not automatically rated; reviewer PICOTS context is required.",
        "Evidence quotation verification confirms source location, not semantic support; human review remains necessary.",
        "The subset omits PE-4.4 and PE-4.6, among other signalling questions.",
    ]
    return ProbastAssessment(
        framework_version=framework["framework_version"],
        document_id=document_id,
        model_identifier=model_identifier,
        context=context,
        findings=verified,
        domains=domain_summaries,
        applicability=applicability,
        assessment_status=(
            "requires_review" if has_unassessed or has_review else "completed"
        ),
        limitations=limitations,
    )
