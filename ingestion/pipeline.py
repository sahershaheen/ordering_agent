"""Orchestrates the full ingestion pipeline.

Runs the four stages in order:
    1. Load the PDF          (pdf_loader)
    2. Extract text          (pdf_loader)
    3. Chunk the text        (chunker)
    4. Save chunks to JSON   (chunk_store)

Embeddings are intentionally NOT generated here; that is a later stage.
"""

from ingestion.chunk_store import save_chunks
from ingestion.chunker import chunk_documents
from ingestion.config import CHUNKS_OUTPUT_PATH, PDF_PATH
from ingestion.logger import get_logger
from ingestion.pdf_loader import load_pdf

logger = get_logger(__name__)


def run_ingestion() -> None:
    """Run the end-to-end ingestion pipeline for the restaurant PDF."""
    logger.info("=== Starting ingestion pipeline ===")

    try:
        # Steps 1 & 2: load the PDF and extract text (one Document per page)
        documents = load_pdf(PDF_PATH)

        # Step 3: split pages into overlapping chunks
        chunks = chunk_documents(documents)

        # Step 4: persist chunks to JSON for the future embedding stage
        save_chunks(chunks, CHUNKS_OUTPUT_PATH, source_file=PDF_PATH.name)

    except (FileNotFoundError, ValueError, OSError):
        # Each stage already logged the specific failure; re-raise so the
        # caller (CLI) can exit with a non-zero status code.
        logger.error("Ingestion pipeline failed — see errors above")
        raise

    logger.info("=== Ingestion pipeline finished successfully ===")


if __name__ == "__main__":
    run_ingestion()
