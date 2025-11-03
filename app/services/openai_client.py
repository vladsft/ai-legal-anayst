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
import threading

# Module-level setup
logger = logging.getLogger(__name__)

# Cache the OpenAI client to avoid recreating it on every call
_client_cache = None

# Thread-safe initialization lock
_client_init_lock = threading.Lock()


def get_openai_client() -> OpenAI:
    """
    Get or create cached OpenAI client with thread-safe initialization.

    This lazy initialization prevents import-time failures when environment
    configuration is missing. The client is cached after first creation to
    avoid repeated instantiation overhead. Uses double-checked locking to
    ensure thread safety when multiple threads call this function concurrently.

    Returns:
        OpenAI: Configured OpenAI client instance

    Raises:
        ValueError: If OPENAI_API_KEY is not configured

    Thread Safety:
        This function is thread-safe. Multiple concurrent calls will result in
        only one client initialization, with all callers receiving the same
        cached instance.

    Example:
        >>> from app.services.openai_client import get_openai_client
        >>> client = get_openai_client()
        >>> completion = client.chat.completions.create(
        ...     model="gpt-4o-mini",
        ...     messages=[{"role": "user", "content": "Hello"}]
        ... )
    """
    global _client_cache

    # First check (without lock) - fast path for already-initialized client
    if _client_cache is None:
        # Acquire lock for initialization
        with _client_init_lock:
            # Second check (with lock) - ensure another thread didn't initialize while we waited
            if _client_cache is None:
                try:
                    # Get settings and validate API key
                    settings = get_settings()
                    if not settings.openai_api_key:
                        raise ValueError(
                            "OPENAI_API_KEY is not configured. Please set the OPENAI_API_KEY "
                            "environment variable to use AI-powered features."
                        )

                    # Create OpenAI client
                    _client_cache = OpenAI(api_key=settings.openai_api_key)
                    logger.info("OpenAI client initialized successfully")

                except Exception as e:
                    logger.error(f"Failed to initialize OpenAI client: {e}")
                    raise ValueError(
                        f"Failed to initialize OpenAI client: {e}. "
                        "Ensure OPENAI_API_KEY is set in your environment."
                    ) from e

    return _client_cache
