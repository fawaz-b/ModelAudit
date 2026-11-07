"""Pydantic schemas for ModelAudit API requests and responses."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Shared configuration
# ---------------------------------------------------------------------------


class StrictBaseModel(BaseModel):
    """Base model that rejects unexpected fields."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Retrieval schemas — existing API
# ---------------------------------------------------------------------------


class RetrievalRequest(StrictBaseModel):
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


class RetrievedPassage(StrictBaseModel):
    """A retrieved passage with its source and ranking information."""

    chunk_id: str
    page: int
    section_guess: str | None
    text: str
    score: float
    rank: int


class RetrievalResponse(StrictBaseModel):
    """Response containing retrieved evidence passages."""

    document_id: str
    query: str
    retrieval_method: str
    result_count: int
    results: list[RetrievedPassage]


# ---------------------------------------------------------------------------
# Assessment request and study context
# ---------------------------------------------------------------------------


class StudyContext(StrictBaseModel):
    """
    Study characteristics used to resolve conditional framework requirements.

    Fields are optional because some characteristics may not be known
    before the paper has been assessed.
    """

    study_type: str | None = None

    has_separate_evaluation_dataset: bool | None = None
    synthetic_data_used: bool | None = None

    multiple_or_identifiable_centres: bool | None = None
    eligibility_uses_continuous_restriction: bool | None = None

    predictor_assessment_requires_interpretation: bool | None = None

    data_omitted_due_to_missingness: bool | None = None
    imputation_used: bool | None = None
    imputation_with_data_partitioning: bool | None = None

    multiple_models_evaluated: bool | None = None

    data_stated_available: bool | None = None
    code_stated_available: bool | None = None

    subgroup_performance_evaluated_or_reported: bool | None = None


class AssessmentRequest(StrictBaseModel):
    """Request to assess a document against a reporting framework."""

    document_id: str = Field(min_length=1)
    study_context: StudyContext = Field(default_factory=StudyContext)


# ---------------------------------------------------------------------------
# Evidence and element-level findings
# ---------------------------------------------------------------------------

ElementStatus = Literal[
    "reported",
    "partially_reported",
    "author_stated_unavailable",
    "not_found_in_main_text",
    "unclear",
    "not_applicable",
    "not_assessed",
]


JudgementCategory = Literal[
    "reported",
    "partially_reported",
    "author_stated_unavailable",
    "not_found_in_main_text",
    "unclear",
    "not_applicable",
    "not_assessed",
]


class EvidenceReference(StrictBaseModel):
    """A passage cited as evidence for an element-level finding."""

    quote: str = Field(
        min_length=1,
        max_length=1000,
        description="Verbatim quotation from the paper.",
    )
    page: int = Field(ge=1)
    chunk_id: str = Field(min_length=1)

    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)

    @field_validator("quote")
    @classmethod
    def validate_quote(cls, value: str) -> str:
        """Reject empty or whitespace-only quotations."""

        if not value.strip():
            raise ValueError("Evidence quote cannot be empty.")

        return value.strip()


class ElementFinding(StrictBaseModel):
    """
    Assessment of one reporting element.

    The model proposes a status and evidence. Evidence verification is
    represented separately and must not be inferred from the presence
    of a quotation.
    """

    element_key: str = Field(min_length=1)
    status: ElementStatus

    explanation: str = Field(
        min_length=1,
        description="Concise explanation of the finding.",
    )

    evidence: list[EvidenceReference] = Field(default_factory=list)

    evidence_verified: bool = False

    reviewer_comment: str | None = None


# ---------------------------------------------------------------------------
# Item-level assessment
# ---------------------------------------------------------------------------


class ItemAssessment(StrictBaseModel):
    """Assessment of one TRIPOD+AI checklist item."""

    item_id: str = Field(min_length=1)

    element_findings: list[ElementFinding]

    category: JudgementCategory

    required_elements: list[str] = Field(default_factory=list)
    unresolved_conditions: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)

    reviewer_status: Literal[
        "pending",
        "accepted",
        "amended",
        "rejected",
    ] = "pending"

    reviewer_comment: str | None = None


# ---------------------------------------------------------------------------
# Complete framework assessment
# ---------------------------------------------------------------------------


class FrameworkAssessment(StrictBaseModel):
    """Complete assessment against one reporting framework."""

    framework_id: str
    framework_name: str
    framework_version: str

    document_id: str

    study_context: StudyContext

    items: list[ItemAssessment]

    assessment_status: Literal[
        "in_progress",
        "completed",
        "requires_review",
    ] = "in_progress"
