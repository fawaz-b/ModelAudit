
"""Orchestration of the PROBAST+AI evaluation-branch subset."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from time import perf_counter
from typing import Any, Protocol

from app.probast_framework import load_probast_framework
from app.probast_judge import build_probast_assessment
from app.probast_llm import (
    LLMResponseError,
    build_probast_question_prompt,
    parse_probast_question_response,
)
from app.probast_schemas import (
    EvaluationComponent,
    ProbastAssessment,
    ProbastQuestionFinding,
    ProbastStudyContext,
)

logger = logging.getLogger(__name__)

TOP_K_PER_QUERY = 4
MAX_PASSAGES_PER_QUESTION = 6
RRF_CONSTANT = 60


class ProbastRetriever(Protocol):
    bm25: Any

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        hints: list[str] | None = None,
    ) -> Sequence[Any]:
        ...


def _passage_dict(
    chunk: Any,
    score: float = 0.0,
    rank: int = 0,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk.chunk_id,
        "page": chunk.page,
        "section_guess": getattr(chunk, "section_guess", None),
        "text": chunk.text,
        "score": score,
        "rank": rank,
    }


def retrieve_probast_passages(
    question: dict[str, Any],
    retriever: ProbastRetriever,
) -> list[dict[str, Any]]:
    queries = question.get("modelaudit", {}).get(
        "retrieval_queries",
        [],
    )

    if not queries:
        queries = [question["official_wording"]]

    scores: dict[str, float] = {}
    chunks: dict[str, Any] = {}

    for query in queries:
        for result in retriever.retrieve(
            query=query,
            top_k=TOP_K_PER_QUERY,
        ):
            chunk = result.chunk
            chunks[chunk.chunk_id] = chunk

            scores[chunk.chunk_id] = (
                scores.get(chunk.chunk_id, 0.0)
                + 1.0 / (RRF_CONSTANT + result.rank)
            )

    ranked = sorted(
        scores.items(),
        key=lambda row: (-row[1], row[0]),
    )[:MAX_PASSAGES_PER_QUESTION]

    return [
        _passage_dict(chunks[chunk_id], score, rank)
        for rank, (chunk_id, score) in enumerate(ranked, start=1)
    ]


def build_source_chunks(
    retriever: ProbastRetriever,
) -> list[dict[str, Any]]:
    return [
        _passage_dict(chunk)
        for chunk in retriever.bm25.chunks
    ]


def _components_for_question(
    question_id: str,
    context: ProbastStudyContext,
) -> list[EvaluationComponent]:
    components: list[EvaluationComponent] = [
        component
        for component in context.evaluation_components
        if component != "unspecified"
    ]

    if not components:
        return ["unspecified"]

    # PE-4.1 and analysis questions are component-sensitive. The other selected
    # questions are still assessed separately for each reported component so
    # component-specific datasets cannot be silently merged.
    return components


def _pe45_applicability(
    component: EvaluationComponent,
    context: ProbastStudyContext,
) -> bool | None:
    if component in {"apparent", "external"}:
        return False

    if component == "internal":
        if context.has_training_test_split is True:
            return True

        if context.has_training_test_split is False:
            return False

        if context.validation_method in {
            "bootstrap",
            "cross_validation",
            "other_resampling",
        }:
            return False

        if context.validation_method == "training_test_split":
            return True

        return None

    return None


async def run_probast_audit(
    document_id: str,
    retriever: ProbastRetriever,
    context: ProbastStudyContext | None = None,
    model_identifier: str | None = None,
) -> ProbastAssessment:
    # Import the existing provider client only when an audit is actually run.
    # This keeps the framework/rules modules independently testable.
    from app.llm import (
        LLMProviderError,
        generate_item_response,
    )
    from app.llm import (
        LLMResponseError as ProviderLLMResponseError,
    )

    started = perf_counter()
    framework = load_probast_framework()
    study_context = context or ProbastStudyContext()
    source_chunks = build_source_chunks(retriever)

    findings: list[ProbastQuestionFinding] = []
    stop_reason: str | None = None

    components = _components_for_question("all", study_context)

    for question in framework["questions"]:
        qid = question["id"]

        for component in components:
            if stop_reason:
                findings.append(
                    ProbastQuestionFinding(
                        question_id=qid,
                        evaluation_component=component,
                        assessment_state="not_assessed",
                        response=None,
                        explanation=(
                            "Assessment was not run because processing "
                            f"stopped: {stop_reason}."
                        ),
                        not_assessed_reason=stop_reason,
                        flags=["assessment_interrupted"],
                    )
                )
                continue

            if qid == "PE-4.5":
                applicable = _pe45_applicability(
                    component,
                    study_context,
                )

                if applicable is False:
                    findings.append(
                        ProbastQuestionFinding(
                            question_id=qid,
                            evaluation_component=component,
                            response="not_applicable",
                            explanation=(
                                "PE-4.5 is not applicable to this evaluation "
                                "component/design under the documented "
                                "conditional rule."
                            ),
                            flags=["conditional_not_applicable"],
                        )
                    )
                    continue

                if applicable is None:
                    findings.append(
                        ProbastQuestionFinding(
                            question_id=qid,
                            evaluation_component=component,
                            response="no_information",
                            explanation=(
                                "The evaluation design does not establish "
                                "whether an internal training/test split "
                                "was used. Not applicable was not inferred."
                            ),
                            flags=["conditional_design_unresolved"],
                        )
                    )
                    continue

            try:
                passages = retrieve_probast_passages(
                    question,
                    retriever,
                )

                if not passages:
                    findings.append(
                        ProbastQuestionFinding(
                            question_id=qid,
                            evaluation_component=component,
                            response="no_information",
                            explanation=(
                                "No relevant source passages were retrieved; "
                                "this is not proof that the paper lacks "
                                "the information."
                            ),
                            flags=["no_retrieved_passages"],
                        )
                    )
                    continue

                prompt = build_probast_question_prompt(
                    question=question,
                    passages=passages,
                    context=study_context.model_dump(),
                    evaluation_component=component,
                    global_rules=framework.get(
                        "modelaudit_global_rules",
                        [],
                    ),
                )

                raw = await generate_item_response(
                    prompt,
                    system_instruction=(
                        "You are a careful clinical prediction model "
                        "risk-of-bias assessment assistant applying the "
                        "PROBAST+AI evaluation branch. Follow the requested "
                        "JSON schema exactly."
                    ),
                )

                parsed = parse_probast_question_response(raw)

                if (
                    parsed.question_id != qid
                    or parsed.evaluation_component != component
                ):
                    raise LLMResponseError(
                        "LLM returned mismatched question/component "
                        f"for {qid}/{component}."
                    )

                findings.append(parsed)

            except (
                LLMProviderError,
                LLMResponseError,
                ProviderLLMResponseError,
            ) as exc:
                logger.exception(
                    "PROBAST assessment failed for %s/%s",
                    qid,
                    component,
                )

                findings.append(
                    ProbastQuestionFinding(
                        question_id=qid,
                        evaluation_component=component,
                        assessment_state="not_assessed",
                        response=None,
                        explanation=(
                            "Assessment could not be completed: "
                            f"{type(exc).__name__}."
                        ),
                        not_assessed_reason=type(exc).__name__,
                        flags=["assessment_error"],
                    )
                )

                if isinstance(exc, LLMProviderError):
                    stop_reason = type(exc).__name__

    result = build_probast_assessment(
        framework=framework,
        document_id=document_id,
        context=study_context,
        findings=findings,
        source_chunks=source_chunks,
        model_identifier=model_identifier,
    )

    logger.info(
        "PROBAST+AI subset finished: document=%s findings=%d "
        "status=%s elapsed=%.2fs",
        document_id,
        len(result.findings),
        result.assessment_status,
        perf_counter() - started,
    )

    return result
