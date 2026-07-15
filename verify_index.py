"""Quick check that the saved FAISS index reloads and answers queries.

Simulates a restart: loads the index from disk (no rebuilding) and runs
a sample similarity search against it.
"""

from ingestion.vector_store import load_vector_store

if __name__ == "__main__":
    # Load the persisted index exactly as the agent would after a restart
    vector_store = load_vector_store()

    # Run a sample query; the question is embedded via OpenAI at query time
    query = "What are the opening hours of the Johar Town branch?"
    results = vector_store.similarity_search(query, k=2)

    print(f"\nQuery: {query}\n")
    for result in results:
        print(f"--- page {result.metadata['page']}, chunk {result.metadata['chunk_id']} ---")
        print(result.page_content[:300])
        print()
