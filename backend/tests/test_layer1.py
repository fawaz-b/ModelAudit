"""Regression tests for the final Layer 1 TRIPOD+AI corrections."""

from app.framework import load_framework
from app.judge import assess_item
from app.schemas import ElementFinding, StudyContext


def test_trivial_required_flag_corrections_are_present():
    framework = load_framework()
    elements = {
        item["id"]: {element["key"]: element for element in item["elements"]}
        for item in framework["items"]
    }

    assert elements["T-8a"]["rationale_for_outcome"]["required"] is False
    assert elements["T-8a"]["consistency_across_groups"]["required"] is False
    assert elements["T-23a"]["confidence_intervals"]["required"] is True
    assert elements["T-23a"]["subgroup_performance"]["required"] is False


def test_not_found_in_retrieved_excerpts_is_downgraded_to_unclear():
    item = {
        "id": "T-test",
        "elements": [
            {
                "key": "test_element",
                "required": True,
                "description": "A test reporting element.",
            }
        ],
    }
    finding = ElementFinding(
        element_key="test_element",
        status="not_found_in_main_text",
        explanation="No supporting passage was found in the retrieved excerpts.",
        evidence=[],
    )

    result = assess_item(
        item=item,
        findings={"test_element": finding},
        study_context=StudyContext(),
        passages=[],
    )

    assert result.element_findings[0].status == "unclear"
    assert result.category == "unclear"
    assert "retrieval_may_be_incomplete:test_element" in result.flags
    assert "absence_claim_requires_review:test_element" not in result.flags
