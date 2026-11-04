"""Compare BM25, semantic, and hybrid retrieval on a research paper."""

import argparse
from pathlib import Path

from app.ingest import process_pdf
from app.retrieval import HybridRetriever

QUERIES = [
    (
        "A",
        "How were the predictors measured?",
    ),
    (
        "B",
        "What methods were used to measure, define and ascertain "
        "the candidate predictors, including their timing and "
        "measurement instruments?",
    ),
    (
        "C",
        "What clinical and laboratory variables were collected "
        "from patients at admission, and how was the patient "
        "data obtained?",
    ),
]


def display_results(method_name, results):
    """Print ranked passages for one retrieval method."""

    print(f"\n{'=' * 90}")
    print(f"{method_name.upper()} — {len(results)} results")
    print("=" * 90)

    if not results:
        print("No results returned.")
        return

    for result in results:
        chunk = result.chunk
        excerpt = " ".join(chunk.text.split())

        if len(excerpt) > 350:
            excerpt = excerpt[:350] + "..."

        print(
            f"\nRank: {result.rank} | "
            f"Score: {result.score:.4f} | "
            f"Chunk: {chunk.chunk_id} | "
            f"Page: {chunk.page} | "
            f"Section: {chunk.section_guess}"
        )
        print(f"Text: {excerpt}")


def main():
    """Run retrieval comparisons against an uploaded PDF."""

    parser = argparse.ArgumentParser(
        description="Compare retrieval methods on a research paper."
    )
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to the PDF to evaluate.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=10,
        help="Number of passages to retrieve per method.",
    )

    args = parser.parse_args()

    if not args.pdf_path.is_file():
        parser.error(f"PDF file not found: {args.pdf_path}")

    if args.top_k < 1:
        parser.error("--top-k must be at least 1.")

    print(f"Processing: {args.pdf_path.name}")

    document = process_pdf(
        args.pdf_path.read_bytes(),
        args.pdf_path.name,
    )

    print(f"Pages: {document.page_count}")
    print(f"Chunks: {len(document.chunks)}")

    print("\nLoading retrieval models and building indexes...")

    retriever = HybridRetriever(chunks=document.chunks)

    print("Retrieval indexes ready.")

    for label, query in QUERIES:
        print("\n\n" + "#" * 90)
        print(f"QUERY {label}: {query}")
        print("#" * 90)

        lexical_results = retriever.bm25.retrieve(
            query=query,
            top_k=args.top_k,
        )

        semantic_results = retriever.semantic.retrieve(
            query=query,
            top_k=args.top_k,
        )

        hybrid_results = retriever.retrieve(
            query=query,
            top_k=args.top_k,
        )

        display_results("BM25", lexical_results)
        display_results("SEMANTIC", semantic_results)
        display_results("HYBRID (RRF)", hybrid_results)
        if label == "C":
            target_chunk_id = "p2-c4"

            print("\n" + "=" * 90)
            print(f"TARGET PASSAGE ANALYSIS: {target_chunk_id}")
            print("=" * 90)

            full_rankings = {
                "BM25": retriever.bm25.retrieve(
                    query=query,
                    top_k=len(document.chunks),
                ),
                "SEMANTIC": retriever.semantic.retrieve(
                    query=query,
                    top_k=len(document.chunks),
                ),
                "HYBRID": retriever.retrieve(
                    query=query,
                    top_k=len(document.chunks),
                ),
            }

            for method, results in full_rankings.items():
                target = next(
                    (
                        result
                        for result in results
                        if result.chunk.chunk_id == target_chunk_id
                    ),
                    None,
                )

                if target:
                    print(f"{method}: rank {target.rank}, score {target.score:.4f}")
                else:
                    print(f"{method}: NOT RETRIEVED")

    print("\n\nDiagnostic completed.")


if __name__ == "__main__":
    main()
