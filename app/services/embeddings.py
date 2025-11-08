"""
Embedding Generation Service

This module provides OpenAI text-embedding-3-small vector generation for semantic search
capabilities. Embeddings are 1536-dimensional vectors used for similarity search with pgvector.

Model: text-embedding-3-small (1536 dimensions)
API: OpenAI Embeddings API
Purpose: Generate semantic vectors for contract clauses to enable similarity-based search

Usage Example:
    from app.services.embeddings import generate_embedding

    embedding_vector, error = generate_embedding("This is a termination clause...")
    if error:
        print(f"Embedding failed: {error}")
    else:
        print(f"Generated {len(embedding_vector)}-dimensional vector")

Requirements:
    - OPENAI_API_KEY must be configured in environment variables
    - Text input should be at least 10 characters for meaningful embeddings
    - Handles truncation automatically for very long texts (>32,000 chars)

Error Handling:
    - Returns tuple (result, error_message) for clear error handling
    - On success: (embedding_vector_list, None)
    - On failure: (None, error_message_string)

Batch Processing:
    - For multiple clauses, use generate_embeddings_batch() for efficiency
    - Reduces API calls and improves performance during bulk operations
"""

import logging
from typing import List, Dict, Any, Optional, Tuple

from app.services.openai_client import get_openai_client

# Module-level logger
logger = logging.getLogger(__name__)

# OpenAI embedding model configuration
EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dimensions, matches Clause.embedding
EMBEDDING_DIMENSIONS = 1536  # Expected dimensions for validation

# Text preprocessing limits
MIN_TEXT_LENGTH = 10  # Minimum characters for meaningful embedding
MAX_TEXT_LENGTH = 32000  # Approximate token limit (8191 tokens ≈ 32,000 chars)


def generate_embedding(text: str) -> Tuple[Optional[List[float]], Optional[str]]:
    """
    Generate OpenAI text-embedding-3-small vector for semantic search.

    Args:
        text: The text to generate an embedding for (clause text or question)

    Returns:
        Tuple of (embedding_vector, error_message):
            - On success: (list of 1536 floats, None)
            - On failure: (None, error message string)

    Error Handling:
        - Returns (None, error) if text is too short or empty
        - Returns (None, error) if OpenAI API call fails
        - Returns (None, error) if API key is missing
        - Returns (None, error) if embedding dimensions don't match expected

    Example:
        >>> embedding, error = generate_embedding("This is a contract clause...")
        >>> if error:
        ...     print(f"Failed: {error}")
        ... else:
        ...     print(f"Success: {len(embedding)} dimensions")
    """
    try:
        # Input validation
        if not text or len(text.strip()) < MIN_TEXT_LENGTH:
            error_msg = f"Text too short for embedding (minimum {MIN_TEXT_LENGTH} characters)"
            logger.warning(error_msg)
            return None, error_msg

        # Text preprocessing
        text = text.strip()
        original_length = len(text)

        # Truncate if exceeds token limit
        if len(text) > MAX_TEXT_LENGTH:
            text = text[:MAX_TEXT_LENGTH]
            logger.warning(
                f"Text truncated from {original_length} to {MAX_TEXT_LENGTH} chars for embedding"
            )

        # Get OpenAI client
        try:
            client = get_openai_client()
        except ValueError as e:
            error_msg = f"OpenAI client configuration error: {str(e)}"
            logger.error(error_msg)
            return None, error_msg

        # Call OpenAI Embeddings API
        logger.debug(f"Generating embedding for text ({len(text)} chars)")
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
            encoding_format="float"
        )

        # Extract embedding vector
        embedding_vector = response.data[0].embedding

        # Validate dimensions
        if len(embedding_vector) != EMBEDDING_DIMENSIONS:
            error_msg = (
                f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, "
                f"got {len(embedding_vector)}"
            )
            logger.error(error_msg)
            return None, error_msg

        logger.debug(f"Successfully generated {len(embedding_vector)}-dimensional embedding")
        return embedding_vector, None

    except ValueError as e:
        # Configuration errors (missing API key, etc.)
        error_msg = f"Configuration error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return None, error_msg

    except Exception as e:
        # Unexpected errors (API errors, network issues, etc.)
        error_msg = f"Unexpected error generating embedding: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return None, error_msg


