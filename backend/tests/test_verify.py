from app.schemas import RetrievedPassage
from app.verify import assess_element, normalise_evidence_text, verify_evidence


def make_passage(
    text="The model used cross-validation to estimate performance.",
    chunk_id="chunk-1",
    page=4,
):
    return RetrievedPassage(
        chunk_id=chunk_id,
        page=page,
        section_guess=None,
        text=text,
        score=1.0,
        rank=1,
    )


def make_reference(
    quote="cross-validation",
    chunk_id="chunk-1",
    page=4,
):
    return {
        "quote": quote,
        "chunk_id": chunk_id,
        "page": page,
    }


def test_exact_quote_is_verified():
    assert verify_evidence(
        [make_reference()],
        [make_passage()],
    )


def test_unicode_dash_and_whitespace_normalisation():
    assert normalise_evidence_text("cross-\nvalidation") == "cross-validation"
    assert verify_evidence(
        [make_reference(quote="cross‑validation")],
        [make_passage()],
    )


def test_invented_quote_is_rejected():
    assert not verify_evidence(
        [make_reference(quote="The model achieved perfect accuracy")],
        [make_passage()],
    )


def test_wrong_page_is_rejected():
    assert not verify_evidence(
        [make_reference(page=5)],
        [make_passage()],
    )


def test_wrong_chunk_id_is_rejected():
    assert not verify_evidence(
        [make_reference(chunk_id="nonexistent")],
        [make_passage()],
    )


def test_empty_evidence_is_not_verified():
    assert not verify_evidence([], [make_passage()])


def test_all_references_must_be_valid():
    assert not verify_evidence(
        [
            make_reference(),
            make_reference(quote="invented quotation"),
        ],
        [make_passage()],
    )


def test_unverified_reported_finding_is_downgraded():
    finding = assess_element(
        {
            "element_key": "e1",
            "status": "reported",
            "explanation": "The paper reports the method.",
            "evidence": [make_reference(quote="invented quotation")],
        },
        [make_passage()],
    )
    assert finding.status == "unclear"
    assert finding.evidence_verified is False
    assert "downgraded" in (finding.reviewer_comment or "")


def test_verified_reported_finding_is_preserved():
    finding = assess_element(
        {
            "element_key": "e1",
            "status": "reported",
            "explanation": "The paper reports the method.",
            "evidence": [make_reference()],
        },
        [make_passage()],
    )
    assert finding.status == "reported"
    assert finding.evidence_verified is True


def test_not_found_status_is_not_claimed_as_quote_verified():
    finding = assess_element(
        {
            "element_key": "e1",
            "status": "not_found_in_main_text",
            "explanation": "The item was not located in the main text.",
            "evidence": [],
        },
        [make_passage()],
    )
    assert finding.status == "not_found_in_main_text"
    assert finding.evidence_verified is False
