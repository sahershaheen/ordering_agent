"""Structured logging setup shared by the whole application.

Every module calls ``get_logger(__name__)`` so log lines are tagged with the
module they came from. Each log line goes to three places:

    - console          : human-readable, for interactive runs
    - logs/app.log     : human-readable file, for quick reading
    - logs/app.jsonl   : STRUCTURED JSON (one object per line) — machine
                         parseable for log search/analysis tools, with
                         timestamp, level, logger, message, and exception
                         details as separate fields.
"""

import json
import logging
import sys
from datetime import datetime, timezone

from ingestion.config import LOGS_DIR

# Single consistent format: timestamp | level | module | message
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Module-level flag so handlers are only attached once, even if
# get_logger() is called from several modules.
_configured = False

# logging.LogRecord attributes that are NOT custom "extra" fields
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message", "asctime", "taskName",
}


class JsonFormatter(logging.Formatter):
    """Format each record as one JSON object per line (JSONL)."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Exceptions become a structured field instead of a text blob
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        # Any extra={...} fields passed by callers are included as-is
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                entry[key] = value
        return json.dumps(entry, ensure_ascii=False, default=str)


def _configure_root_logger() -> None:
    """Attach console + text-file + JSON-file handlers to the root logger."""
    global _configured
    if _configured:
        return

    # Make sure the logs directory exists before creating the file handlers
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Console handler: human-readable output while the app runs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Text file handler: human-readable record of every run
    file_handler = logging.FileHandler(LOGS_DIR / "app.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    # JSON file handler: structured logs for tooling and analysis
    json_handler = logging.FileHandler(LOGS_DIR / "app.jsonl", encoding="utf-8")
    json_handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console_handler)
    root.addHandler(file_handler)
    root.addHandler(json_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger tagged with the calling module's name."""
    _configure_root_logger()
    return logging.getLogger(name)
