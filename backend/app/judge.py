"""Deterministic item and framework judgement for ModelAudit."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .framework import derive_item_judgement
from .schemas import (
    ElementFinding,
    FrameworkAssessment,
    ItemAssessment,
    RetrievedPassage,
    StudyContext,
)
from .verify import assess_element


def _as_dict(value: Any) -> dict[str, Any]:
    """Convert a Pydantic model or mapping into a dictionary."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(
        f"Expected a mapping or Pydantic model, got {type(value)}"
    )


def assess_item(
    item: dict[str, Any],
    findings: Mapping[str, ElementFinding | Mapping[str, Any]],
    study_context: StudyContext | Mapping[str, Any],
    passages: Sequence[RetrievedPassage | Mapping[str, Any]],
    not_assessed_reason: str | None = None,
) -> ItemAssessment:
    """Verify element findings and derive the item's category deterministically."""

    if not_assessed_reason:
        unassessed_findings = [
            ElementFinding(
                element_key=element["key"],
                status="not_assessed",
                explanation=(
                    "This element was not assessed because processing stopped "
                    f"before this item could be evaluated: {not_assessed_reason}."
                ),
                reviewer_comment=(
                    "Assess this item when the required provider/service is available."
                ),
            )
            for element in item["elements"]
        ]
        return ItemAssessment(
            item_id=item["id"],
            element_findings=unassessed_findings,
            category="not_assessed",
            required_elements=[
                element["key"]
                for element in item["elements"]
                if element.get("required", False)
            ],
            flags=[f"assessment_not_run:{not_assessed_reason}"],
            reviewer_comment=(
                "No judgement was made for this item. It must be assessed "
                "before the framework assessment can be considered complete."
            ),
        )

    context = _as_dict(study_context)
    verified_findings: list[ElementFinding] = []
    findings_for_derivation: dict[str, dict[str, Any]] = {}
    review_flags: list[str] = []

    for element in item["elements"]:
        element_key = element["key"]
        raw_finding = findings.get(element_key)

        if raw_finding is None:
            finding = ElementFinding(
                element_key=element_key,
                status="unclear",
                explanation="No assessment finding was supplied for this element.",
                reviewer_comment="The element requires assessment or reviewer clarification.",
            )
        else:
            finding = assess_element(raw_finding, passages)

        if finding.status == "not_found_in_main_text":
            # The LLM sees only a limited set of retrieved excerpts. A quote
            # verification pass against all chunks does not establish that the
            # excerpts provided adequate coverage to support an absence claim.
            finding = finding.model_copy(
                update={
                    "status": "unclear",
                    "reviewer_comment": (
                        "The supplied excerpts do not establish that this "
                        "information is absent from the entire main text. "
                        "Review the full paper before assigning an absence "
                        "judgement."
                    ),
                }
            )
            review_flags.append(
                f"retrieval_may_be_incomplete:{element_key}"
            )

        verified_findings.append(finding)
        findings_for_derivation[element_key] = {
            "status": finding.status,
            "evidence_verified": finding.evidence_verified,
        }

    judgement = derive_item_judgement(
        item=item,
        element_findings=findings_for_derivation,
        study_context=context,
    )

    return ItemAssessment(
        item_id=item["id"],
        element_findings=verified_findings,
        category=judgement["category"],
        required_elements=judgement["required_elements"],
        unresolved_conditions=judgement["unresolved_conditions"],
        flags=[*judgement["flags"], *review_flags],
    )


def assess_framework(
    framework: dict[str, Any],
    document_id: str,
    study_context: StudyContext,
    findings_by_item: Mapping[
        str, Mapping[str, ElementFinding | Mapping[str, Any]]
    ],
    passages: Sequence[RetrievedPassage | Mapping[str, Any]],
    not_assessed_items: Mapping[str, str] | None = None,
) -> FrameworkAssessment:
    """Assemble a framework assessment from verified findings."""

    item_assessments: list[ItemAssessment] = []

    for item in framework["items"]:
        result = assess_item(
            item=item,
            findings=findings_by_item.get(item["id"], {}),
            study_context=study_context,
            passages=passages,
            not_assessed_reason=(not_assessed_items or {}).get(item["id"]),
        )
        item_assessments.append(result)

    requires_review = any(
        assessment.category in {"unclear", "not_assessed"}
        or assessment.flags
        or assessment.unresolved_conditions
        for assessment in item_assessments
    )

    return FrameworkAssessment(
        framework_id=framework["framework"],
        framework_name=framework["framework"],
        framework_version=framework["framework_version"],
        document_id=document_id,
        study_context=study_context,
        items=item_assessments,
        assessment_status=(
            "requires_review" if requires_review else "completed"
        ),
    )
