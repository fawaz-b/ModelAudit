"""Load and validate the ModelAudit PROBAST+AI evaluation subset."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_FRAMEWORK_PATH = Path(__file__).resolve().parents[1] / "framework" / "probast_ai_subset.json"
EXPECTED_QUESTION_IDS = {
    "PE-1.3", "PE-2.4", "PE-3.1", "PE-4.1", "PE-4.2", "PE-4.3", "PE-4.5", "PE-4.7"
}
EXPECTED_DOMAINS = {"D1", "D2", "D3", "D4"}
VALID_RESPONSES = {"yes", "probably_yes", "probably_no", "no", "no_information", "not_applicable"}
EXPECTED_DOMAIN_QUESTION_COUNTS = {"D1": 3, "D2": 4, "D3": 4, "D4": 7}


class ProbastFrameworkError(ValueError):
    """Raised when the PROBAST+AI framework configuration is invalid."""


def load_probast_framework(path: Path | str = DEFAULT_FRAMEWORK_PATH) -> dict[str, Any]:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProbastFrameworkError(f"Could not load PROBAST+AI JSON at {path}: {exc}") from exc
    validate_probast_framework(data)
    return data


def validate_probast_framework(data: dict[str, Any]) -> None:
    if not isinstance(data, dict):
        raise ProbastFrameworkError("Framework root must be an object")
    if data.get("framework") != "PROBAST+AI" or data.get("branch") != "evaluation":
        raise ProbastFrameworkError("Expected the PROBAST+AI evaluation branch")
    if data.get("licence", {}).get("name") != "CC BY-NC 4.0":
        raise ProbastFrameworkError("Expected explicit CC BY-NC 4.0 licence metadata")

    questions = data.get("questions")
    if not isinstance(questions, list) or len(questions) != 8:
        raise ProbastFrameworkError("MVP must contain exactly eight questions")
    ids = [q.get("id") for q in questions]
    if len(ids) != len(set(ids)):
        raise ProbastFrameworkError("Question IDs must be unique")
    if set(ids) != EXPECTED_QUESTION_IDS:
        raise ProbastFrameworkError(f"Unexpected question set: {sorted(set(ids))}")

    domains = data.get("domains")
    if not isinstance(domains, list) or {d.get("id") for d in domains} != EXPECTED_DOMAINS:
        raise ProbastFrameworkError("Expected exactly domains D1-D4")
    domain_map = {d["id"]: d for d in domains}
    for domain_id, expected_count in EXPECTED_DOMAIN_QUESTION_COUNTS.items():
        domain = domain_map[domain_id]
        coverage = domain.get("coverage", {})
        if coverage.get("official") != expected_count:
            raise ProbastFrameworkError(f"Incorrect official question count for {domain_id}")
        if coverage.get("complete") is not False:
            raise ProbastFrameworkError(f"Subset domain {domain_id} must be marked incomplete")

    seen_by_domain: dict[str, set[str]] = {domain_id: set() for domain_id in EXPECTED_DOMAINS}
    for question in questions:
        question_id = question["id"]
        domain_id = question.get("domain_id")
        if domain_id not in EXPECTED_DOMAINS:
            raise ProbastFrameworkError(f"Invalid domain for {question_id}: {domain_id}")
        seen_by_domain[domain_id].add(question_id)
        if question.get("response_scale") != "standard":
            raise ProbastFrameworkError(f"Unexpected response scale for {question_id}")
        if question_id == "PE-4.5":
            rule = question.get("conditional_rule")
            if not isinstance(rule, dict) or rule.get("when_condition_false") != "not_applicable":
                raise ProbastFrameworkError("PE-4.5 must conditionally allow not_applicable")
            if question.get("not_applicable_allowed") is not True:
                raise ProbastFrameworkError("PE-4.5 must declare not_applicable_allowed")
        elif question.get("not_applicable_allowed") is not False:
            raise ProbastFrameworkError(f"Unexpected not_applicable permission for {question_id}")

    for domain_id, domain in domain_map.items():
        declared = set(domain.get("included_question_ids", []))
        if declared != seen_by_domain[domain_id]:
            raise ProbastFrameworkError(f"Question/domain membership mismatch for {domain_id}")
        coverage = domain["coverage"]
        if coverage.get("included") != len(declared):
            raise ProbastFrameworkError(f"Incorrect included question count for {domain_id}")

    response_options = {item.get("value") for item in data.get("response_scale", {}).get("standard", {}).get("options", [])}
    if response_options != VALID_RESPONSES:
        raise ProbastFrameworkError("Response scale does not match the official six options")

    if data.get("domain_judgement", {}).get("modelaudit_decisions", [{}])[0].get("status") != "proposed":
        raise ProbastFrameworkError("Expected explicit proposed ModelAudit domain-judgement policy")
