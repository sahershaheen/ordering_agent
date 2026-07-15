"""CLI entry point to create/verify the SQLite database.

Usage:
    uv run python init_db.py

Note: running this manually is optional — the database also initializes
itself automatically the first time any code opens a connection.
"""

import sys

from database.db import DATABASE_PATH, initialize_database
from database.schema import ALL_TABLES

if __name__ == "__main__":
    try:
        initialize_database()
    except Exception:
        # Failure details were already logged by the database module;
        # exit non-zero so scripts/CI can detect the failure.
        sys.exit(1)

    print(f"\nDatabase ready at: {DATABASE_PATH}")
    print(f"Tables: {', '.join(ALL_TABLES)}")
