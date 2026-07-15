"""Step 3: Chunking.

Splits the extracted page Documents into smaller overlapping chunks using
RecursiveCharacterTextSplitter, so each chunk is small enough to embed and
retrieve precisely, while overlap preserves context across boundaries.
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ingestion.config import CHUNK_OVERLAP, CHUNK_SEPARATORS, CHUNK_SIZE
from ingestion.logger import get_logger

logger = get_logger(__name__)


def chunk_documents(documents: list[Document]) -> list[Document]:
    """Split page Documents into overlapping chunks.

    Args:
        documents: Per-page Documents produced by the PDF loader.

    Returns:
        A list of chunk Documents (page metadata is carried over
        automatically by the splitter).

    Raises:
        ValueError: If no documents were provided or splitting produced
            no chunks.
    """
    # --- Guard against an empty input list ------------------------------
    if not documents:
        logger.error("No documents provided to the chunker")
        raise ValueError("Cannot chunk an empty list of documents")

    logger.info(
        "Chunking %d pages (chunk_size=%d, chunk_overlap=%d)",
        len(documents),
        CHUNK_SIZE,
        CHUNK_OVERLAP,
    )

    # --- Configure the splitter ------------------------------------------
    # The recursive splitter tries each separator in order (paragraphs,
    # lines, sentences, words) and only falls back to harder splits when
    # a piece is still too large, keeping chunks semantically coherent.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=CHUNK_SEPARATORS,
        length_function=len,
    )

    # --- Perform the split -------------------------------------------------
    chunks = splitter.split_documents(documents)

    if not chunks:
        logger.error("Splitting produced zero chunks")
        raise ValueError("Text splitting produced no chunks")

    # Log basic statistics so chunking quality can be sanity-checked
    sizes = [len(chunk.page_content) for chunk in chunks]
    logger.info(
        "Produced %d chunks (min=%d, max=%d, avg=%d chars)",
        len(chunks),
        min(sizes),
        max(sizes),
        sum(sizes) // len(sizes),
    )
    return chunks
