"""The retrieval pipeline: query -> embedding -> FAISS -> top chunks -> GPT.

Flow for every question:
    1. The user query is embedded with text-embedding-3-small (the SAME
       model used to embed the knowledge-base chunks — required for the
       similarity search to be meaningful).
    2. FAISS returns the top-K most similar chunks (K = 5 from config).
    3. The chunks are formatted into a context block.
    4. GPT answers using ONLY that context; if the answer is not in the
       context it must say so with the standard fallback sentence.

Steps 1-2 happen inside FAISS's similarity_search(), which uses the
embedding client attached to the store when it was loaded.
"""

import threading
import time

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

from ingestion.config import RETRIEVAL_TOP_K
from ingestion.logger import get_logger
from ingestion.vector_store import load_vector_store

logger = get_logger(__name__)

# --- Retrieval cache ---------------------------------------------------------
# Popular queries ("menu", "opening hours") repeat constantly. Caching the
# FAISS results for a few minutes skips both the OpenAI embedding call and
# the search — faster responses and lower API cost. The knowledge base is
# static between ingestion runs, so short-lived caching is safe.
CACHE_TTL_SECONDS = 300
_cache: dict[tuple[str, int], tuple[float, list, float]] = {}
_cache_lock = threading.Lock()
cache_stats = {"hits": 0, "misses": 0}

# --- Citation recorder --------------------------------------------------------
# Records the sources and confidence of the most recent retrievals so the
# API can attach citations to a chat reply. Reset at the start of each
# request, read after the agent finishes.
_recorder_lock = threading.Lock()
_recorded_sources: list[dict] = []


def reset_recorded_sources() -> None:
    """Clear the citation recorder (call before handling a new request)."""
    with _recorder_lock:
        _recorded_sources.clear()


def get_recorded_sources() -> list[dict]:
    """Return sources used since the last reset (deduplicated by page)."""
    with _recorder_lock:
        seen: dict[int, dict] = {}
        for src in _recorded_sources:
            # Keep the highest-confidence snippet per page
            page = src["page"]
            if page not in seen or src["confidence"] > seen[page]["confidence"]:
                seen[page] = src
        return sorted(seen.values(), key=lambda s: -s["confidence"])

# Fallback sentence used whenever the context does not contain the answer
NOT_FOUND_MESSAGE = "I couldn't find that information in our restaurant records."

# Prompt for the grounded-answer step: GPT may ONLY use the given context
GROUNDED_ANSWER_PROMPT = """\
You are a helpful assistant for the Flavour & Rush restaurant.
Answer the customer's question using ONLY the context below, which was
retrieved from the restaurant's official knowledge base.

Rules:
- Use only facts stated in the context. Never invent menu items, prices,
  opening hours, addresses, or policies.
- If the context does not contain the answer, reply exactly:
  "{not_found}"
- Be friendly, concise, and natural.

Context:
{context}

Customer question: {question}
"""

# Loaded lazily on first query and cached for the life of the process
_vector_store = None


def _get_store():
    """Load the FAISS index (with its query embedder) once, then reuse it."""
    global _vector_store
    if _vector_store is None:
        # load_vector_store attaches text-embedding-3-small as the query
        # embedder, so similarity_search embeds queries with the right model
        _vector_store = load_vector_store()
    return _vector_store


def _distance_to_confidence(l2_distance: float) -> float:
    """Convert a FAISS L2 distance into a 0..1 confidence score.

    OpenAI embeddings are unit-length, so for two vectors a distance d
    relates to cosine similarity as: cosine = 1 - d²/2. Cosine similarity
    is a natural "how well does this chunk match the question" score:
    1.0 = identical meaning, 0 = unrelated.
    """
    return round(max(0.0, min(1.0, 1.0 - (l2_distance**2) / 2.0)), 3)


