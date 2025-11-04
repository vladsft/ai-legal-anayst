"""
Services module for business logic and external service integrations.

This package contains service modules for various AI-powered features:
- entity_extractor: OpenAI-powered entity extraction from contracts
- jurisdiction_analyzer: UK contract law analysis and jurisdiction detection
- risk_analyzer: Risk assessment for unfair/risky clauses
- summarizer: Plain-language contract summarization with role-specific perspectives
- Future: embeddings, qa_engine (planned for phase 5)

Service Pattern:
Each service follows a consistent pattern for reliability and maintainability:
- Uses OpenAI (GPT-4o for analysis, GPT-4o-mini for summarization)
- Returns tuple of (result, error_message) for clear error handling
- Implements lazy client initialization via get_openai_client()
- Comprehensive logging and error handling for debugging
- Structured JSON output with validation
"""
