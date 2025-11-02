"""
Services module for business logic and external service integrations.

This package contains service modules for various AI-powered features:
- entity_extractor: OpenAI-powered entity extraction from contracts (GPT-4o)
- jurisdiction_analyzer: UK contract law analysis and jurisdiction detection (GPT-4o)
- Future: risk_assessor, summarizer, embeddings, qa_engine (planned for phases 3-5)

Service Pattern:
Each service follows a consistent pattern for reliability and maintainability:
- Uses OpenAI GPT-4o for AI-powered analysis
- Returns tuple of (result, error_message) for clear error handling
- Implements caching for OpenAI client to avoid repeated initialization
- Comprehensive logging and error handling for debugging
- Lazy initialization to prevent import-time failures
"""
