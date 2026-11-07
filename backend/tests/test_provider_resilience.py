from types import SimpleNamespace
from typing import Any

import pytest
from app import audit, llm
from app.schemas import RetrievedPassage, StudyContext


def test_provider_registry_selects_openai_compatible_adapter(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_provider", "groq")

    adapter = llm.get_provider_adapter()

    assert isinstance(adapter, llm.OpenAICompatibleAdapter)
    assert adapter.provider_name == "groq"


def test_unknown_provider_fails_with_configuration_error(monkeypatch):
    monkeypatch.setattr(llm.settings, "llm_provider", "unknown-provider")

    with pytest.raises(
        llm.LLMConfigurationError,
        match="Unsupported LLM_PROVIDER",
    ):
        llm.get_provider_adapter()


@pytest.mark.asyncio
async def test_quota_exhaustion_stops_audit_and_marks_remaining_items(
    monkeypatch,
):
    framework = {
        "framework": "TRIPOD+AI",
        "framework_version": "2024",
        "global_rules": [],
        "items": [
            {
                "id": "item-1",
                "elements": [{"key": "e1", "required": True}],
                "assessment_prompt": "Assess item 1",
            },
            {
                "id": "item-2",
                "elements": [{"key": "e2", "required": True}],
                "assessment_prompt": "Assess item 2",
            },
            {
                "id": "item-3",
                "elements": [{"key": "e3", "required": True}],
                "assessment_prompt": "Assess item 3",
            },
        ],
    }

    calls = {"count": 0}

    class FakeRetriever:
        """Minimal test implementation of the audit retriever interface."""

        bm25 = SimpleNamespace(chunks=[])

        def retrieve(
            self,
            query: str,
            top_k: int,
        ) -> list[Any]:
            return []

    monkeypatch.setattr(
        audit,
        "load_framework",
        lambda: framework,
    )

    monkeypatch.setattr(
        audit,
        "retrieve_item_passages",
        lambda item, retriever: [
            RetrievedPassage(
                chunk_id="chunk-1",
                page=1,
                section_guess=None,
                text="Source text",
                score=1.0,
                rank=1,
            )
        ],
    )

    async def quota_failure(*args, **kwargs):
        calls["count"] += 1
        raise llm.LLMQuotaError("daily quota exhausted")

    monkeypatch.setattr(
        audit,
        "assess_single_item",
        quota_failure,
    )

    result = await audit.run_tripod_audit(
        document_id="doc-1",
        retriever=FakeRetriever(),
        study_context=StudyContext(),
    )

    assert calls["count"] == 1
    assert result.assessment_status == "requires_review"

    assert [item.category for item in result.items] == [
        "not_assessed",
        "not_assessed",
        "not_assessed",
    ]

    assert all(
        any(flag.startswith("assessment_not_run:") for flag in item.flags)
        for item in result.items
    )


@pytest.mark.asyncio
async def test_quota_exhaustion_preserves_completed_findings(monkeypatch):
    framework = {
        "framework": "TRIPOD+AI",
        "framework_version": "2024",
        "global_rules": [],
        "items": [
            {
                "id": "item-1",
                "elements": [{"key": "e1", "required": True}],
                "assessment_prompt": "Assess item 1",
            },
            {
                "id": "item-2",
                "elements": [{"key": "e2", "required": True}],
                "assessment_prompt": "Assess item 2",
            },
            {
                "id": "item-3",
                "elements": [{"key": "e3", "required": True}],
                "assessment_prompt": "Assess item 3",
            },
        ],
    }

    class FakeRetriever:
        """Minimal test implementation of the audit retriever interface."""

        bm25 = SimpleNamespace(
            chunks=[
                SimpleNamespace(
                    chunk_id="chunk-1",
                    page=1,
                    section_guess=None,
                    text="Source text",
                )
            ]
        )

        def retrieve(
            self,
            query: str,
            top_k: int,
        ) -> list[Any]:
            return []

    calls = {"count": 0}

    monkeypatch.setattr(
        audit,
        "load_framework",
        lambda: framework,
    )

    monkeypatch.setattr(
        audit,
        "retrieve_item_passages",
        lambda item, retriever: [
            RetrievedPassage(
                chunk_id="chunk-1",
                page=1,
                section_guess=None,
                text="Source text",
                score=1.0,
                rank=1,
            )
        ],
    )

    async def assess_with_quota_failure(*args, **kwargs):
        calls["count"] += 1

        if calls["count"] == 1:
            return {
                "e1": {
                    "element_key": "e1",
                    "status": "reported",
                    "explanation": "The paper reports this element.",
                    "evidence": [
                        {
                            "quote": "Source text",
                            "page": 1,
                            "chunk_id": "chunk-1",
                        }
                    ],
                }
            }

        raise llm.LLMQuotaError("daily quota exhausted")

    monkeypatch.setattr(
        audit,
        "assess_single_item",
        assess_with_quota_failure,
    )

    result = await audit.run_tripod_audit(
        document_id="doc-1",
        retriever=FakeRetriever(),
        study_context=StudyContext(),
    )

    assert calls["count"] == 2
    assert result.assessment_status == "requires_review"

    first_item = result.items[0]
    second_item = result.items[1]
    third_item = result.items[2]

    # Completed findings must survive quota exhaustion.
    first_finding = first_item.element_findings[0]

    assert first_finding.element_key == "e1"
    assert first_finding.status == "reported"
    assert first_finding.evidence_verified is True
    assert first_finding.explanation == ("The paper reports this element.")

    # The item where quota exhaustion occurred was not assessed.
    assert second_item.category == "not_assessed"
    assert any(flag.startswith("assessment_error:") for flag in second_item.flags)

    # The subsequent item was never attempted.
    assert third_item.category == "not_assessed"
    assert any(flag.startswith("assessment_not_run:") for flag in third_item.flags)
