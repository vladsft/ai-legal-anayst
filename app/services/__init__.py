"""
Services module for business logic and external service integrations.

This package contains service modules for various AI-powered features:
- entity_extractor: OpenAI-powered entity extraction from contracts
- jurisdiction_analyzer: UK contract law analysis and jurisdiction detection
- risk_analyzer: Risk assessment for unfair/risky clauses
- summarizer: Plain-language contract summarization with role-specific perspectives
- embeddings: OpenAI text-embedding-3-small vector generation for semantic search
- qa_engine: Interactive Q&A with semantic search and GPT-4o-mini answer generation

Service Pattern:
Each service follows a consistent pattern for reliability and maintainability:
- Uses OpenAI (GPT-4o for analysis, GPT-4o-mini for summarization and Q&A, text-embedding-3-small for embeddings)
- Returns tuple of (result, error_message) for clear error handling
- Implements lazy client initialization via get_openai_client()
- Comprehensive logging and error handling for debugging
- Structured JSON output with validation (where applicable)
"""
