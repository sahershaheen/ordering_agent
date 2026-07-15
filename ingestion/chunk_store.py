"""Step 4: Saving chunks.

Serialises the chunk Documents to a JSON file so the later embedding step
(and any debugging) can work from a stable on-disk artifact instead of
re-parsing the PDF every time.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.documents import Document

from ingestion.logger import get_logger

logger = get_logger(__name__)


def save_chunks(chunks: list[Document], output_path: Path, source_file: str) -> None:
    """Write chunks to a JSON file with metadata for traceability.

    The JSON layout is:
        {
          "metadata": { source file, chunk count, created_at, ... },
          "chunks": [ { "chunk_id", "text", "page", "source" }, ... ]
        }

    Args:
        chunks: The chunk Documents to persist.
        output_path: Destination JSON file path.
        source_file: Name of the original PDF (stored in metadata).

    Raises:
        OSError: If the file cannot be written (permissions, disk full, ...).
    """
    # --- Make sure the destination directory exists ----------------------
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Convert Documents to plain JSON-serialisable dicts ---------------
    # Each chunk gets a stable chunk_id so embeddings can reference it later.
    chunk_records = [
        {
            "chunk_id": index,
            "text": chunk.page_content,
            # PyPDFLoader stores 0-based page numbers; convert to 1-based
            # so the metadata matches what a human sees in a PDF viewer.
            "page": chunk.metadata.get("page", -1) + 1,
            "source": source_file,
        }
        for index, chunk in enumerate(chunks)
    ]

    # --- Wrap chunks with run metadata for traceability -------------------
    payload = {
        "metadata": {
            "source_file": source_file,
            "num_chunks": len(chunk_records),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "chunks": chunk_records,
    }

    # --- Write the JSON file (UTF-8 so menu symbols like £ survive) -------
    try:
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
    except OSError:
        logger.exception("Failed to write chunks to %s", output_path)
        raise

    logger.info("Saved %d chunks to %s", len(chunk_records), output_path)
