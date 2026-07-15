"""CLI for the standalone retrieval pipeline: ask one grounded question.

Usage:
    uv run python ask.py "What are the opening hours of the DHA branch?"

This runs the full pipeline (query embedding -> FAISS top-5 -> GPT answer)
without the ordering agent — useful for testing retrieval quality directly.
"""

import sys

from retrieval.retriever import answer_question

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: uv run python ask.py "your question here"')
        sys.exit(1)

    # Everything after the script name is treated as the question
    question = " ".join(sys.argv[1:])
    print(f"\nQuestion: {question}")
    print(f"\nAnswer: {answer_question(question)}")
