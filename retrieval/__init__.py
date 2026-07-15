"""Retrieval pipeline for the Flavour & Rush knowledge base.

Turns a user question into an embedding (text-embedding-3-small),
searches the FAISS index for the top matching chunks, and passes them
to GPT so every restaurant answer is grounded in retrieved context.
"""
