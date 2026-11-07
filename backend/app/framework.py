"""Load and validate the data-driven TRIPOD+AI MVP framework."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FRAMEWORK_PATH = (
    Path(__file__).resolve().parents[1] / "framework" / "tripod_ai_subset.json"
)
VALID_CATEGORIES = {
    "reported",
    "partially_reported",
    "author_stated_unavailable",
    "not_found_in_main_text",
    "unclear",
    "not_applicable",
}
VALID_OPERATORS = {"equals", "in"}


class FrameworkError(ValueError):
    """Raised when a framework definition is malformed."""


def load_framework(path: Path | str = FRAMEWORK_PATH) -> dict[str, Any]:
    path = Path(path)
    try:
        framework = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FrameworkError(f"Could not load framework JSON at {path}: {exc}") from exc
    validate_framework(framework)
    return framework


def validate_framework(framework: dict[str, Any]) -> None:
    if not isinstance(framework, dict):
        raise FrameworkError("Framework root must be an object.")
    items = framework.get("items")
    if not isinstance(items, list) or not items:
        raise FrameworkError("Framework must contain a non-empty items list.")
    item_ids: set[str] = set()
    for item in items:
        item_id = item.get("id")
        if not isinstance(item_id, str) or not item_id:
            raise FrameworkError("Every item must have a non-empty id.")
        if item_id in item_ids:
            raise FrameworkError(f"Duplicate framework item id: {item_id}")
        item_ids.add(item_id)
        item_condition = item.get("applies_when")
        if item_condition is not None and (
            not isinstance(item_condition, dict)
            or not isinstance(item_condition.get("field"), str)
            or item_condition.get("operator") not in VALID_OPERATORS
            or "value" not in item_condition
        ):
            raise FrameworkError(
                f"Invalid item-level applies_when condition on {item_id}."
            )
        elements = item.get("elements")
        if not isinstance(elements, list) or not elements:
            raise FrameworkError(f"{item_id} must contain a non-empty elements list.")
        element_keys: set[str] = set()
        for element in elements:
            key = element.get("key")
            if not isinstance(key, str) or not key:
                raise FrameworkError(f"Every element in {item_id} must have a key.")
            if key in element_keys:
                raise FrameworkError(f"Duplicate element key {item_id}.{key}")
            element_keys.add(key)
            if not isinstance(element.get("required"), bool):
                raise FrameworkError(
                    f"{item_id}.{key} must define required as a boolean."
                )
            condition = element.get("applies_when")
            if condition is not None:
                if (
                    not isinstance(condition, dict)
                    or not isinstance(condition.get("field"), str)
                    or condition.get("operator") not in VALID_OPERATORS
                    or "value" not in condition
                ):
                    raise FrameworkError(
                        f"Invalid applies_when condition on {item_id}.{key}."
                    )
        scheme = item.get("judgement_categories")
        if scheme is not None and not isinstance(scheme, list):
            raise FrameworkError(
                f"{item_id}.judgement_categories must be a list when present."
            )
    categories = framework.get("judgement_scheme", {}).get("categories", {})
    missing = VALID_CATEGORIES - set(categories)
    if missing:
        raise FrameworkError(
            f"Missing judgement category definitions: {sorted(missing)}"
        )


def condition_applies(
    condition: dict[str, Any] | None, study_context: dict[str, Any]
) -> bool | None:
    """Return True/False; None means the condition cannot yet be resolved."""
    if condition is None:
        return True
    field = condition["field"]
    if field not in study_context or study_context[field] is None:
        return None
    actual = study_context[field]
    expected = condition["value"]
    if condition["operator"] == "equals":
        return actual == expected
    if condition["operator"] == "in":
        return actual in expected
    raise FrameworkError(f"Unsupported condition operator: {condition['operator']}")


def derive_item_judgement(
    item: dict[str, Any],
    element_findings: dict[str, dict[str, Any]],
    study_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Derive an item category from element findings; never trusts an LLM category."""
    context = study_context or {}
    item_applies = condition_applies(item.get("applies_when"), context)
    if item_applies is False:
        return {
            "category": "not_applicable",
            "required_elements": [],
            "unresolved_conditions": [],
            "flags": [],
        }
    if item_applies is None:
        return {
            "category": "unclear",
            "required_elements": [],
            "unresolved_conditions": ["item_applicability"],
            "flags": ["study_context_incomplete"],
        }
    applicable: list[tuple[dict[str, Any], dict[str, Any]]] = []
    unresolved_conditions: list[str] = []

    for element in item["elements"]:
        applies = condition_applies(element.get("applies_when"), context)
        if applies is None:
            unresolved_conditions.append(element["key"])
            continue
        if applies:
            applicable.append((element, element_findings.get(element["key"], {})))

    required = [(el, finding) for el, finding in applicable if el["required"]]
    if unresolved_conditions:
        return {
            "category": "unclear",
            "required_elements": [el["key"] for el, _ in required],
            "unresolved_conditions": unresolved_conditions,
            "flags": ["study_context_incomplete"],
        }
    if not required:
        return {
            "category": "not_applicable",
            "required_elements": [],
            "unresolved_conditions": [],
            "flags": [],
        }

    statuses: list[str] = []
    flags: list[str] = []
    for element, finding in required:
        status = finding.get("status", "unclear")
        if status not in VALID_CATEGORIES:
            status = "unclear"
            flags.append(f"invalid_status:{element['key']}")
        if (
            status in {"reported", "partially_reported"}
            and finding.get("evidence_verified") is not True
        ):
            status = "unclear"
            flags.append(f"evidence_unverified:{element['key']}")
        statuses.append(status)

    if all(s == "not_found_in_main_text" for s in statuses):
        category = "not_found_in_main_text"
    elif all(s == "author_stated_unavailable" for s in statuses):
        category = "author_stated_unavailable"
    elif all(s == "reported" for s in statuses):
        category = "reported"
    elif all(s in {"reported", "author_stated_unavailable"} for s in statuses):
        category = "reported" if "reported" in statuses else "author_stated_unavailable"
    elif all(s == "unclear" for s in statuses):
        category = "unclear"
    else:
        category = "partially_reported"

    return {
        "category": category,
        "required_elements": [el["key"] for el, _ in required],
        "unresolved_conditions": [],
        "flags": flags,
    }
