"""CLI entry point for the RAG ingestion pipeline.

Usage:
    uv run python ingest.py
"""

import sys

from ingestion.pipeline import run_ingestion

if __name__ == "__main__":
    try:
        run_ingestion()
    except Exception:
        # Failure details were already logged by the pipeline;
        # exit non-zero so scripts/CI can detect the failure.
        sys.exit(1)
