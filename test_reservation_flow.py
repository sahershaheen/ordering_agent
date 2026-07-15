"""Scripted test of the full reservation lifecycle.

Covers: booking (with special requests collected), viewing, modifying,
and cancelling a reservation.

Usage:
    uv run python test_reservation_flow.py
"""

from agent.ordering_agent import build_agent

CONFIG = {"configurable": {"thread_id": "reservation-flow-test"}}

TURNS = [
    # Book: agent should collect all details including special requests
    "Hi, I'd like to book a table for this Saturday the 18th of July at 8 pm. "
    "We'll be 6 people. Name is Bilal Raza, phone +92-333-4455667.",
    # Special request answer -> booking should be saved
    "Yes actually, it's my wife's birthday — can we get a birthday arrangement?",
    # View
    "Can you show me my reservation details?",
    # Modify: change time and guest count
    "Actually, can we make it 9 pm instead, and we'll be 8 people now.",
    # Cancel
    "Ah sorry, plans changed completely. Please cancel the reservation.",
    # Verify cancelled
    "Can you double check it's cancelled?",
]


def main() -> None:
    agent = build_agent()

    for turn in TURNS:
        print("\n" + "=" * 70)
        print(f"CUSTOMER: {turn}")
        result = agent.invoke(
            {"messages": [{"role": "user", "content": turn}]}, CONFIG
        )
        print(f"\nAGENT: {result['messages'][-1].content}")


if __name__ == "__main__":
    main()
