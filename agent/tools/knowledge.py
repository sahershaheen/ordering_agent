"""RAG tool: search the Flavour & Rush knowledge base.

This is the ONLY source the agent may use for restaurant facts
(menu, prices, hours, branches, policies, promotions, FAQs).

The heavy lifting (query embedding, FAISS search, context formatting)
lives in the shared retrieval pipeline: retrieval/retriever.py.
"""

from langchain_core.tools import tool

from ingestion.logger import get_logger
from retrieval.retriever import format_context, retrieve

logger = get_logger(__name__)


@tool
def search_knowledge_base(query: str) -> str:
    """Search the Flavour & Rush restaurant knowledge base.

    Use this for EVERY restaurant fact: menu items, prices, ingredients,
    opening hours, branch addresses, delivery zones, policies, promotions,
    discounts and FAQs. Never state a restaurant fact without checking it
    here first.

    Args:
        query: A natural-language search query, e.g. "burger menu prices"
            or "opening hours Johar Town branch".

    Returns:
        The most relevant knowledge-base passages, or a message saying
        nothing relevant was found.
    """
    # Run the shared retrieval pipeline: embed query -> FAISS -> top-5 chunks
    try:
        documents = retrieve(query)
    except RuntimeError:
        # Full error was logged inside retrieve(); give the model a clean message
        return "The knowledge base is currently unavailable. Apologise to the customer."

    if not documents:
        return "No relevant information found in the restaurant records."

    # Format the chunks (with page sources) for the model to read
    return format_context(documents)
