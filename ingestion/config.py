"""Central configuration for the ingestion pipeline.

Keeping all paths and tuning knobs in one place makes the pipeline easy
to adjust without touching the processing code.
"""

from pathlib import Path

# --- Project layout -------------------------------------------------------

# Root of the project (this file lives in <root>/ingestion/config.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Where source documents live
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

# Where processed artifacts (chunk JSON files) are written
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

# Where log files are written
LOGS_DIR = PROJECT_ROOT / "logs"

# --- Input / output files --------------------------------------------------

# The restaurant knowledge-base PDF to ingest
PDF_PATH = RAW_DATA_DIR / "Flavour_And_Rush_RAG_Sample_Dataset.pdf"

# The JSON file the chunks are saved to
CHUNKS_OUTPUT_PATH = PROCESSED_DATA_DIR / "chunks.json"

# The JSON file the embeddings are saved to
EMBEDDINGS_OUTPUT_PATH = PROCESSED_DATA_DIR / "embeddings.json"

# Directory where the FAISS vector index is persisted. FAISS writes two
# files here: index.faiss (the vectors) and index.pkl (texts + metadata).
VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "vector_store"

# --- Embedding parameters ---------------------------------------------------

# OpenAI embedding model. text-embedding-3-small returns 1536-dimensional
# vectors and is fast and cheap — a good fit for a restaurant knowledge base.
EMBEDDING_MODEL = "text-embedding-3-small"

# How many chunks to send to the API per request. Batching reduces the
# number of round-trips (30 chunks = 1 request at this size).
EMBEDDING_BATCH_SIZE = 100

# --- Retrieval parameters ---------------------------------------------------

# How many chunks to retrieve from FAISS for each user query
RETRIEVAL_TOP_K = 5

# --- Chunking parameters ----------------------------------------------------

# Chunk size in characters. 1000 chars (~200 tokens) keeps each chunk focused
# on a single topic (one menu section, one FAQ, one policy) while still giving
# the retriever enough surrounding context to be useful.
CHUNK_SIZE = 1000

# Overlap between consecutive chunks. 200 chars (20%) prevents information
# that sits on a chunk boundary (e.g. a menu item's price on the next line)
# from being split away from its context.
CHUNK_OVERLAP = 200

# Separators tried in order by RecursiveCharacterTextSplitter: it prefers to
# split on paragraph breaks, then line breaks, then sentences, then words,
# so chunks stay as semantically intact as possible.
CHUNK_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
