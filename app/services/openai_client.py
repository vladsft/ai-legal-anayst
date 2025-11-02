"""
Shared OpenAI client management module.

This module provides a centralized, cached OpenAI client instance for use
across all AI-powered services (entity extraction, jurisdiction analysis, etc.).

Usage:
    from app.services.openai_client import get_openai_client

    client = get_openai_client()
    completion = client.chat.completions.create(...)

Benefits:
- Single source of truth for OpenAI client configuration
- Lazy initialization to prevent import-time failures
- Client caching to avoid repeated instantiation overhead
- Consistent error handling across services
"""

from openai import OpenAI
from app.config import get_settings
import logging

# Module-level setup
logger = logging.getLogger(__name__)

# Cache the OpenAI client to avoid recreating it on every call
_client_cache = None


def get_openai_client() -> OpenAI:
    """
    Get or create cached OpenAI client.

    This lazy initialization prevents import-time failures when environment
    configuration is missing. The client is cached after first creation to
    avoid repeated instantiation overhead.

    Returns:
        OpenAI: Configured OpenAI client instance

    Raises:
        ValueError: If OPENAI_API_KEY is not configured

    Example:
        >>> from app.services.openai_client import get_openai_client
        >>> client = get_openai_client()
        >>> completion = client.chat.completions.create(
        ...     model="gpt-4o",
        ...     messages=[{"role": "user", "content": "Hello"}]
        ... )
    """
    global _client_cache

    if _client_cache is None:
        try:
            settings = get_settings()
            if not settings.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY is not configured. Please set the OPENAI_API_KEY "
                    "environment variable to use AI-powered features."
                )
            _client_cache = OpenAI(api_key=settings.openai_api_key)
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise ValueError(
                f"Failed to initialize OpenAI client: {e}. "
                "Ensure OPENAI_API_KEY is set in your environment."
            ) from e

    return _client_cache
