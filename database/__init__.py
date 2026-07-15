"""Local SQLite database for the Restaurant Ordering & Booking Agent.

Stores the transactional data the agent will create at runtime:
customers, orders, reservations, payments, and feedback.
The knowledge base (menu, policies, FAQs) lives separately in the
FAISS vector store — this database is for live business records.
"""
