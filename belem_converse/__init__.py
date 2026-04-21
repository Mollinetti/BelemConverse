"""BelemConverse backend package.

Deterministic place discovery for Belém do Pará. Pipeline:
    Query -> TF-IDF intent + slot extraction (planner)
        -> Deterministic retrieval (open-hours -> proximity -> category -> rank)
        -> LLM summarization (no hallucination, summarizer-only)

Public modules:
    cities       - City profiles (Belém by default)
    classifiers  - TF-IDF intent classifier
    core         - Query planner, retrievers, ranking, tour planner, RAG agent
    ingest       - CSV ingestion + vector store + OSM helpers
    tools        - Operational scripts (data refresh, etc.)
    utils        - Config, models, exceptions, helpers
"""

__version__ = "1.0.0"
