"""Tests for the LLM provider client."""

import httpx
import pytest
from app import llm
from app.llm import LLMProviderError, generate_item_response


@pytest.mark.asyncio
async def test_generate_item_response_success(monkeypatch):
    """A successful provider response returns its message content."""

    monkeypatch.setattr(llm.settings, "llm_api_key", "test-key")

    async def mock_post(self, url, **kwargs):
        assert url.endswith("/chat/completions")
        assert kwargs["json"]["model"] == llm.settings.llm_model
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"

        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={"choices": [{"message": {"content": '{"element_findings": []}'}}]},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    result = await generate_item_response("Test prompt")

    assert result == '{"element_findings": []}'


@pytest.mark.asyncio
async def test_generate_item_response_missing_key(monkeypatch):
    """Missing API credentials fail before making a request."""

    monkeypatch.setattr(llm.settings, "llm_api_key", "")

    with pytest.raises(LLMProviderError, match="LLM_API_KEY"):
        await generate_item_response("Test prompt")
