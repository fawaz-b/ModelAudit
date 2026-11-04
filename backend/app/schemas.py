"""Pydantic schemas for ModelAudit API requests and responses."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RetrievalRequest(BaseModel):
    """Request parameters for retrieving evidence from a document."""

    query: str = Field(
        min_length=1,
        max_length=2000,
        description="Question or framework item to retrieve evidence for.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of passages to return.",
    )
    hints: list[str] = Field(
        default_factory=list,
        description="Optional keywords to improve retrieval.",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Reject queries containing only whitespace."""

        if not value.strip():
            raise ValueError("Query cannot contain only whitespace.")

        return value.strip()


class RetrievedPassage(BaseModel):
    """A retrieved passage with its source and ranking information."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    page: int
    section_guess: str | None
    text: str
    score: float
    rank: int


class RetrievalResponse(BaseModel):
    """Response containing retrieved evidence passages."""

    document_id: str
    query: str
    retrieval_method: str
    result_count: int
    results: list[RetrievedPassage]
