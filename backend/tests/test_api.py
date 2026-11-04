"""API tests for ModelAudit document upload."""

import pymupdf
import pytest
from app.main import app, documents, retrievers
from fastapi.testclient import TestClient


class FakeEmbeddingModel:
    """Provide deterministic embeddings for API tests."""

    def encode(
        self,
        sentences,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ):
        """Return simple two-dimensional embeddings."""

        import numpy as np

        return np.asarray(
            [[1.0, 0.0] for _ in sentences],
            dtype=np.float32,
        )


@pytest.fixture
def client():
    """Provide a test client and isolate in-memory registries."""

    documents.clear()
    retrievers.clear()

    with TestClient(app) as test_client:
        yield test_client

    documents.clear()
    retrievers.clear()


def create_test_pdf() -> bytes:
    """Create a small text-based PDF for upload tests."""

    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text(
        (72, 72),
        "Clinical prediction model study. This paper evaluates model performance.",
    )

    content = pdf.tobytes()
    pdf.close()

    return content


def test_root_endpoint(client):
    """Return basic API information."""

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "Welcome to ModelAudit"


def test_health_endpoint(client):
    """Return a healthy API status."""

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_upload_valid_pdf(client):
    """Accept and process a valid research PDF."""

    content = create_test_pdf()

    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "research_paper.pdf",
                content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["filename"] == "research_paper.pdf"
    assert result["page_count"] == 1
    assert result["chunk_count"] >= 1
    assert len(result["document_id"]) == 64
    assert "Clinical prediction model study" in result["extracted_text"]

    assert result["document_id"] in documents


def test_upload_invalid_file(client):
    """Reject a file that is not a valid PDF."""

    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "invalid.pdf",
                b"This is not a PDF",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert "not a valid PDF" in response.json()["detail"]


def test_upload_oversized_file(client):
    """Reject uploads exceeding the configured 15 MB limit."""

    oversized_content = b"%PDF-" + b"x" * (15 * 1024 * 1024)

    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "oversized.pdf",
                oversized_content,
                "application/pdf",
            )
        },
    )

    assert response.status_code == 413
    assert "15 MB" in response.json()["detail"]


def test_failed_upload_is_not_registered(client):
    """Ensure failed uploads are not added to the document registry."""

    response = client.post(
        "/documents/upload",
        files={
            "file": (
                "invalid.pdf",
                b"invalid content",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert len(documents) == 0


def test_retrieve_document_evidence(client, monkeypatch):
    """Retrieve evidence from an uploaded document."""

    monkeypatch.setattr(
        "app.main.get_embedding_model",
        lambda: FakeEmbeddingModel(),
    )

    upload_response = client.post(
        "/documents/upload",
        files={
            "file": (
                "research_paper.pdf",
                create_test_pdf(),
                "application/pdf",
            )
        },
    )

    document_id = upload_response.json()["document_id"]

    response = client.post(
        f"/documents/{document_id}/retrieve",
        json={
            "query": "clinical prediction model",
            "top_k": 3,
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["document_id"] == document_id
    assert result["retrieval_method"] == "hybrid_bm25_semantic_rrf"
    assert result["result_count"] >= 1
    assert result["results"][0]["chunk_id"] == "p1-c1"
    assert result["results"][0]["page"] == 1


def test_retrieve_unknown_document(client):
    """Reject retrieval requests for unknown documents."""

    response = client.post(
        "/documents/unknown-document/retrieve",
        json={"query": "clinical prediction model"},
    )

    assert response.status_code == 404


def test_retrieve_rejects_whitespace_query(client):
    """Reject queries containing only whitespace."""

    response = client.post(
        "/documents/unknown-document/retrieve",
        json={"query": "   "},
    )

    assert response.status_code == 422
