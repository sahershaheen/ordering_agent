"""Embedding stage: convert saved chunks into OpenAI embedding vectors.

Reads the chunks produced by the ingestion pipeline (data/processed/chunks.json),
generates one embedding per chunk using OpenAI's text-embedding-3-small model,
and saves the vectors alongside their chunk metadata to a local JSON file so
they can be inspected before a vector database is introduced.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings

from ingestion.config import (
    CHUNKS_OUTPUT_PATH,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_MODEL,
    EMBEDDINGS_OUTPUT_PATH,
)
from ingestion.logger import get_logger

logger = get_logger(__name__)


def load_chunks(chunks_path: Path) -> list[dict]:
    """Load the chunk records produced by the ingestion pipeline.

    Args:
        chunks_path: Path to chunks.json.

    Returns:
        The list of chunk dicts ({"chunk_id", "text", "page", "source"}).

    Raises:
        FileNotFoundError: If chunks.json does not exist (ingestion not run).
        ValueError: If the file is malformed or contains no chunks.
    """
    # --- The chunks file must exist before we can embed anything ---------
    if not chunks_path.exists():
        logger.error("Chunks file not found at %s — run ingest.py first", chunks_path)
        raise FileNotFoundError(f"Chunks file not found: {chunks_path}")

    # --- Parse the JSON and validate its structure ------------------------
    try:
        with chunks_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        chunks = payload["chunks"]
    except (json.JSONDecodeError, KeyError) as exc:
        logger.exception("Chunks file %s is malformed", chunks_path)
        raise ValueError(f"Malformed chunks file: {chunks_path}") from exc

    if not chunks:
        logger.error("Chunks file %s contains no chunks", chunks_path)
        raise ValueError("No chunks found to embed")

    logger.info("Loaded %d chunks from %s", len(chunks), chunks_path.name)
    return chunks


def embed_chunks(chunks: list[dict]) -> list[list[float]]:
    """Generate an embedding vector for every chunk's text.

    Args:
        chunks: Chunk dicts loaded from chunks.json.

    Returns:
        A list of embedding vectors, index-aligned with the input chunks.

    Raises:
        ValueError: If the OpenAI API key is missing.
        RuntimeError: If the embedding API call fails.
    """
    # --- Load the API key from .env and fail fast if it's missing ---------
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not found — check your .env file")
        raise ValueError("OPENAI_API_KEY is not set in the environment/.env")

    logger.info(
        "Embedding %d chunks with model %s (batch size %d)",
        len(chunks),
        EMBEDDING_MODEL,
        EMBEDDING_BATCH_SIZE,
    )

    # --- Configure the embeddings client -----------------------------------
    # chunk_size here is LangChain's batch size: how many texts are sent
    # to the OpenAI API in a single request.
    embedder = OpenAIEmbeddings(model=EMBEDDING_MODEL, chunk_size=EMBEDDING_BATCH_SIZE)

    # --- Call the API; wrap failures (auth, network, rate limits) ----------
    texts = [chunk["text"] for chunk in chunks]
    try:
        vectors = embedder.embed_documents(texts)
    except Exception as exc:
        logger.exception("OpenAI embedding request failed")
        raise RuntimeError(f"Embedding generation failed: {exc}") from exc

    # --- Sanity-check the response before returning it ---------------------
    if len(vectors) != len(chunks):
        logger.error(
            "Expected %d embeddings but received %d", len(chunks), len(vectors)
        )
        raise RuntimeError("Embedding count does not match chunk count")

    logger.info(
        "Generated %d embeddings (%d dimensions each)", len(vectors), len(vectors[0])
    )
    return vectors


def save_embeddings(
    chunks: list[dict], vectors: list[list[float]], output_path: Path
) -> None:
    """Save embeddings with their chunk metadata to a JSON file.

    The JSON layout is:
        {
          "metadata": { model, dimensions, num_embeddings, created_at },
          "embeddings": [ { "chunk_id", "text", "page", "source",
                            "embedding": [...] }, ... ]
        }

    Args:
        chunks: The original chunk dicts (for id/text/page metadata).
        vectors: The embedding vectors, index-aligned with chunks.
        output_path: Destination JSON file path.

    Raises:
        OSError: If the file cannot be written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # --- Pair each chunk with its vector so the file is self-contained -----
    # Keeping the text next to the vector makes manual inspection easy.
    records = [
        {**chunk, "embedding": vector}
        for chunk, vector in zip(chunks, vectors)
    ]

    payload = {
        "metadata": {
            "model": EMBEDDING_MODEL,
            "dimensions": len(vectors[0]),
            "num_embeddings": len(records),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "embeddings": records,
    }

    # --- Write the JSON file ------------------------------------------------
    try:
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False)
    except OSError:
        logger.exception("Failed to write embeddings to %s", output_path)
        raise

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info(
        "Saved %d embeddings to %s (%.1f MB)", len(records), output_path, size_mb
    )


def run_embedding() -> None:
    """Run the full embedding stage: load chunks -> embed -> save."""
    logger.info("=== Starting embedding stage ===")

    try:
        # Step 1: load the chunks produced by the ingestion pipeline
        chunks = load_chunks(CHUNKS_OUTPUT_PATH)

        # Step 2: generate one embedding vector per chunk via OpenAI
        vectors = embed_chunks(chunks)

        # Step 3: save vectors + metadata locally for inspection
        save_embeddings(chunks, vectors, EMBEDDINGS_OUTPUT_PATH)

    except (FileNotFoundError, ValueError, RuntimeError, OSError):
        # Specific failures were already logged where they occurred
        logger.error("Embedding stage failed — see errors above")
        raise

    logger.info("=== Embedding stage finished successfully ===")


if __name__ == "__main__":
    run_embedding()
