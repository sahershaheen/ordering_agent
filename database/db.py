"""SQLite connection handling and automatic database initialization.

Usage from anywhere in the app:

    from database.db import get_connection

    with get_connection() as conn:
        conn.execute("INSERT INTO customers (full_name, phone) VALUES (?, ?)", ...)

The database file and all tables are created automatically the first time
a connection is opened — no manual setup step is required.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from database.schema import ALL_TABLES
from ingestion.config import PROJECT_ROOT
from ingestion.logger import get_logger

logger = get_logger(__name__)

# The SQLite file lives next to the other local data artifacts
DATABASE_PATH = PROJECT_ROOT / "data" / "restaurant.db"

# Tracks whether initialization ran in this process, so we only pay the
# (cheap, idempotent) table-creation cost once per run.
_initialized = False


def initialize_database(db_path: Path = DATABASE_PATH) -> None:
    """Create the database file and all tables if they don't exist yet.

    Safe to call any number of times: every statement uses
    CREATE TABLE IF NOT EXISTS, so existing data is never touched.

    Args:
        db_path: Where the SQLite file should live.

    Raises:
        sqlite3.Error: If table creation fails.
    """
    # --- Make sure the parent directory (data/) exists --------------------
    db_path.parent.mkdir(parents=True, exist_ok=True)

    is_new = not db_path.exists()

    # --- Create every table inside a single transaction -------------------
    try:
        with sqlite3.connect(db_path) as conn:
            for table_name, create_statement in ALL_TABLES.items():
                conn.execute(create_statement)
                logger.debug("Ensured table exists: %s", table_name)
            conn.commit()
    except sqlite3.Error:
        logger.exception("Failed to initialize database at %s", db_path)
        raise

    if is_new:
        logger.info(
            "Created new database at %s with tables: %s",
            db_path,
            ", ".join(ALL_TABLES),
        )
    else:
        logger.info("Database at %s verified (%d tables)", db_path, len(ALL_TABLES))


@contextmanager
def get_connection(db_path: Path = DATABASE_PATH) -> Iterator[sqlite3.Connection]:
    """Open a connection, auto-initializing the database on first use.

    Commits on success, rolls back on error, and always closes the
    connection — callers just use it in a ``with`` block.

    Args:
        db_path: Path to the SQLite file.

    Yields:
        An open sqlite3.Connection with foreign keys enforced and
        rows accessible by column name (sqlite3.Row).

    Raises:
        sqlite3.Error: If the connection cannot be opened or a statement
            inside the ``with`` block fails (after rolling back).
    """
    # --- Automatic initialization: run once per process --------------------
    global _initialized
    if not _initialized:
        initialize_database(db_path)
        _initialized = True

    # --- Open the connection ------------------------------------------------
    try:
        conn = sqlite3.connect(db_path)
    except sqlite3.Error:
        logger.exception("Could not open database at %s", db_path)
        raise

    # Return rows that support access by column name (row["full_name"])
    conn.row_factory = sqlite3.Row
    # SQLite doesn't enforce foreign keys unless explicitly enabled
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        yield conn
        # Commit everything the caller did if no exception occurred
        conn.commit()
    except sqlite3.Error:
        # Undo any partial writes from the failed block
        conn.rollback()
        logger.exception("Database operation failed — transaction rolled back")
        raise
    finally:
        conn.close()
