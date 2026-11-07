"""Evidence verification for PROBAST+AI question findings."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from app.probast_schemas import ProbastEvidenceReference, ProbastQuestionFinding


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    raise TypeError(f"Expected mapping or Pydantic model, got {type(value)}")


def normalise_evidence_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\u2010-\u2015\u2212\uFE58\uFE63\uFF0D]", "-", text)
    text = re.sub(r"(?<=\w)-\s+(?=[a-z])", "-", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def verify_probast_evidence(
    evidence: Sequence[ProbastEvidenceReference | Mapping[str, Any]],
    source_chunks: Sequence[Any],
) -> bool:
    if not evidence:
        return False
    lookup: dict[str, dict[str, Any]] = {}
    for chunk in source_chunks:
        row = _as_dict(chunk)
        lookup[row["chunk_id"]] = row
    for reference in evidence:
        ref = _as_dict(reference)

        chunk_id = ref.get("chunk_id")

        if not isinstance(chunk_id, str):
            return False

        chunk = lookup.get(chunk_id)

        if chunk is None or ref.get("page") != chunk.get("page"):
            return False

        quote = ref.get("quote")
        text = chunk.get("text")

        if not isinstance(quote, str) or not isinstance(text, str):
            return False

        if normalise_evidence_text(quote) not in normalise_evidence_text(text):
            return False
    return True


def verify_probast_finding(
    finding: ProbastQuestionFinding,
    source_chunks: Sequence[Any],
) -> ProbastQuestionFinding:
    data = finding.model_dump()
    if data["assessment_state"] == "not_assessed" or data["response"] in {
        "no_information", "not_applicable"
    }:
        data["evidence_verified"] = bool(data["evidence"]) and verify_probast_evidence(
            data["evidence"], source_chunks
        )
        return ProbastQuestionFinding.model_validate(data)

    verified = verify_probast_evidence(data["evidence"], source_chunks)
    data["evidence_verified"] = verified
    if not verified:
        data["assessment_state"] = "not_assessed"
        data["response"] = None
        data["not_assessed_reason"] = "Evidence quotation could not be verified against the cited source chunk and page."
        data["flags"].append("evidence_verification_failed")
        data["explanation"] = (
            "The proposed response was withheld because its supporting quotation "
            "could not be verified against the source document."
        )
    return ProbastQuestionFinding.model_validate(data)
