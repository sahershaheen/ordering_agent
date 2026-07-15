"""CLI entry point for the FAISS vector store stage.

Usage:
    uv run python build_index.py

Requires data/processed/embeddings.json (run `uv run python embed.py` first).
"""

import sys

from ingestion.vector_store import run_indexing

if __name__ == "__main__":
    try:
        run_indexing()
    except Exception:
        # Failure details were already logged by the indexing stage;
        # exit non-zero so scripts/CI can detect the failure.
        sys.exit(1)
