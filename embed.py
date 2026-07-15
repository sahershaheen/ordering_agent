"""CLI entry point for the embedding stage.

Usage:
    uv run python embed.py

Requires data/processed/chunks.json (run `uv run python ingest.py` first)
and OPENAI_API_KEY in the .env file.
"""

import sys

from ingestion.embedder import run_embedding

if __name__ == "__main__":
    try:
        run_embedding()
    except Exception:
        # Failure details were already logged by the embedding stage;
        # exit non-zero so scripts/CI can detect the failure.
        sys.exit(1)
