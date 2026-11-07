import pytest
from app.framework import (
    FrameworkError,
    condition_applies,
    derive_item_judgement,
    load_framework,
    validate_framework,
)


def test_framework_loads_and_has_exact_mvp_item_set():
    framework = load_framework()
    assert len(framework["items"]) == 14
    assert {item["id"] for item in framework["items"]} == {
        "T-3b",
        "T-5a",
        "T-5b",
        "T-6a",
        "T-6b",
        "T-8a",
        "T-9b",
        "T-10",
        "T-11",
        "T-12e",
        "T-16",
        "T-18e",
        "T-18f",
        "T-23a",
    }


def test_duplicate_element_keys_are_rejected():
    framework = {
        "items": [
            {
                "id": "T-X",
                "elements": [
                    {"key": "same", "required": True},
                    {"key": "same", "required": False},
                ],
            }
        ],
        "judgement_scheme": {
            "categories": {
                "reported": "",
                "partially_reported": "",
                "author_stated_unavailable": "",
                "not_found_in_main_text": "",
                "unclear": "",
                "not_applicable": "",
            }
        },
    }
    with pytest.raises(FrameworkError, match="Duplicate element key"):
        validate_framework(framework)


def test_conditional_element_is_unresolved_when_context_missing():
    condition = {"field": "study_type", "operator": "equals", "value": "prognostic"}
    assert condition_applies(condition, {}) is None
    assert condition_applies(condition, {"study_type": "prognostic"}) is True
    assert condition_applies(condition, {"study_type": "diagnostic"}) is False


def test_no_separate_evaluation_dataset_makes_t16_not_applicable():
    framework = load_framework()
    item = next(item for item in framework["items"] if item["id"] == "T-16")
    result = derive_item_judgement(item, {}, {"has_separate_evaluation_dataset": False})
    assert result["category"] == "not_applicable"


def test_missing_study_context_does_not_silently_mark_not_applicable():
    framework = load_framework()
    item = next(item for item in framework["items"] if item["id"] == "T-16")
    result = derive_item_judgement(item, {}, {})
    assert result["category"] == "unclear"
    assert "study_context_incomplete" in result["flags"]


def test_all_required_elements_reported_derives_reported():
    item = {
        "elements": [{"key": "a", "required": True}, {"key": "b", "required": True}]
    }
    findings = {
        "a": {"status": "reported", "evidence_verified": True},
        "b": {"status": "reported", "evidence_verified": True},
    }
    assert derive_item_judgement(item, findings)["category"] == "reported"


def test_unverified_quote_downgrades_to_unclear():
    item = {"elements": [{"key": "a", "required": True}]}
    result = derive_item_judgement(
        item, {"a": {"status": "reported", "evidence_verified": False}}
    )
    assert result["category"] == "unclear"
    assert "evidence_unverified:a" in result["flags"]


def test_mix_of_reported_and_not_found_is_partial():
    item = {
        "elements": [{"key": "a", "required": True}, {"key": "b", "required": True}]
    }
    findings = {
        "a": {"status": "reported", "evidence_verified": True},
        "b": {"status": "not_found_in_main_text"},
    }
    assert derive_item_judgement(item, findings)["category"] == "partially_reported"


def test_required_confidence_intervals_and_optional_conditional_subgroups():
    framework = load_framework()
    item = next(item for item in framework["items"] if item["id"] == "T-23a")
    elements = {el["key"]: el for el in item["elements"]}

    assert elements["confidence_intervals"]["required"] is True

    subgroup = elements["subgroup_performance"]
    assert subgroup["required"] is False
    assert subgroup["applies_when"] is not None
