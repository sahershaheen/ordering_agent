"""Step 1 & 2: PDF loading and text extraction.

Uses LangChain's PyPDFLoader, which reads the PDF page by page and returns
one Document per page (with page-number metadata we keep for traceability).
"""

from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document

from ingestion.logger import get_logger

logger = get_logger(__name__)


def load_pdf(pdf_path: Path) -> list[Document]:
    """Load a PDF and extract its text as a list of per-page Documents.

    Args:
        pdf_path: Path to the PDF file to load.

    Returns:
        A list of Documents, one per page, each carrying page metadata.

    Raises:
        FileNotFoundError: If the PDF does not exist at the given path.
        ValueError: If the PDF is unreadable or contains no extractable text.
    """
    # --- Validate the input file exists before attempting to parse it ---
    if not pdf_path.exists():
        logger.error("PDF not found at %s", pdf_path)
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    logger.info("Loading PDF: %s", pdf_path.name)

    # --- Parse the PDF; wrap parser failures in a clear error -----------
    try:
        loader = PyPDFLoader(str(pdf_path))
        documents = loader.load()
    except Exception as exc:
        logger.exception("Failed to parse PDF %s", pdf_path.name)
        raise ValueError(f"Could not parse PDF {pdf_path.name}: {exc}") from exc

    # --- Sanity-check that we actually extracted some text --------------
    total_chars = sum(len(doc.page_content) for doc in documents)
    if total_chars == 0:
        logger.error("PDF %s parsed but contains no extractable text", pdf_path.name)
        raise ValueError(
            f"No text extracted from {pdf_path.name}. "
            "The PDF may be scanned images and need OCR."
        )

    logger.info(
        "Extracted %d pages, %d characters total", len(documents), total_chars
    )
    return documents
