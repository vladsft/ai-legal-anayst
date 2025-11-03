"""
Entity extraction service using OpenAI GPT-4o.

This module extracts structured entities from legal contracts using OpenAI's GPT-4o model.
It identifies and extracts key information such as parties, dates, financial terms, governing
laws, and obligations.

Entity types supported:
- party: Legal entities involved (companies, individuals, organizations)
- date: Important dates (effective date, termination date, deadlines, milestones)
- financial_term: Monetary amounts, payment terms, pricing, fees, penalties
- governing_law: Applicable laws, jurisdictions, dispute resolution venues
- obligation: Key duties and responsibilities of each party

Usage:
    from app.services.entity_extractor import extract_entities

    entities = extract_entities(contract_text)
    # Returns list of dicts with entity_type, value, context, confidence

Requirements:
- OPENAI_API_KEY must be set in environment variables
- OpenAI GPT-4o access (ensure sufficient API credits)

Error handling:
- Returns empty list on failures (API errors, parsing errors, etc.)
- Logs all errors for debugging and monitoring
"""

from app.services.openai_client import get_openai_client
from typing import List, Dict, Any, Optional
import json
import logging

# Module-level setup
logger = logging.getLogger(__name__)
MODEL_NAME = "gpt-4o-mini"

# Entity type definitions
ENTITY_TYPES = ['party', 'date', 'financial_term', 'governing_law', 'obligation']


def _build_system_prompt() -> str:
    """
    Build the system prompt for the OpenAI model.

    Returns:
        Comprehensive system prompt instructing the model to extract entities.
    """
    return """You are a legal contract analyst specializing in entity extraction.

Your task is to extract key entities from contract text and return them in a structured JSON format.

Entity Types to Extract:

1. **party**: Legal entities involved in the contract
   - Examples: "Acme Corporation", "John Smith", "ABC Ltd."
   - Include both primary parties and any mentioned third parties

2. **date**: Important dates mentioned in the contract
   - Examples: "January 1, 2024", "within 30 days", "December 31, 2025"
   - Include effective dates, termination dates, deadlines, milestones
   - Capture both absolute dates and relative time periods

3. **financial_term**: Monetary amounts and payment-related terms
   - Examples: "$50,000", "5% annual interest", "monthly fee of £1,000"
   - Include prices, fees, penalties, payment schedules, interest rates

4. **governing_law**: Applicable laws and jurisdictions
   - Examples: "State of California", "English law", "New York courts"
   - Include governing law clauses, jurisdiction, dispute resolution venues

5. **obligation**: Key duties and responsibilities of parties
   - Examples: "maintain confidentiality", "deliver services within 30 days", "provide monthly reports"
   - Include both affirmative obligations (must do) and negative obligations (must not do)

Output Format:

Return a JSON object with an "entities" key containing an array of entity objects.
Each entity object must have:
- entity_type: One of [party, date, financial_term, governing_law, obligation]
- value: The extracted text (keep it concise, typically 1-10 words)
- context: Surrounding text (1-2 sentences) showing where this appears in the contract
- confidence: Your confidence level ["high", "medium", "low"]
  - "high": Explicitly and clearly stated
  - "medium": Implied or requires minor interpretation
  - "low": Ambiguous or uncertain

Example Output:
{
  "entities": [
    {
      "entity_type": "party",
      "value": "Acme Corporation",
      "context": "This Agreement is entered into between Acme Corporation and Beta Inc.",
      "confidence": "high"
    },
    {
      "entity_type": "date",
      "value": "January 1, 2024",
      "context": "This Agreement shall commence on January 1, 2024.",
      "confidence": "high"
    },
    {
      "entity_type": "financial_term",
      "value": "$50,000 annual fee",
      "context": "Client agrees to pay a $50,000 annual fee for services rendered.",
      "confidence": "high"
    }
  ]
}

Guidelines:
- Be thorough and extract ALL relevant entities
- Prioritize accuracy over quantity
- Keep values concise and specific
- Provide meaningful context for each entity
- Be consistent with confidence levels
"""


def extract_entities(contract_text: str) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Extract entities from contract text using OpenAI GPT-4o.

    Args:
        contract_text: The full contract text to analyze

    Returns:
        Tuple containing:
        - List of entity dictionaries with keys: entity_type, value, context, confidence
        - Error message string if extraction failed, None if successful

    Example:
        >>> entities, error = extract_entities("This Agreement between Acme Corp and Beta Inc...")
        >>> if error:
        ...     print(f"Extraction failed: {error}")
        >>> else:
        ...     print(entities[0])
        {
            'entity_type': 'party',
            'value': 'Acme Corp',
            'context': 'This Agreement between Acme Corp and Beta Inc...',
            'confidence': 'high'
        }
    """
    # Input validation
    if not contract_text or len(contract_text.strip()) < 50:
        error_msg = "Contract text is empty or too short for entity extraction"
        logger.warning(error_msg)
        return [], error_msg

    try:
        logger.info(f"Starting entity extraction for contract (length: {len(contract_text)} chars)")

        # Get or create OpenAI client (lazy initialization)
        client = get_openai_client()

        # Build user prompt
        user_prompt = f"""Extract all entities from the following contract text:

{contract_text}

Remember to return a JSON object with an "entities" array containing all extracted entities."""

        # Call OpenAI API
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,  # Low temperature for consistent, deterministic results
            response_format={"type": "json_object"}  # Enforce JSON output (GPT-4o feature)
        )

        # Extract response
        response_content = completion.choices[0].message.content
        logger.debug(f"Received response from OpenAI: {response_content[:200]}...")

        # Parse JSON
        response_data = json.loads(response_content)

        # Validate response structure
        if "entities" not in response_data:
            error_msg = "OpenAI response missing 'entities' key"
            logger.error(error_msg)
            return [], error_msg

        entities = response_data["entities"]
        if not isinstance(entities, list):
            error_msg = f"OpenAI response 'entities' is not a list: {type(entities)}"
            logger.error(error_msg)
            return [], error_msg

        # Validate and clean each entity
        validated_entities = []
        for entity in entities:
            # Check required fields
            if "entity_type" not in entity or "value" not in entity:
                logger.warning(f"Skipping entity missing required fields: {entity}")
                continue

            # Validate entity type
            entity_type = entity["entity_type"]
            if entity_type not in ENTITY_TYPES:
                logger.warning(f"Skipping entity with invalid type '{entity_type}': {entity}")
                continue

            # Default confidence if missing
            if "confidence" not in entity or not entity["confidence"]:
                entity["confidence"] = "medium"

            # Truncate context if too long
            if "context" in entity and entity["context"] and len(entity["context"]) > 500:
                entity["context"] = entity["context"][:497] + "..."

            validated_entities.append(entity)

        logger.info(f"Successfully extracted {len(validated_entities)} entities")
        return validated_entities, None

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON response from OpenAI: {e}"
        logger.error(error_msg)
        return [], error_msg

    except ValueError as e:
        # Catch configuration errors (missing API key, etc.)
        error_msg = str(e)
        logger.error(error_msg)
        return [], error_msg

    except Exception as e:
        # Catch OpenAI API errors and any other unexpected errors
        error_msg = f"Entity extraction failed: {type(e).__name__}: {e}"
        logger.error(error_msg)
        return [], error_msg
