"""Pydantic contracts for the ModelAudit PROBAST+AI evaluation MVP."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ProbastResponse = Literal[
    "yes",
    "probably_yes",
    "probably_no",
    "no",
    "no_information",
    "not_applicable",
]

EvaluationComponent = Literal[
    "apparent",
    "internal",
    "external",
    "unspecified",
]

ValidationMethod = Literal[
    "training_test_split",
    "bootstrap",
    "cross_validation",
    "other_resampling",
    "none",
    "unclear",
]

ReviewerStatus = Literal["pending", "accepted", "amended", "rejected"]

AssessmentStatus = Literal["in_progress", "completed", "requires_review"]

AssessmentState = Literal["assessed", "not_assessed"]


class ProbastBaseModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class PICOTSContext(ProbastBaseModel):
    population: str | None = None
    index_model: str | None = None
    comparator_model: str | None = None
    outcome: str | None = None
    timing: str | None = None
    setting: str | None = None
    intended_use: str | None = None

    @property
    def supplied(self) -> bool:
        return any(self.model_dump().values())


class ProbastStudyContext(ProbastBaseModel):
    study_type: Literal["development", "evaluation", "both", "unclear"] = "unclear"

    evaluation_components: list[EvaluationComponent] = Field(
        default_factory=lambda: ["unspecified"]
    )

    validation_method: ValidationMethod = "unclear"
    has_training_test_split: bool | None = None
    evaluation_dataset_independent: bool | None = None
    picots: PICOTSContext = Field(default_factory=PICOTSContext)

    @model_validator(mode="after")
    def validate_components(self):
        if not self.evaluation_components:
            raise ValueError("At least one evaluation component must be specified.")

        if (
            "unspecified" in self.evaluation_components
            and len(self.evaluation_components) > 1
        ):
            raise ValueError(
                "'unspecified' cannot be combined with named evaluation components."
            )

        if (
            self.validation_method == "training_test_split"
            and self.has_training_test_split is False
        ):
            raise ValueError(
                "validation_method conflicts with has_training_test_split=False"
            )

        if (
            self.validation_method
            in {"bootstrap", "cross_validation", "other_resampling"}
            and self.has_training_test_split is True
        ):
            raise ValueError(
                "Resampling method conflicts with has_training_test_split=True"
            )

        return self


class ProbastEvidenceReference(ProbastBaseModel):
    quote: str = Field(min_length=1, max_length=1000)
    page: int = Field(ge=1)
    chunk_id: str = Field(min_length=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_offsets(self):
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end < self.char_start
        ):
            raise ValueError("char_end must be greater than or equal to char_start")

        return self


class ProbastQuestionFinding(ProbastBaseModel):
    question_id: str = Field(pattern=r"^PE-[1-4]\.[1-7]$")

    evaluation_component: EvaluationComponent = "unspecified"

    assessment_state: AssessmentState = "assessed"

    response: ProbastResponse | None = None

    explanation: str = Field(min_length=1, max_length=3000)

    evidence: list[ProbastEvidenceReference] = Field(default_factory=list)

    evidence_verified: bool = False

    reviewer_status: ReviewerStatus = "pending"

    reviewer_comment: str | None = Field(default=None, max_length=3000)

    flags: list[str] = Field(default_factory=list)

    not_assessed_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def enforce_finding_contract(self):
        if self.assessment_state == "not_assessed":
            if self.response is not None:
                raise ValueError(
                    "A not_assessed finding must not carry a PROBAST response."
                )

            if not self.not_assessed_reason:
                raise ValueError("not_assessed findings require a reason.")

            return self

        if self.response is None:
            raise ValueError("An assessed finding requires a PROBAST response.")

        # Directional LLM proposals are allowed to be parsed before
        # evidence verification. The verifier must subsequently either:
        # 1. verify the quotation evidence and preserve the response, or
        # 2. downgrade an unsupported directional response.
        #
        # Therefore, quotation evidence is not required at this stage.

        if self.response == "not_applicable" and not self.explanation.strip():
            raise ValueError(
                "Not-applicable findings require a contextual explanation."
            )

        return self


class ProbastDomainSummary(ProbastBaseModel):
    domain_id: Literal["D1", "D2", "D3", "D4"]

    included_questions: list[str]

    official_question_count: int = Field(ge=1)

    coverage_complete: Literal[False] = False

    risk_of_bias_judgement: Literal["not_assessed"] = "not_assessed"

    rationale: str | None = None


class ProbastApplicabilityFinding(ProbastBaseModel):
    domain_id: Literal["D1", "D2", "D3"]

    judgement: Literal["not_assessed"] = "not_assessed"

    rationale: str | None = None

    picots_supplied: bool = False


class ProbastAssessmentRequest(ProbastBaseModel):
    document_id: str = Field(min_length=1)

    context: ProbastStudyContext = Field(default_factory=ProbastStudyContext)

    model_identifier: str | None = Field(
        default=None,
        max_length=300,
    )


class ProbastAssessment(ProbastBaseModel):
    framework_id: Literal["PROBAST+AI"] = "PROBAST+AI"

    framework_version: str

    branch: Literal["evaluation"] = "evaluation"

    document_id: str = Field(min_length=1)

    model_identifier: str | None = None

    context: ProbastStudyContext

    findings: list[ProbastQuestionFinding]

    domains: list[ProbastDomainSummary]

    applicability: list[ProbastApplicabilityFinding] = Field(default_factory=list)

    assessment_status: AssessmentStatus = "in_progress"

    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_subset_contract(self):
        keys = [
            (finding.question_id, finding.evaluation_component)
            for finding in self.findings
        ]

        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate question/component findings are not allowed")

        if any(
            domain.risk_of_bias_judgement != "not_assessed" for domain in self.domains
        ):
            raise ValueError(
                "The eight-question MVP cannot produce official "
                "domain risk-of-bias judgements"
            )

        return self
