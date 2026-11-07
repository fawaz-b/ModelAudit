"""Evidence quotation verification for ModelAudit assessments."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from .schemas import ElementFinding, EvidenceReference, RetrievedPassage

EVIDENCE_REQUIRED_STATUSES = {
    "reported",
    "partially_reported",
    "author_stated_unavailable",
}


def _as_dict(value: Any) -> dict[str, Any]:
    """Convert a Pydantic model or mapping into a dictionary."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"Expected a mapping or Pydantic model, got {type(value)}")


def normalise_evidence_text(text: str) -> str:
    """
    Normalise PDF-extracted text for exact quotation matching.

    This permits Unicode punctuation and whitespace differences and rejoins
    words split by a line-break hyphen. It does not perform fuzzy matching.
    """
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]", "-", text)
    text = re.sub(r"(?<=\w)-\s+(?=[a-z])", "-", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def verify_evidence(
    evidence: Sequence[EvidenceReference | Mapping[str, Any]],
    passages: Sequence[RetrievedPassage | Mapping[str, Any]],
) -> bool:
    """
    Verify that every quotation exists in its cited chunk and page.

    All references must resolve. An empty evidence list is never verified.
    Matching is exact after conservative Unicode/whitespace normalisation.
    """
    if not evidence:
        return False

    passage_lookup: dict[str, dict[str, Any]] = {}
    for passage in passages:
        passage_data = _as_dict(passage)
        chunk_id = passage_data.get("chunk_id")
        if isinstance(chunk_id, str) and chunk_id:
            passage_lookup[chunk_id] = passage_data

    for reference in evidence:
        ref = _as_dict(reference)
        chunk_id = ref.get("chunk_id")

        if not isinstance(chunk_id, str):
            return False

        chunk = passage_lookup.get(chunk_id)

        if chunk is None or ref.get("page") != chunk.get("page"):
            return False

        quote = ref.get("quote")
        chunk_text = chunk.get("text")
        if not isinstance(quote, str) or not isinstance(chunk_text, str):
            return False

        normalised_quote = normalise_evidence_text(quote)
        normalised_chunk = normalise_evidence_text(chunk_text)
        if not normalised_quote or normalised_quote not in normalised_chunk:
            return False

    return True


def assess_element(
    finding: ElementFinding | Mapping[str, Any],
    passages: Sequence[RetrievedPassage | Mapping[str, Any]],
) -> ElementFinding:
    """
    Verify an element finding and correct unsupported positive claims.

    `not_found_in_main_text` is not verifiable by a quotation. It is retained
    as a proposed absence finding, but the item judge must flag it for review.
    """
    data = _as_dict(finding)
    evidence = data.get("evidence", [])
    status = data["status"]
    verified = verify_evidence(evidence, passages)
    data["evidence_verified"] = verified

    if status in EVIDENCE_REQUIRED_STATUSES and not verified:
        data["status"] = "unclear"
        existing_comment = data.get("reviewer_comment")
        warning = (
            "The proposed status was downgraded because its supporting "
            "quotation could not be verified against the cited source."
        )
        data["reviewer_comment"] = (
            f"{existing_comment} {warning}" if existing_comment else warning
        )

    return ElementFinding.model_validate(data)