def generate_embeddings_batch(texts: List[str]) -> Tuple[List[Optional[List[float]]], List[Optional[str]]]:
    """
    Generate embeddings for multiple texts in a single API call for efficiency.

    Args:
        texts: List of text strings to generate embeddings for

    Returns:
        Tuple of (embeddings_list, errors_list):
            - embeddings_list: List of embedding vectors (None for failed texts)
            - errors_list: List of error messages (None for successful texts)
            - Both lists have same length as input texts

    Example:
        >>> texts = ["Clause 1 text", "Clause 2 text", "Clause 3 text"]
        >>> embeddings, errors = generate_embeddings_batch(texts)
        >>> for i, (emb, err) in enumerate(zip(embeddings, errors)):
        ...     if err:
        ...         print(f"Text {i} failed: {err}")
        ...     else:
        ...         print(f"Text {i} success: {len(emb)} dimensions")
    """
    try:
        # Input validation
        if not texts:
            logger.warning("Empty text list provided to generate_embeddings_batch")
            return [], []

        # Filter and preprocess texts
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and len(text.strip()) >= MIN_TEXT_LENGTH:
                # Truncate if needed
                processed_text = text.strip()
                if len(processed_text) > MAX_TEXT_LENGTH:
                    processed_text = processed_text[:MAX_TEXT_LENGTH]
                    logger.warning(f"Text {i} truncated from {len(text)} to {MAX_TEXT_LENGTH} chars")

                valid_texts.append(processed_text)
                valid_indices.append(i)
            else:
                logger.warning(f"Text {i} too short for embedding (minimum {MIN_TEXT_LENGTH} characters)")

        if not valid_texts:
            error_msg = f"No valid texts for embedding (all too short, minimum {MIN_TEXT_LENGTH} chars)"
            logger.warning(error_msg)
            return [None] * len(texts), [error_msg] * len(texts)

        # Get OpenAI client
        try:
            client = get_openai_client()
        except ValueError as e:
            error_msg = f"OpenAI client configuration error: {str(e)}"
            logger.error(error_msg)
            return [None] * len(texts), [error_msg] * len(texts)

        # Call OpenAI Embeddings API with batch
        logger.info(f"Generating embeddings for {len(valid_texts)} texts in batch")
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=valid_texts,
            encoding_format="float"
        )

        # Initialize result lists
        embeddings_list: List[Optional[List[float]]] = [None] * len(texts)
        errors_list: List[Optional[str]] = [None] * len(texts)

        # Process successful embeddings
        successful = 0
        for i, embedding_data in enumerate(response.data):
            original_index = valid_indices[i]
            embedding_vector = embedding_data.embedding

            # Validate dimensions
            if len(embedding_vector) != EMBEDDING_DIMENSIONS:
                error_msg = (
                    f"Embedding dimension mismatch: expected {EMBEDDING_DIMENSIONS}, "
                    f"got {len(embedding_vector)}"
                )
                logger.error(f"Text {original_index}: {error_msg}")
                errors_list[original_index] = error_msg
            else:
                embeddings_list[original_index] = embedding_vector
                successful += 1

        # Mark skipped texts as failed
        for i in range(len(texts)):
            if i not in valid_indices and embeddings_list[i] is None:
                errors_list[i] = f"Text too short for embedding (minimum {MIN_TEXT_LENGTH} characters)"

        failed = len(texts) - successful
        logger.info(
            f"Batch embedding complete: {successful} successful, {failed} failed out of {len(texts)} total"
        )

        return embeddings_list, errors_list

    except ValueError as e:
        # Configuration errors
        error_msg = f"Configuration error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [None] * len(texts), [error_msg] * len(texts)

    except Exception as e:
        # Unexpected errors
        error_msg = f"Unexpected error generating batch embeddings: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [None] * len(texts), [error_msg] * len(texts)