def retrieve(query: str, k: int = RETRIEVAL_TOP_K) -> list[Document]:
    """Embed the query and return the top-k most relevant chunks from FAISS.

    Results are cached for CACHE_TTL_SECONDS per (query, k). Each chunk's
    match confidence (0..1) is stored in its metadata as "confidence",
    and all sources are recorded for citation reporting.

    Args:
        query: The user's question in natural language.
        k: How many chunks to retrieve (default 5).

    Returns:
        The k most similar chunk Documents, best match first.

    Raises:
        RuntimeError: If the index cannot be loaded or the search fails
            (e.g. OpenAI embedding call fails).
    """
    cache_key = (query.strip().lower(), k)

    # --- Cache lookup -------------------------------------------------------
    with _cache_lock:
        cached = _cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            cache_stats["hits"] += 1
            _, results, top_confidence = cached
            logger.info("Retrieval cache HIT for %r (confidence=%.2f)", query, top_confidence)
            _record(results)
            return results
        cache_stats["misses"] += 1

    logger.info("Retrieving top %d chunks for query: %r", k, query)

    # --- Steps 1 & 2: embed the query and search the index (with scores) ---
    try:
        scored = _get_store().similarity_search_with_score(query, k=k)
    except Exception as exc:
        logger.exception("Retrieval failed for query %r", query)
        raise RuntimeError(f"Retrieval failed: {exc}") from exc

    # Attach a confidence score to each chunk's metadata
    results = []
    for doc, distance in scored:
        doc.metadata["confidence"] = _distance_to_confidence(float(distance))
        results.append(doc)

    top_confidence = results[0].metadata["confidence"] if results else 0.0
    logger.info(
        "Retrieved %d chunks (pages: %s, top confidence: %.2f)",
        len(results),
        ", ".join(str(doc.metadata.get("page", "?")) for doc in results),
        top_confidence,
    )

    # --- Store in cache and record citations --------------------------------
    with _cache_lock:
        _cache[cache_key] = (time.monotonic() + CACHE_TTL_SECONDS, results, top_confidence)
    _record(results)
    return results


def _record(documents: list[Document]) -> None:
    """Add retrieved chunks to the citation recorder."""
    with _recorder_lock:
        for doc in documents:
            _recorded_sources.append({
                "page": doc.metadata.get("page", -1),
                "snippet": doc.page_content[:120],
                "confidence": doc.metadata.get("confidence", 0.0),
            })


def format_context(documents: list[Document]) -> str:
    """Format retrieved chunks into a single context block for the prompt.

    Each chunk is tagged with its source page so answers are traceable.

    Args:
        documents: Retrieved chunk Documents.

    Returns:
        One string containing all chunks, separated by dividers.
    """
    if not documents:
        return "(no relevant information found)"

    return "\n\n---\n\n".join(
        f"[Source: page {doc.metadata.get('page', '?')} of the knowledge base]\n"
        f"{doc.page_content}"
        for doc in documents
    )


def answer_question(question: str) -> str:
    """Run the full retrieval pipeline and return a grounded answer.

    Args:
        question: The customer's question.

    Returns:
        GPT's answer based only on the retrieved context, or the standard
        fallback sentence when the knowledge base has no answer, or an
        apology if the pipeline itself fails.
    """
    # --- Steps 1 & 2: retrieve the top-5 relevant chunks --------------------
    try:
        documents = retrieve(question)
    except RuntimeError:
        # Already logged inside retrieve(); give the caller a safe message
        return "Sorry, I'm having trouble accessing our restaurant records right now."

    # --- Step 3: build the grounded prompt with the retrieved context -------
    prompt = GROUNDED_ANSWER_PROMPT.format(
        not_found=NOT_FOUND_MESSAGE,
        context=format_context(documents),
        question=question,
    )

    # --- Step 4: ask GPT, constrained to the context -------------------------
    # Temperature 0 keeps the answer strictly factual to the context
    try:
        model = ChatOpenAI(model="gpt-4o", temperature=0)
        response = model.invoke(prompt)
    except Exception:
        logger.exception("GPT answer generation failed for %r", question)
        return "Sorry, I'm having trouble answering right now. Please try again."

    logger.info("Answered question %r using %d chunks", question, len(documents))
    return response.content
