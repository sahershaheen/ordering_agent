"""Interactive terminal chat with ordering_agent.

Usage:
    uv run python chat.py

Type your messages; type 'exit' or 'quit' to leave.
"""

import sys
import uuid

from agent.memory import chat
from agent.ordering_agent import build_agent


def main() -> None:
    # Build the agent (loads the FAISS index lazily on first question)
    try:
        agent = build_agent()
    except Exception as exc:
        print(f"Failed to start the agent: {exc}")
        sys.exit(1)

    # A fresh session id per CLI run gives this conversation its own memory
    session_id = f"cli-{uuid.uuid4().hex[:8]}"

    print("=" * 60)
    print("  Flavour & Rush — Ordering & Booking Assistant")
    print("  (type 'exit' to quit)")
    print("=" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break

        # Send the message within this session; chat() handles errors
        # internally and always returns a printable reply
        print(f"\nAgent: {chat(agent, session_id, user_input)}")

    print("\nGoodbye!")


if __name__ == "__main__":
    main()
