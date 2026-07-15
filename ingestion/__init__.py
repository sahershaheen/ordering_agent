"""RAG ingestion pipeline for the Flavour & Rush knowledge base.

This package handles the offline data-preparation stage of the RAG system:
loading the restaurant PDF, extracting its text, splitting it into chunks,
and saving those chunks to disk as JSON (ready for a later embedding step).
"""
