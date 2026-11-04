"""Main entry point for the ModelAudit API."""

from dataclasses import asdict
from functools import lru_cache
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.ingest import (
    MAX_FILE_SIZE_MB,
    PDFIngestionError,
    ProcessedDocument,
    process_pdf,
)
from app.retrieval import DEFAULT_EMBEDDING_MODEL, HybridRetriever
from app.schemas import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievedPassage,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "An evidence-linked appraisal assistant for clinical prediction model papers."
    ),
)

# Temporary in-memory document registry for the single-paper MVP.
documents: dict[str, ProcessedDocument] = {}

# Retrieval indexes are created lazily, one per uploaded document.
retrievers: dict[str, HybridRetriever] = {}


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load and cache one CPU embedding model instance."""

    return SentenceTransformer(
        DEFAULT_EMBEDDING_MODEL,
        device="cpu",
    )


@app.get("/")
async def root():
    """Return basic API information."""

    return {
        "message": "Welcome to ModelAudit",
        "version": settings.app_version,
    }


@app.get("/health")
async def health_check():
    """Check whether the API is operational."""

    return {
        "status": "healthy",
        "service": "modelaudit-api",
    }


@app.post("/documents/upload")
async def upload_document(
    file: Annotated[UploadFile, File()],
):
    """Upload, validate, extract, and chunk a research paper."""

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="A filename must be provided.",
        )

    try:
        content = await file.read(MAX_FILE_SIZE_MB * 1024 * 1024 + 1)

        if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="PDF exceeds the 15 MB upload limit.",
            )

        processed = process_pdf(content, file.filename)

        documents[processed.document_hash] = processed

        # Invalidate an existing index if this document is re-uploaded.
        retrievers.pop(processed.document_hash, None)

        return {
            "document_id": processed.document_hash,
            "filename": processed.filename,
            "page_count": processed.page_count,
            "chunk_count": len(processed.chunks),
            "extracted_text": processed.extracted_text,
            "chunks": [asdict(chunk) for chunk in processed.chunks],
        }

    except PDFIngestionError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    finally:
        await file.close()


@app.post(
    "/documents/{document_id}/retrieve",
    response_model=RetrievalResponse,
)
async def retrieve_document_evidence(
    document_id: str,
    request: RetrievalRequest,
):
    """Retrieve ranked evidence passages from an uploaded document."""

    document = documents.get(document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found. Upload the PDF first.",
        )

    try:
        # Build the document-specific index only on its first retrieval.
        if document_id not in retrievers:
            retrievers[document_id] = HybridRetriever(
                chunks=document.chunks,
                model=get_embedding_model(),
            )

        retriever = retrievers[document_id]

        results = retriever.retrieve(
            query=request.query,
            top_k=request.top_k,
            hints=request.hints,
        )

        passages = [
            RetrievedPassage(
                chunk_id=result.chunk.chunk_id,
                page=result.chunk.page,
                section_guess=result.chunk.section_guess,
                text=result.chunk.text,
                score=result.score,
                rank=result.rank,
            )
            for result in results
        ]

        return RetrievalResponse(
            document_id=document_id,
            query=request.query,
            retrieval_method="hybrid_bm25_semantic_rrf",
            result_count=len(passages),
            results=passages,
        )

    except Exception as exc:
        # Avoid exposing internal model or retrieval errors to API clients.
        retrievers.pop(document_id, None)

        raise HTTPException(
            status_code=503,
            detail="Evidence retrieval is temporarily unavailable.",
        ) from exc
