"""Tests for PDF ingestion and document chunking."""

import pymupdf
import pytest
from app.ingest import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    MAX_FILE_SIZE_MB,
    MAX_PDF_PAGES,
    PDFIngestionError,
    calculate_document_hash,
    create_chunks,
    detect_section,
    extract_pdf_text,
    process_pdf,
)


def create_test_pdf(page_texts: list[str]) -> bytes:
    """Create an in-memory PDF containing the supplied page texts."""

    document = pymupdf.open()

    for text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), text)

    pdf_bytes = document.tobytes()
    document.close()

    return pdf_bytes


def test_extract_text_from_valid_pdf():
    """Extract text successfully from a valid PDF."""

    content = create_test_pdf(["Abstract of the study", "Methods section"])

    pages, page_count = extract_pdf_text(content)

    assert page_count == 2
    assert len(pages) == 2
    assert "Abstract of the study" in pages[0]["text"]
    assert "Methods section" in pages[1]["text"]


def test_preserve_page_numbers():
    """Associate extracted text with its original page number."""

    content = create_test_pdf(["First page", "Second page", "Third page"])

    pages, _ = extract_pdf_text(content)

    assert [page["page"] for page in pages] == [1, 2, 3]


def test_reject_non_pdf_file():
    """Reject uploads that do not have a PDF signature."""

    with pytest.raises(PDFIngestionError, match="not a valid PDF"):
        extract_pdf_text(b"This is not a PDF")


def test_reject_corrupted_pdf():
    """Reject files with a PDF signature but invalid PDF contents."""

    with pytest.raises(PDFIngestionError, match="Unable to read PDF"):
        extract_pdf_text(b"%PDF-1.7 corrupted content")


def test_reject_oversized_pdf():
    """Reject uploads larger than the configured size limit."""

    oversized_content = b"%PDF-" + b"x" * (MAX_FILE_SIZE_MB * 1024 * 1024)

    with pytest.raises(PDFIngestionError, match="15 MB"):
        extract_pdf_text(oversized_content)


def test_reject_pdf_with_too_many_pages():
    """Reject PDFs exceeding the maximum page count."""

    content = create_test_pdf(["Page content"] * (MAX_PDF_PAGES + 1))

    with pytest.raises(PDFIngestionError, match="40-page"):
        extract_pdf_text(content)


def test_reject_scanned_pdf_without_extractable_text():
    """Reject image-only or blank PDFs without extractable text."""

    content = create_test_pdf(["", ""])

    with pytest.raises(
        PDFIngestionError,
        match="No extractable text found",
    ):
        extract_pdf_text(content)


def test_calculate_document_hash():
    """Generate a consistent SHA-256 hash for identical content."""

    content = b"sample PDF content"

    first_hash = calculate_document_hash(content)
    second_hash = calculate_document_hash(content)

    assert first_hash == second_hash
    assert len(first_hash) == 64


def test_create_chunks_from_long_text():
    """Split long text into overlapping, page-linked chunks."""

    text = "word " * 700

    chunks = create_chunks(
        [
            {
                "page": 1,
                "text": text,
            }
        ]
    )

    assert len(chunks) > 1
    assert all(chunk.page == 1 for chunk in chunks)
    assert all(chunk.text for chunk in chunks)
    assert all(chunk.char_start < chunk.char_end for chunk in chunks)
    assert chunks[0].chunk_id == "p1-c1"
    assert chunks[1].chunk_id == "p1-c2"

    # Consecutive chunks should overlap.
    assert chunks[1].char_start < chunks[0].char_end


def test_chunk_size_and_overlap_configuration():
    """Keep the chunking configuration within expected bounds."""

    assert CHUNK_SIZE == 1200
    assert CHUNK_OVERLAP == 200
    assert CHUNK_OVERLAP < CHUNK_SIZE


def test_process_complete_pdf():
    """Process a PDF and return its hash, text, pages, and chunks."""

    content = create_test_pdf(
        [
            "Abstract of the research paper",
            "Methods and study design",
            "Results of the study",
        ]
    )

    result = process_pdf(content, "sample_paper.pdf")

    assert result.filename == "sample_paper.pdf"
    assert result.page_count == 3
    assert result.document_hash == calculate_document_hash(content)
    assert "Abstract of the research paper" in result.extracted_text
    assert "[Page 1]" in result.extracted_text
    assert "[Page 3]" in result.extracted_text
    assert len(result.chunks) >= 1


def test_detect_standard_section_heading():
    """Recognise a standard section heading."""

    text = "Methods\nWe conducted a retrospective cohort study."

    assert detect_section(text) == "methods"


def test_detect_numbered_section_heading():
    """Recognise numbered section headings."""

    text = "2.1. Methods\nWe conducted a retrospective cohort study."

    assert detect_section(text) == "methods"


def test_detect_heading_below_page_header():
    """Find a section heading below page header information."""

    text = (
        "Journal of Clinical Research\n"
        "Volume 12, Issue 3\n"
        "Page 45\n"
        "\n"
        "Results\n"
        "The study included 500 participants."
    )

    assert detect_section(text) == "results"


def test_return_none_when_no_section_heading_exists():
    """Return None when no recognisable heading is present."""

    text = (
        "This study investigated clinical prediction models "
        "among hospitalised patients."
    )

    assert detect_section(text) is None


def test_chunks_inherit_page_section():
    """Assign the detected page section to all chunks from that page."""

    text = "Methods\n" + ("The study collected clinical data. " * 150)

    chunks = create_chunks(
        [
            {
                "page": 1,
                "text": text,
            }
        ]
    )

    assert len(chunks) > 1
    assert all(chunk.section_guess == "methods" for chunk in chunks)


def test_chunks_without_section_heading_have_none():
    """Keep section_guess as None when no heading is detected."""

    text = "The study collected clinical data. " * 100

    chunks = create_chunks(
        [
            {
                "page": 1,
                "text": text,
            }
        ]
    )

    assert len(chunks) > 0
    assert all(chunk.section_guess is None for chunk in chunks)
