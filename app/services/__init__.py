"""
Services module for business logic and external service integrations.

This package contains service modules for various AI-powered features:
- entity_extractor: OpenAI-powered entity extraction from contracts (GPT-4o)
- jurisdiction_analyzer: UK contract law analysis and jurisdiction detection (GPT-4o)
- risk_analyzer: Risk assessment for unfair/risky clauses (GPT-4o)
- Future: summarizer, embeddings, qa_engine (planned for phases 4-5)

Service Pattern:
Each service follows a consistent pattern for reliability and maintainability:
- Uses OpenAI GPT-4o for AI-powered analysis
- Returns tuple of (result, error_message) for clear error handling
- Implements lazy client initialization via get_openai_client()
- Comprehensive logging and error handling for debugging
- Structured JSON output with validation
"""
