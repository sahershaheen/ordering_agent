"""Scripted test of the complete ordering workflow.

Simulates a hesitant customer so the agent has to guide them through
every step: menu -> recommendation -> quantity -> delivery -> address/phone
-> payment -> confirmation -> saved order -> summary with estimated time.

Usage:
    uv run python test_order_flow.py
"""

from agent.ordering_agent import build_agent

CONFIG = {"configurable": {"thread_id": "order-flow-test"}}

TURNS = [
    # 1. Customer asks for food (vague, so the agent must show the menu)
    "Hi, I'm hungry. What do you have?",
    # 2-3. Customer is unsure, agent should recommend
    "Hmm, I can't decide. I like spicy food. What do you recommend?",
    # 4. Customer picks; agent should confirm quantity
    "The Firecracker Burger sounds great, I'll take that.",
    # Quantity answer + agent should ask delivery or takeaway
    "Make it two please.",
    # 5-6. Delivery, so the agent should ask for address and phone
    "Delivery please.",
    "Address is Flat 3, Block C, Gulberg 3, Lahore. Phone +92-321-9998877. My name is Sara Ahmed.",
    # 7. Payment method (one of the five mock options)
    "I'll pay with JazzCash.",
    # 8-11. Confirm -> order saved -> summary + estimated delivery time
    "Yes, that's all correct. Confirm the order.",
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
