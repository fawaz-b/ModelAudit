"""Load and validate the ModelAudit PROBAST+AI evaluation subset."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_FRAMEWORK_PATH = (
    Path(__file__).resolve().parents[1] / "framework" / "probast_ai_subset.json"
)

EXPECTED_QUESTION_IDS = {
    "PE-1.3",
    "PE-2.4",
    "PE-3.1",
    "PE-4.1",
    "PE-4.2",
    "PE-4.3",
    "PE-4.5",
    "PE-4.7",
}

EXPECTED_DOMAINS = {"D1", "D2", "D3", "D4"}

VALID_RESPONSES = {
    "yes",
    "probably_yes",
    "probably_no",
    "no",
    "no_information",
    "not_applicable",
}

EXPECTED_DOMAIN_QUESTION_COUNTS = {
    "D1": 3,
    "D2": 4,
    "D3": 4,
    "D4": 7,
}


class ProbastFrameworkError(ValueError):
    """Raised when the PROBAST+AI framework configuration is invalid."""


def load_probast_framework(
    path: Path | str = DEFAULT_FRAMEWORK_PATH,
) -> dict[str, Any]:
    path = Path(path)

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProbastFrameworkError(
            f"Could not load PROBAST+AI JSON at {path}: {exc}"
        ) from exc

    validate_probast_framework(data)

    return data


def validate_probast_framework(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ProbastFrameworkError("Framework root must be an object.")

    if data.get("framework") != "PROBAST+AI" or data.get("branch") != "evaluation":
        raise ProbastFrameworkError("Expected the PROBAST+AI evaluation branch.")

    if data.get("licence", {}).get("name") != "CC BY-NC 4.0":
        raise ProbastFrameworkError("Expected explicit CC BY-NC 4.0 licence metadata.")

    questions = data.get("questions")

    if not isinstance(questions, list) or len(questions) != 8:
        raise ProbastFrameworkError("MVP must contain exactly eight questions.")

    # Validate question objects and IDs before comparing the question set.
    ids: list[str] = []

    for question in questions:
        if not isinstance(question, dict):
            raise ProbastFrameworkError("Each question must be an object.")

        question_id = question.get("id")

        if not isinstance(question_id, str) or not question_id.strip():
            raise ProbastFrameworkError(
                "Each question must have a non-empty string ID."
            )

        ids.append(question_id)

    if len(ids) != len(set(ids)):
        raise ProbastFrameworkError("Question IDs must be unique.")

    if set(ids) != EXPECTED_QUESTION_IDS:
        raise ProbastFrameworkError(f"Unexpected question set: {sorted(set(ids))}")

    # Validate the required PROBAST+AI domains.
    domains = data.get("domains")

    if (
        not isinstance(domains, list)
        or {d.get("id") for d in domains if isinstance(d, dict)} != EXPECTED_DOMAINS
    ):
        raise ProbastFrameworkError("Expected exactly domains D1-D4.")

    domain_map = {d["id"]: d for d in domains if isinstance(d, dict)}

    seen_by_domain: dict[str, set[str]] = {key: set() for key in EXPECTED_DOMAINS}

    for question in questions:
        qid = question["id"]
        domain_id = question.get("domain_id")

        if domain_id not in EXPECTED_DOMAINS:
            raise ProbastFrameworkError(f"Invalid domain for {qid}: {domain_id}")

        seen_by_domain[domain_id].add(qid)

        if question.get("response_scale") != "standard":
            raise ProbastFrameworkError(f"Unexpected response scale for {qid}.")

        if not question.get("official_wording"):
            raise ProbastFrameworkError(f"Missing official wording for {qid}.")

        if not isinstance(question.get("official_guidance"), dict):
            raise ProbastFrameworkError(
                f"Missing reviewed official guidance for {qid}."
            )

        if not isinstance(question.get("modelaudit"), dict):
            raise ProbastFrameworkError(f"Missing ModelAudit guidance for {qid}.")

    # Validate domain coverage and question membership.
    for domain_id, expected_count in EXPECTED_DOMAIN_QUESTION_COUNTS.items():
        domain = domain_map[domain_id]
        coverage = domain.get("coverage", {})

        if coverage.get("official") != expected_count:
            raise ProbastFrameworkError(
                f"Incorrect official question count for {domain_id}."
            )

        if coverage.get("complete") is not False:
            raise ProbastFrameworkError(
                f"Subset domain {domain_id} must be marked incomplete."
            )

        declared = set(domain.get("included_question_ids", []))

        if declared != seen_by_domain[domain_id]:
            raise ProbastFrameworkError(
                f"Question/domain membership mismatch for {domain_id}."
            )

        if coverage.get("included") != len(declared):
            raise ProbastFrameworkError(
                f"Incorrect included question count for {domain_id}."
            )

    # Validate the official response scale.
    response_scale = data.get("response_scale", {})
    standard_scale = response_scale.get("standard", {})
    options = standard_scale.get("options", [])

    if not isinstance(options, list):
        raise ProbastFrameworkError("Response scale options must be a list.")

    response_options = {item.get("value") for item in options if isinstance(item, dict)}

    if response_options != VALID_RESPONSES:
        raise ProbastFrameworkError(
            "Response scale does not match the official six options."
        )

    # PE-4.1 must explicitly declare evaluation-component dependencies.
    pe41 = next(q for q in questions if q["id"] == "PE-4.1")

    if pe41.get("conditional_rule", {}).get("type") != "evaluation_component_dependent":
        raise ProbastFrameworkError(
            "PE-4.1 must declare evaluation-component dependencies."
        )


    # PE-4.5 must exist and preserve its conditional applicability rule.
    pe45 = next(
        (
            question
            for question in questions
            if question.get("id") == "PE-4.5"
        ),
        None,
    )

    if pe45 is None:
        raise ProbastFrameworkError("PE-4.5 is required.")

    conditional_rule: dict[str, Any] = pe45.get("conditional_rule")

    if not isinstance(conditional_rule, dict):
        raise ProbastFrameworkError(
            "PE-4.5 must define a conditional rule that conditionally allows "
            "not_applicable."
        )

    when_condition_false = conditional_rule.get("when_condition_false")

    if (
        when_condition_false is not None
        and when_condition_false != "not_applicable"
    ):
        raise ProbastFrameworkError(
            "PE-4.5 must conditionally allow not_applicable when its condition is false."
        )

    expected_applicability = {
        "apparent": "not_applicable",
        "external": "not_applicable",
        "internal_resampling_without_training_test_split": "not_applicable",
        "internal_training_test_split": "applicable",
    }

    if (
        conditional_rule.get("applicability_by_component")
        != expected_applicability
    ):
        raise ProbastFrameworkError(
            "PE-4.5 applicability does not match the reviewed conditional rule."
        )

    # Validate the ModelAudit domain-judgement policy.
    decisions = data.get("domain_judgement", {}).get("modelaudit_decisions", [])

    if not decisions or decisions[0].get("status") != "proposed":
        raise ProbastFrameworkError(
            "Expected explicit proposed ModelAudit domain-judgement policy."
        )

    if not data.get("omitted_questions"):
        raise ProbastFrameworkError("Omitted official questions must be disclosed.")
