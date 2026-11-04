"""Tests for BM25 document retrieval."""

import pytest
from app.ingest import DocumentChunk
from app.retrieval import BM25Retriever, tokenize


@pytest.fixture
def sample_chunks():
    """Provide representative clinical prediction paper passages."""

    return [
        DocumentChunk(
            chunk_id="p1-c1",
            page=1,
            section_guess="Abstract",
            text=(
                "This study developed a clinical prediction model "
                "for cardiovascular disease using patient records."
            ),
            char_start=0,
            char_end=120,
        ),
        DocumentChunk(
            chunk_id="p3-c1",
            page=3,
            section_guess="Methods",
            text=(
                "Predictors included age, sex, blood pressure, "
                "smoking status and diabetes. Blood pressure "
                "was measured using a calibrated sphygmomanometer."
            ),
            char_start=0,
            char_end=150,
        ),
        DocumentChunk(
            chunk_id="p5-c1",
            page=5,
            section_guess="Results",
            text=(
                "The final model demonstrated good discrimination "
                "with an area under the receiver operating "
                "characteristic curve of 0.82."
            ),
            char_start=0,
            char_end=130,
        ),
        DocumentChunk(
            chunk_id="p6-c1",
            page=6,
            section_guess="Discussion",
            text=(
                "The study was conducted in a tertiary hospital "
                "among adults attending outpatient clinics."
            ),
            char_start=0,
            char_end=100,
        ),
    ]


def test_tokenize_text():
    """Tokenization should lowercase and extract alphanumeric terms."""

    assert tokenize("Blood Pressure, Age 45!") == [
        "blood",
        "pressure",
        "age",
        "45",
    ]


def test_build_retrieval_index(sample_chunks):
    """Build an index from document chunks."""

    retriever = BM25Retriever(sample_chunks)

    assert len(retriever.chunks) == 4
    assert retriever.index is not None


def test_retrieve_relevant_predictor_passage(sample_chunks):
    """Rank the predictor measurement passage highly."""

    retriever = BM25Retriever(sample_chunks)

    results = retriever.retrieve(
        "How were predictors measured?",
        hints=["blood pressure", "sphygmomanometer"],
        top_k=3,
    )

    assert len(results) >= 1
    assert results[0].chunk.chunk_id == "p3-c1"
    assert results[0].chunk.page == 3


def test_retrieve_returns_ranked_results(sample_chunks):
    """Return results in descending relevance order."""

    retriever = BM25Retriever(sample_chunks)

    results = retriever.retrieve(
        "clinical prediction model cardiovascular disease",
        top_k=3,
    )

    assert len(results) <= 3
    assert [result.rank for result in results] == list(range(1, len(results) + 1))

    scores = [result.score for result in results]

    assert scores == sorted(scores, reverse=True)


def test_retrieve_respects_top_k(sample_chunks):
    """Limit the number of returned passages."""

    retriever = BM25Retriever(sample_chunks)

    results = retriever.retrieve(
        "clinical prediction model",
        top_k=2,
    )

    assert len(results) <= 2


def test_retrieve_returns_no_unrelated_passages(sample_chunks):
    """Return no results when the query has no matching terms."""

    retriever = BM25Retriever(sample_chunks)

    results = retriever.retrieve(
        "quantum astronomy galaxies",
    )

    assert results == []


def test_reject_empty_document_chunks():
    """Reject an empty document collection."""

    with pytest.raises(ValueError, match="empty chunks"):
        BM25Retriever([])


def test_reject_chunks_without_searchable_text():
    """Reject chunks containing no searchable terms."""

    chunk = DocumentChunk(
        chunk_id="p1-c1",
        page=1,
        section_guess=None,
        text="!!! ...",
        char_start=0,
        char_end=7,
    )

    with pytest.raises(ValueError, match="no searchable text"):
        BM25Retriever([chunk])


def test_reject_empty_query(sample_chunks):
    """Reject an empty retrieval query."""

    retriever = BM25Retriever(sample_chunks)

    with pytest.raises(ValueError, match="cannot be empty"):
        retriever.retrieve("   ")


def test_reject_invalid_top_k(sample_chunks):
    """Reject invalid result limits."""

    retriever = BM25Retriever(sample_chunks)

    with pytest.raises(ValueError, match="at least 1"):
        retriever.retrieve("predictors", top_k=0)


class FakeEmbeddingModel:
    """Provide deterministic embeddings for retrieval unit tests."""

    def encode(
        self,
        sentences,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    ):
        """Return simple vectors based on passage content."""

        import numpy as np

        embeddings = []

        for sentence in sentences:
            text = sentence.lower()

            if "blood pressure" in text or "hypertension" in text:
                embeddings.append([1.0, 0.0])
            else:
                embeddings.append([0.0, 1.0])

        return np.asarray(embeddings, dtype=np.float32)


def test_semantic_retrieval_finds_similar_meaning(sample_chunks):
    """Retrieve a blood pressure passage for a hypertension query."""

    from app.retrieval import SemanticRetriever

    retriever = SemanticRetriever(
        chunks=sample_chunks,
        model=FakeEmbeddingModel(),
    )

    results = retriever.retrieve(
        "How was hypertension measured?",
        top_k=2,
    )

    assert results[0].chunk.chunk_id == "p3-c1"
    assert results[0].rank == 1


def test_semantic_retrieval_respects_top_k(sample_chunks):
    """Limit semantic results to the requested number."""

    from app.retrieval import SemanticRetriever

    retriever = SemanticRetriever(
        chunks=sample_chunks,
        model=FakeEmbeddingModel(),
    )

    results = retriever.retrieve(
        "How was hypertension measured?",
        top_k=2,
    )

    assert len(results) == 2


def test_hybrid_retrieval_combines_both_methods(sample_chunks):
    """Build and query a combined lexical and semantic index."""

    from app.retrieval import HybridRetriever

    retriever = HybridRetriever(
        chunks=sample_chunks,
        model=FakeEmbeddingModel(),
    )

    results = retriever.retrieve(
        "How was blood pressure measured?",
        top_k=3,
    )

    assert len(results) == 3
    assert results[0].chunk.chunk_id == "p3-c1"


def test_hybrid_retrieval_returns_unique_chunks(sample_chunks):
    """Do not duplicate chunks when combining rankings."""

    from app.retrieval import HybridRetriever

    retriever = HybridRetriever(
        chunks=sample_chunks,
        model=FakeEmbeddingModel(),
    )

    results = retriever.retrieve(
        "clinical prediction model",
        top_k=4,
    )

    chunk_ids = [result.chunk.chunk_id for result in results]

    assert len(chunk_ids) == len(set(chunk_ids))


def test_hybrid_retrieval_rejects_invalid_rrf_k(sample_chunks):
    """Reject invalid Reciprocal Rank Fusion constants."""

    from app.retrieval import HybridRetriever

    with pytest.raises(ValueError, match="rrf_k"):
        HybridRetriever(
            chunks=sample_chunks,
            model=FakeEmbeddingModel(),
            rrf_k=0,
        )
