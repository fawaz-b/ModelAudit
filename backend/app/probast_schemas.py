"""Pydantic contracts for the ModelAudit PROBAST+AI evaluation MVP.

PROBAST+AI content is reproduced/adapted under CC BY-NC 4.0; see the
framework JSON attribution and licence metadata. ModelAudit-specific
fields and safeguards are not endorsed by the framework authors.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProbastBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


ProbastResponse = Literal[
    "yes", "probably_yes", "probably_no", "no", "no_information", "not_applicable"
]
ProbastDomainJudgement = Literal["low", "high", "unclear"]
ReviewerStatus = Literal["pending", "accepted", "amended", "rejected"]
AssessmentStatus = Literal["in_progress", "completed", "requires_review"]


class ProbastEvidenceReference(ProbastBaseModel):
    quote: str = Field(min_length=1, max_length=1000)
    page: int = Field(ge=1)
    chunk_id: str = Field(min_length=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_offsets(self):
        if self.char_start is not None and self.char_end is not None and self.char_end < self.char_start:
            raise ValueError("char_end must be greater than or equal to char_start")
        return self


class ProbastQuestionFinding(ProbastBaseModel):
    question_id: str = Field(pattern=r"^PE-[1-4]\.[1-7]$")
    response: ProbastResponse
    explanation: str = Field(min_length=1, max_length=3000)
    evidence: list[ProbastEvidenceReference] = Field(default_factory=list)
    evidence_verified: bool = False
    reviewer_status: ReviewerStatus = "pending"
    reviewer_comment: str | None = Field(default=None, max_length=3000)
    flags: list[str] = Field(default_factory=list)


class ProbastDomainSummary(ProbastBaseModel):
    domain_id: Literal["D1", "D2", "D3", "D4"]
    included_questions: list[str]
    official_question_count: int = Field(ge=1)
    coverage_complete: Literal[False] = False
    # This MVP deliberately does not produce official domain judgements.
    risk_of_bias_judgement: Literal["not_assessed"] = "not_assessed"
    rationale: str | None = None


class ProbastApplicabilityFinding(ProbastBaseModel):
    domain_id: Literal["D1", "D2", "D3"]
    judgement: Literal["not_assessed"] = "not_assessed"
    rationale: str | None = None
    # Applicability requires the assessor's intended use/PICOTS context.
    picots_supplied: bool = False


class ProbastAssessment(ProbastBaseModel):
    framework_id: Literal["PROBAST+AI"] = "PROBAST+AI"
    framework_version: str
    branch: Literal["evaluation"] = "evaluation"
    document_id: str = Field(min_length=1)
    model_identifier: str | None = None
    evaluation_component: Literal["apparent", "internal", "external", "unspecified"] = "unspecified"
    findings: list[ProbastQuestionFinding]
    domains: list[ProbastDomainSummary]
    applicability: list[ProbastApplicabilityFinding] = Field(default_factory=list)
    assessment_status: AssessmentStatus = "in_progress"
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_subset_contract(self):
        ids = [finding.question_id for finding in self.findings]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate PROBAST+AI question findings are not allowed")
        if any(domain.risk_of_bias_judgement != "not_assessed" for domain in self.domains):
            raise ValueError("The eight-question MVP cannot produce official domain risk-of-bias judgements")
        return self
