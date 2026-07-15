"""FastAPI backend for the Flavour & Rush ordering & booking system.

Exposes the whole stack over HTTP:
    - /chat and /voice-chat : talk to the GPT-4o agent (RAG + tools + memory)
    - /order, /order-status : direct structured order endpoints (SQLite)
    - /reservation, /cancel-reservation : reservation endpoints (SQLite)
    - /menu : knowledge-base retrieval (FAISS)
    - /health : component status checks
"""
