"""Start the Flavour & Rush API on localhost:8000.

Usage:
    uv run python server.py

Docs UI: http://localhost:8000/docs
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000)
