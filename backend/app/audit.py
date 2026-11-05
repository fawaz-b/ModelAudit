
"""Orchestration of the TRIPOD+AI reporting assessment."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from time import perf_counter
from typing import Any, Protocol

from app.framework import load_framework
from app.judge import assess_framework
from app.llm import (
    LLMProviderError,
    LLMQuotaError,
    LLMRateLimitError,
    LLMResponseError,
    build_item_prompt,
    generate_item_response,
    parse_item_response,
)
from app.schemas import (
    FrameworkAssessment,
    RetrievedPassage,
    StudyContext,
)

logger = logging.getLogger(__name__)

RETRIEVAL_TOP_K = 4
MAX_PASSAGES_PER_ITEM = 4
RRF_CONSTANT = 60

class AuditRetriever(Protocol):
    """Structural interface required by the audit pipeline."""

    bm25: Any

    def retrieve(
        self,
        query: str,
        top_k: int,
    ) -> Sequence[Any]:
        """Retrieve ranked document chunks."""
        ...


def retrieve_item_passages(
    item: dict[str, Any],
    retriever: AuditRetriever,
) -> list[RetrievedPassage]:
    """Retrieve and deduplicate the highest-ranked evidence passages."""

    queries = item.get("retrieval_queries") or [item["assessment_prompt"]]

    fused_scores: dict[str, float] = {}
    chunks: dict[str, Any] = {}

    for query in queries:
        results = retriever.retrieve(
            query=query,
            top_k=RETRIEVAL_TOP_K,
        )

        for result in results:
            chunk = result.chunk
            chunk_id = chunk.chunk_id

            chunks[chunk_id] = chunk
            fused_scores[chunk_id] = (
                fused_scores.get(chunk_id, 0.0)
                + 1.0 / (RRF_CONSTANT + result.rank)
            )

    ranked = sorted(
        fused_scores.items(),
        key=lambda entry: (-entry[1], entry[0]),
    )[:MAX_PASSAGES_PER_ITEM]

    return [
        RetrievedPassage(
            chunk_id=chunk_id,
            page=chunks[chunk_id].page,
            section_guess=chunks[chunk_id].section_guess,
            text=chunks[chunk_id].text,
            score=score,
            rank=rank,
        )
        for rank, (chunk_id, score) in enumerate(ranked, start=1)
    ]


def build_document_passages(
    retriever: AuditRetriever,
) -> list[RetrievedPassage]:
    """Build the complete source-chunk collection for evidence verification."""

    return [
        RetrievedPassage(
            chunk_id=chunk.chunk_id,
            page=chunk.page,
            section_guess=chunk.section_guess,
            text=chunk.text,
            score=0.0,
            rank=0,
        )
        for chunk in retriever.bm25.chunks
    ]


async def assess_single_item(
    item: dict[str, Any],
    passages: list[RetrievedPassage],
    study_context: StudyContext,
    global_rules: list[str],
) -> dict[str, Any]:
    """Call the LLM and validate its element-level findings."""

    prompt = build_item_prompt(
        item=item,
        passages=passages,
        study_type=study_context.study_type or "unknown",
        global_rules=global_rules,
    )

    response = await generate_item_response(prompt)
    findings = parse_item_response(response)

    expected_keys = {element["key"] for element in item["elements"]}
    unexpected_keys = set(findings) - expected_keys

    if unexpected_keys:
        raise LLMResponseError(
            f"LLM returned unexpected element keys: {sorted(unexpected_keys)}"
        )

    return findings


async def run_tripod_audit(
    document_id: str,
    retriever: AuditRetriever,
    study_context: StudyContext | None = None,
) -> FrameworkAssessment:
    """Run the selected TRIPOD+AI assessment for one uploaded document."""

    audit_started = perf_counter()

    framework = load_framework()
    context = study_context or StudyContext()
    global_rules = framework.get("global_rules", [])

    findings_by_item: dict[str, dict[str, Any]] = {}
    item_errors: dict[str, str] = {}
    not_assessed_items: dict[str, str] = {}
    stop_reason: str | None = None

    # Construct once: evidence verification checks quotes against the
    # complete set of document chunks, not only the retrieved excerpts.
    document_passages = build_document_passages(retriever)

    logger.info(
        "Starting TRIPOD+AI assessment: document=%s items=%d chunks=%d",
        document_id,
        len(framework["items"]),
        len(document_passages),
    )

    # Keep calls sequential to reduce pressure on the provider's
    # token-per-minute quota.
    for item_index, item in enumerate(framework["items"]):
        item_id = item["id"]

        if stop_reason:
            not_assessed_items[item_id] = stop_reason
            continue
        item_started = perf_counter()

        try:
            passages = retrieve_item_passages(
                item=item,
                retriever=retriever,
            )

            if not passages:
                logger.warning(
                    "No passages retrieved: item=%s document=%s",
                    item_id,
                    document_id,
                )
                findings_by_item[item_id] = {}
                item_errors[item_id] = "no_retrieved_passages"
                continue

            prompt_char_count = sum(len(passage.text) for passage in passages)

            findings = await assess_single_item(
                item=item,
                passages=passages,
                study_context=context,
                global_rules=global_rules,
            )

            findings_by_item[item_id] = findings

            logger.info(
                "Assessment item completed: item=%s passages=%d "
                "source_chars=%d findings=%d elapsed=%.2fs",
                item_id,
                len(passages),
                prompt_char_count,
                len(findings),
                perf_counter() - item_started,
            )

        except (LLMQuotaError, LLMRateLimitError) as exc:
            logger.error(
                "Stopping assessment after provider limit: item=%s error=%s",
                item_id,
                type(exc).__name__,
            )
            item_errors[item_id] = type(exc).__name__
            stop_reason = type(exc).__name__
            not_assessed_items[item_id] = stop_reason
            for remaining_item in framework["items"][item_index + 1:]:
                not_assessed_items[remaining_item["id"]] = stop_reason
            break

        except (LLMProviderError, LLMResponseError) as exc:
            logger.exception(
                "Assessment item failed: item=%s error=%s",
                item_id,
                type(exc).__name__,
            )
            findings_by_item[item_id] = {}
            item_errors[item_id] = type(exc).__name__

        except Exception as exc:
            logger.exception(
                "Unexpected assessment failure: item=%s",
                item_id,
            )
            findings_by_item[item_id] = {}
            item_errors[item_id] = type(exc).__name__

    assessment = assess_framework(
        framework=framework,
        document_id=document_id,
        study_context=context,
        findings_by_item=findings_by_item,
        passages=document_passages,
        not_assessed_items=not_assessed_items,
    )

    if item_errors:
        updated_items = []

        for item_assessment in assessment.items:
            error = item_errors.get(item_assessment.item_id)

            if error:
                updated_items.append(
                    item_assessment.model_copy(
                        update={
                            "flags": [
                                *item_assessment.flags,
                                f"assessment_error:{error}",
                            ]
                        }
                    )
                )
            else:
                updated_items.append(item_assessment)

        assessment = assessment.model_copy(
            update={
                "items": updated_items,
                "assessment_status": "requires_review",
            }
        )

    logger.info(
        "TRIPOD+AI assessment finished: document=%s status=%s "
        "successful_items=%d failed_items=%d not_assessed_items=%d "
        "stop_reason=%s elapsed=%.2fs",
        document_id,
        assessment.assessment_status,
        sum(
        1
        for item_id in findings_by_item
        if item_id not in item_errors
        ),
        len(item_errors),
        len(not_assessed_items),
        stop_reason,
        perf_counter() - audit_started,
    )

    return assessment
