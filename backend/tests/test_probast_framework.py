
import json
from pathlib import Path

import pytest
from app.probast_framework import (
    ProbastFrameworkError,
    validate_probast_framework,
)

FRAMEWORK_PATH = (
    Path(__file__).resolve().parents[1]
    / "framework"
    / "probast_ai_subset.json"
)


@pytest.fixture
def framework():
    return json.loads(FRAMEWORK_PATH.read_text(encoding="utf-8"))


def test_framework_configuration_is_valid(framework):
    validate_probast_framework(framework)


def test_rejects_missing_question(framework):
    framework["questions"].pop()

    with pytest.raises(ProbastFrameworkError, match="exactly eight"):
        validate_probast_framework(framework)


def test_rejects_duplicate_question_id(framework):
    framework["questions"][1]["id"] = framework["questions"][0]["id"]

    with pytest.raises(ProbastFrameworkError, match="unique"):
        validate_probast_framework(framework)


def test_pe_45_conditional_na_is_preserved(framework):
    question = next(
        item for item in framework["questions"]
        if item["id"] == "PE-4.5"
    )

    question["conditional_rule"]["when_condition_false"] = "no"

    with pytest.raises(
        ProbastFrameworkError,
        match="conditionally allow",
    ):
        validate_probast_framework(framework)


def test_rejects_false_complete_domain_claim(framework):
    framework["domains"][0]["coverage"]["complete"] = True

    with pytest.raises(
        ProbastFrameworkError,
        match="marked incomplete",
    ):
        validate_probast_framework(framework)


def test_rejects_question_domain_mismatch(framework):
    framework["questions"][0]["domain_id"] = "D4"

    with pytest.raises(
        ProbastFrameworkError,
        match="membership mismatch",
    ):
        validate_probast_framework(framework)


def test_question_finding_schema_accepts_official_id():
    from app.probast_schemas import ProbastQuestionFinding

    finding = ProbastQuestionFinding(
        question_id="PE-1.3",
        response="yes",
        explanation="The paper describes the cohort.",
    )

    assert finding.question_id == "PE-1.3"


def test_question_finding_schema_rejects_tripod_category():
    from app.probast_schemas import ProbastQuestionFinding
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ProbastQuestionFinding(
            question_id="PE-1.3",
            response="reported",  # type: ignore[arg-type]
            explanation="Not a PROBAST response.",
        )
