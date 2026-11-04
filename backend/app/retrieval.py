"""Lexical, semantic, and hybrid retrieval of research paper evidence."""

import re
from dataclasses import dataclass
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from app.ingest import DocumentChunk

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class RetrievalResult:
    """A retrieved document chunk with its relevance score and rank."""

    chunk: DocumentChunk
    score: float
    rank: int


def tokenize(text: str) -> list[str]:
    """Convert text into lowercase alphanumeric tokens."""

    return re.findall(r"[a-z0-9]+", text.lower())


class BM25Retriever:
    """Retrieve relevant document chunks using BM25 ranking."""

    def __init__(self, chunks: list[DocumentChunk]):
        """Build a BM25 index from the supplied document chunks."""

        if not chunks:
            raise ValueError("Cannot build a retrieval index from empty chunks.")

        self.chunks = chunks
        self.tokenized_corpus = [tokenize(chunk.text) for chunk in chunks]

        if not any(self.tokenized_corpus):
            raise ValueError("Document chunks contain no searchable text.")

        self.index = BM25Okapi(self.tokenized_corpus)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        hints: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Return the highest-ranking chunks relevant to a query."""

        if not query.strip():
            raise ValueError("Retrieval query cannot be empty.")

        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        search_text = " ".join([query, *(hints or [])])
        tokenized_query = tokenize(search_text)

        if not tokenized_query:
            raise ValueError("Retrieval query contains no searchable terms.")

        scores = self.index.get_scores(tokenized_query)

        ranked_indices = sorted(
            range(len(scores)),
            key=lambda index: (-scores[index], index),
        )

        results = []

        for index in ranked_indices:
            score = float(scores[index])

            if score <= 0:
                continue

            results.append(
                RetrievalResult(
                    chunk=self.chunks[index],
                    score=score,
                    rank=len(results) + 1,
                )
            )

            if len(results) == top_k:
                break

        return results


class SemanticRetriever:
    """Retrieve document chunks using embedding-based similarity."""

    def __init__(
        self,
        chunks: list[DocumentChunk],
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        model: Any | None = None,
    ):
        """Encode document chunks and prepare a semantic search index."""

        if not chunks:
            raise ValueError("Cannot build a retrieval index from empty chunks.")

        if not any(chunk.text.strip() for chunk in chunks):
            raise ValueError("Document chunks contain no searchable text.")

        self.chunks = chunks

        # Load the embedding model only when semantic retrieval is requested.
        self.model = model or SentenceTransformer(model_name, device="cpu")

        self.embeddings = self.model.encode(
            [chunk.text for chunk in chunks],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        self.embeddings = np.asarray(self.embeddings, dtype=np.float32)

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        hints: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Return chunks ranked by cosine similarity to the query."""

        if not query.strip():
            raise ValueError("Retrieval query cannot be empty.")

        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        search_text = " ".join([query, *(hints or [])])

        query_embedding = self.model.encode(
            [search_text],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]

        query_embedding = np.asarray(query_embedding, dtype=np.float32)

        # Embeddings are normalized, so their dot product is cosine similarity.
        scores = self.embeddings @ query_embedding

        ranked_indices = np.argsort(-scores, kind="stable")[:top_k]

        return [
            RetrievalResult(
                chunk=self.chunks[int(index)],
                score=float(scores[index]),
                rank=rank,
            )
            for rank, index in enumerate(ranked_indices, start=1)
        ]


class HybridRetriever:
    """Combine BM25 and semantic rankings using Reciprocal Rank Fusion."""

    def __init__(
        self,
        chunks: list[DocumentChunk],
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        model: Any | None = None,
        rrf_k: int = 60,
    ):
        """Build lexical and semantic indexes for the same document."""

        if rrf_k < 1:
            raise ValueError("rrf_k must be at least 1.")

        self.bm25 = BM25Retriever(chunks)
        self.semantic = SemanticRetriever(
            chunks=chunks,
            model_name=model_name,
            model=model,
        )
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        hints: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Fuse lexical and semantic rankings into one result list."""

        if not query.strip():
            raise ValueError("Retrieval query cannot be empty.")

        if top_k < 1:
            raise ValueError("top_k must be at least 1.")

        # Retrieve a wider candidate pool before combining rankings.
        candidate_k = min(len(self.bm25.chunks), max(top_k * 3, top_k))

        lexical_results = self.bm25.retrieve(
            query=query,
            top_k=candidate_k,
            hints=hints,
        )

        semantic_results = self.semantic.retrieve(
            query=query,
            top_k=candidate_k,
            hints=hints,
        )

        fused_scores: dict[str, float] = {}
        chunks_by_id: dict[str, DocumentChunk] = {}

        for results in (lexical_results, semantic_results):
            for result in results:
                chunk_id = result.chunk.chunk_id

                chunks_by_id[chunk_id] = result.chunk

                fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (
                    self.rrf_k + result.rank
                )

        ranked_chunks = sorted(
            fused_scores.items(),
            key=lambda item: (-item[1], item[0]),
        )[:top_k]

        return [
            RetrievalResult(
                chunk=chunks_by_id[chunk_id],
                score=score,
                rank=rank,
            )
            for rank, (chunk_id, score) in enumerate(
                ranked_chunks,
                start=1,
            )
        ]
