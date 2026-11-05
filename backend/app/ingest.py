
"""PDF ingestion, text extraction, and document chunking."""

import hashlib
import re
from dataclasses import dataclass

import pymupdf

MAX_FILE_SIZE_MB = 15
MAX_PDF_PAGES = 40
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


class PDFIngestionError(Exception):
    """Raised when a PDF cannot be safely processed."""


@dataclass
class DocumentChunk:
    """A text segment linked to its source page and character offsets."""

    chunk_id: str
    page: int
    section_guess: str | None
    text: str
    char_start: int
    char_end: int


@dataclass
class ProcessedDocument:
    """The extracted and chunked contents of an uploaded PDF."""

    document_hash: str
    filename: str
    page_count: int
    extracted_text: str
    chunks: list[DocumentChunk]


def calculate_document_hash(content: bytes) -> str:
    """Return the SHA-256 hash of the original PDF bytes."""

    return hashlib.sha256(content).hexdigest()


def extract_pdf_text(content: bytes) -> tuple[list[dict], int]:
    """Extract text from each page of a PDF with upload safeguards."""

    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise PDFIngestionError("PDF exceeds the 15 MB upload limit.")

    if not content.startswith(b"%PDF-"):
        raise PDFIngestionError("Uploaded file is not a valid PDF.")

    try:
        with pymupdf.open(stream=content, filetype="pdf") as document:
            page_count = len(document)

            if page_count == 0:
                raise PDFIngestionError("PDF contains no pages.")

            if page_count > MAX_PDF_PAGES:
                raise PDFIngestionError(
                    f"PDF exceeds the {MAX_PDF_PAGES}-page limit."
                )

            pages = []

            for page_index in range(page_count):
                page = document.load_page(page_index)
                page_number = page_index + 1
                extracted = page.get_text("text")

                if not isinstance(extracted, str):
                    raise PDFIngestionError("Unable to extract text from PDF page.")

                text = extracted.strip()

                pages.append(
                    {
                        "page": page_number,
                        "text": text,
                    }
                )

    except PDFIngestionError:
        raise
    except Exception as exc:
        raise PDFIngestionError(
            "Unable to read PDF. The file may be corrupted or encrypted."
        ) from exc

    if not any(page["text"] for page in pages):
        raise PDFIngestionError(
            "No extractable text found. Scanned PDFs are not supported."
        )

    return pages, page_count


def detect_section(text: str) -> str | None:
    """Guess a document section from headings near the start of page text."""

    common_sections = [
        "abstract",
        "introduction",
        "methods",
        "methodology",
        "results",
        "discussion",
        "conclusion",
        "limitations",
        "references",
    ]

    for line in text.splitlines()[:5]:
        heading = line.strip().lower()

        if not heading:
            continue

        # Remove optional section numbering, e.g. "2. Methods".
        heading = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", heading)

        for section in common_sections:
            if heading == section:
                return section

    return None


def create_chunks(pages: list[dict]) -> list[DocumentChunk]:
    """Split normalised page text into overlapping, page-linked chunks.

    Character offsets are relative to the normalised text of each page.
    Chunk IDs are stable within a processed document.
    """

    chunks = []

    for page_data in pages:
        page_number = page_data["page"]
        original_text = page_data["text"]

        # Detect the section before normalising whitespace.
        section_guess = detect_section(original_text)

        # Normalise text separately for consistent chunking.
        text = re.sub(r"\s+", " ", original_text).strip()

        if not text:
            continue

        page_chunks = []
        start = 0

        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))

            if end < len(text):
                boundary = text.rfind(" ", start, end)

                if boundary > start:
                    end = boundary

            chunk_text = text[start:end].strip()

            if chunk_text:
                page_chunks.append(
                    DocumentChunk(
                        chunk_id=f"p{page_number}-c{len(page_chunks) + 1}",
                        page=page_number,
                        section_guess=section_guess,
                        text=chunk_text,
                        char_start=start,
                        char_end=end,
                    )
                )

            if end >= len(text):
                break

            start = max(end - CHUNK_OVERLAP, start + 1)

        chunks.extend(page_chunks)

    return chunks


def process_pdf(content: bytes, filename: str) -> ProcessedDocument:
    """Validate, extract, hash, and chunk an uploaded PDF."""

    pages, page_count = extract_pdf_text(content)

    extracted_text = "\n".join(
        f"[Page {page['page']}]\n{page['text']}" for page in pages
    )

    chunks = create_chunks(pages)

    return ProcessedDocument(
        document_hash=calculate_document_hash(content),
        filename=filename,
        page_count=page_count,
        extracted_text=extracted_text,
        chunks=chunks,
    )
