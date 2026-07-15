"""Tools available to ordering_agent.

Grouped by concern:
    - knowledge.py    : RAG search over the Flavour & Rush knowledge base
    - orders.py       : placing and tracking orders (SQLite)
    - reservations.py : booking, retrieving and cancelling reservations (SQLite)
"""

from agent.tools.knowledge import search_knowledge_base
from agent.tools.orders import place_order, track_order
from agent.tools.reservations import (
    book_reservation,
    cancel_reservation,
    get_reservations,
    modify_reservation,
)

# The complete toolbox handed to the agent
ALL_TOOLS = [
    search_knowledge_base,
    place_order,
    track_order,
    book_reservation,
    get_reservations,
    modify_reservation,
    cancel_reservation,
]
