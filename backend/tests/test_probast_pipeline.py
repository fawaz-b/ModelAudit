import json
from pathlib import Path

import pytest
from app.probast_audit import _pe45_applicability
from app.probast_framework import (
    ProbastFrameworkError,
    validate_probast_framework,
)
from app.probast_schemas import (
    ProbastQuestionFinding,
    ProbastStudyContext,
)
from app.probast_verify import verify_probast_evidence
from pydantic import ValidationError

FRAMEWORK_PATH = Path(__file__).parents[1] / "framework" / "probast_ai_subset.json"


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


def test_pe45_uses_reviewed_conditional_structure(framework):
    question = next(q for q in framework["questions"] if q["id"] == "PE-4.5")
    question["conditional_rule"]["applicability_by_component"][
        "internal_training_test_split"
    ] = "not_applicable"
    with pytest.raises(ProbastFrameworkError, match="applicability"):
        validate_probast_framework(framework)


def test_domains_remain_incomplete(framework):
    framework["domains"][0]["coverage"]["complete"] = True
    with pytest.raises(ProbastFrameworkError, match="incomplete"):
        validate_probast_framework(framework)


def test_rejects_question_domain_mismatch(framework):
    framework["questions"][0]["domain_id"] = "D4"
    with pytest.raises(ProbastFrameworkError, match="membership mismatch"):
        validate_probast_framework(framework)


def test_pe45_apparent_and_external_not_applicable():
    ctx = ProbastStudyContext(evaluation_components=["apparent", "external"])
    assert _pe45_applicability("apparent", ctx) is False
    assert _pe45_applicability("external", ctx) is False


def test_pe45_internal_split_applicable():
    ctx = ProbastStudyContext(
        evaluation_components=["internal"],
        validation_method="training_test_split",
        has_training_test_split=True,
    )
    assert _pe45_applicability("internal", ctx) is True


def test_pe45_internal_resampling_not_applicable():
    ctx = ProbastStudyContext(
        evaluation_components=["internal"],
        validation_method="bootstrap",
        has_training_test_split=False,
    )
    assert _pe45_applicability("internal", ctx) is False


def test_pe45_unknown_internal_design_unresolved():
    ctx = ProbastStudyContext(evaluation_components=["internal"])
    assert _pe45_applicability("internal", ctx) is None


def test_response_schema_rejects_tripod_category():
    with pytest.raises(ValidationError):
        ProbastQuestionFinding(
            question_id="PE-1.3",
            response="reported",
            explanation="Not a PROBAST response.",
        )


def test_directional_response_can_be_parsed_before_verification():
    finding = ProbastQuestionFinding(
        question_id="PE-1.3",
        response="yes",
        explanation="Evidence suggests representativeness.",
        evidence=[
            {"quote": "The cohort was representative.", "page": 1, "chunk_id": "c1"}
        ],
    )
    assert finding.evidence_verified is False


def test_not_assessed_is_not_a_signalling_response():
    finding = ProbastQuestionFinding(
        question_id="PE-1.3",
        assessment_state="not_assessed",
        response=None,
        explanation="Provider quota exhausted.",
        not_assessed_reason="LLMProviderError",
    )
    assert finding.response is None
    assert finding.assessment_state == "not_assessed"


def test_quote_verification_requires_exact_source_chunk():
    chunks = [
        {"chunk_id": "c1", "page": 2, "text": "The cohort included 120 participants."}
    ]
    evidence = [
        {"quote": "The cohort included 120 participants.", "page": 2, "chunk_id": "c1"}
    ]
    assert verify_probast_evidence(evidence, chunks) is True
    wrong_page = [
        {"quote": "The cohort included 120 participants.", "page": 3, "chunk_id": "c1"}
    ]
    assert verify_probast_evidence(wrong_page, chunks) is False


def test_unverified_directional_finding_is_downgraded():
    from app.probast_verify import verify_probast_finding

    finding = ProbastQuestionFinding(
        question_id="PE-1.3",
        response="yes",
        explanation="The paper describes a representative cohort.",
        evidence=[
            {
                "quote": "The cohort was representative.",
                "page": 1,
                "chunk_id": "missing",
            }
        ],
    )
    checked = verify_probast_finding(finding, [])
    assert checked.assessment_state == "not_assessed"
    assert checked.response is None
    assert "evidence_verification_failed" in checked.flags


def test_assessment_assembly_never_emits_domain_judgements(framework):
    from app.probast_judge import build_probast_assessment

    context = ProbastStudyContext(evaluation_components=["external"])
    findings = [
        ProbastQuestionFinding(
            question_id="PE-1.3",
            evaluation_component="external",
            response="no_information",
            explanation="The supplied report excerpts do not provide enough information.",
        )
    ]
    assessment = build_probast_assessment(
        framework=framework,
        document_id="doc-123",
        context=context,
        findings=findings,
        source_chunks=[],
    )
    assert len(assessment.domains) == 4
    assert all(d.risk_of_bias_judgement == "not_assessed" for d in assessment.domains)
    assert assessment.assessment_status == "requires_review"
