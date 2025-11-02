"""
Jurisdiction analysis service using OpenAI GPT-4o.

This module analyzes contracts through UK contract law lens using OpenAI's GPT-4o model.
It detects jurisdiction, identifies applicable UK statutes, maps legal principles, assesses
enforceability, and provides clause-specific interpretations under UK law.

Jurisdiction Focus:
- Primary focus: United Kingdom (England and Wales) contract law
- Detects jurisdiction and confirms if UK law applies
- Identifies relevant UK statutes and legal principles
- Assesses enforceability under UK contract law
- Provides recommendations for UK law compliance

Analysis Components:
- Jurisdiction detection with confidence level
- Applicable UK statutes (Consumer Rights Act, UCTA, etc.)
- Legal principles (formation, interpretation, unfair terms, etc.)
- Overall enforceability assessment
- Clause-specific interpretations with legal reasoning
- Recommendations for compliance

Usage:
    from app.services.jurisdiction_analyzer import analyze_jurisdiction

    analysis, error = analyze_jurisdiction(contract_text, contract_id)
    if error:
        print(f"Analysis failed: {error}")
    else:
        print(f"Jurisdiction: {analysis['jurisdiction_confirmed']}")
        print(f"Confidence: {analysis['confidence']}")

Requirements:
- OPENAI_API_KEY must be set in environment variables
- OpenAI GPT-4o access (ensure sufficient API credits)

Error handling:
- Returns tuple of (analysis_dict, error_message)
- On success: (analysis_dict, None)
- On failure: ({}, error_message_string)
- Logs all errors for debugging and monitoring

DISCLAIMER:
This analysis is for informational purposes only and does NOT constitute legal advice.
Always consult qualified legal professionals for actual legal guidance on contract matters.
"""

from app.services.openai_client import get_openai_client
from app.jurisdictions.uk_config import get_system_prompt, get_user_prompt
from typing import List, Dict, Any, Optional, Tuple
import json
import logging

# Module-level setup
logger = logging.getLogger(__name__)
MODEL_NAME = "gpt-4o"

# Token limit safety thresholds
# GPT-4o has 128k context window, but we want to be conservative
# Assuming ~4 chars per token as rough estimate
MAX_CONTRACT_CHARS = 200000  # ~50k tokens, leaving room for prompts and response
TRUNCATE_TO_CHARS = 150000   # ~37.5k tokens if we need to truncate

# Jurisdiction normalization mapping to canonical codes
# Maps human-readable jurisdiction values to standardized codes
JURISDICTION_MAPPING = {
    'england and wales': 'UK_EW',
    'uk': 'UK_EW',
    'united kingdom': 'UK_EW',
    'scotland': 'UK_SC',
    'northern ireland': 'UK_NI',
    'england': 'UK_EW',
    'wales': 'UK_EW',
    'unknown': 'UNKNOWN',
}


def normalize_jurisdiction(jurisdiction: str) -> str:
    """
    Normalize jurisdiction string to canonical code.

    This function maps freeform jurisdiction values returned by the AI
    to standardized jurisdiction codes for consistent storage and querying.

    Args:
        jurisdiction: Freeform jurisdiction string (e.g., 'England and Wales', 'UK')

    Returns:
        str: Canonical jurisdiction code (e.g., 'UK_EW', 'UK_SC')
               Returns 'UNKNOWN' for None, empty, or non-string inputs

    Examples:
        >>> normalize_jurisdiction('England and Wales')
        'UK_EW'
        >>> normalize_jurisdiction('Scotland')
        'UK_SC'
        >>> normalize_jurisdiction('New York')
        'New York'  # Returns original if no mapping exists
        >>> normalize_jurisdiction(None)
        'UNKNOWN'
        >>> normalize_jurisdiction('')
        'UNKNOWN'
    """
    # Input validation - handle None, non-string, and empty values
    if jurisdiction is None or not isinstance(jurisdiction, str) or jurisdiction.strip() == "":
        logger.warning(f"Invalid jurisdiction input: {repr(jurisdiction)}. Returning 'UNKNOWN'")
        return 'UNKNOWN'

    # Try to find mapping (case-insensitive)
    normalized = JURISDICTION_MAPPING.get(jurisdiction.lower())

    if normalized:
        logger.debug(f"Normalized jurisdiction '{jurisdiction}' to '{normalized}'")
        return normalized

    # Return original if no mapping exists
    logger.debug(f"No normalization mapping found for jurisdiction '{jurisdiction}', using original value")
    return jurisdiction


def _validate_analysis_response(response: Dict[str, Any]) -> bool:
    """
    Validate that the analysis response has required fields and correct structure.

    Args:
        response: The parsed JSON response from OpenAI

    Returns:
        bool: True if valid, False otherwise
    """
    # Check required fields
    required_fields = ['jurisdiction_confirmed', 'confidence', 'enforceability_assessment']
    for field in required_fields:
        if field not in response:
            logger.error(f"Validation failed: Missing required field '{field}'")
            return False
        if not response[field]:
            logger.error(f"Validation failed: Field '{field}' is empty")
            return False

    # Validate confidence level (case-insensitive)
    valid_confidence = ['high', 'medium', 'low']
    if response['confidence'].lower() not in valid_confidence:
        logger.error(f"Validation failed: Invalid confidence level '{response['confidence']}'. Must be one of {valid_confidence}")
        return False

    # Validate optional list fields are actually lists
    list_fields = ['applicable_statutes', 'legal_principles', 'key_considerations',
                   'clause_interpretations', 'recommendations']
    for field in list_fields:
        if field in response and response[field] is not None:
            if not isinstance(response[field], list):
                logger.error(f"Validation failed: Field '{field}' must be a list, got {type(response[field])}")
                return False

    # Validate clause_interpretations items structure
    if 'clause_interpretations' in response and response['clause_interpretations']:
        for idx, item in enumerate(response['clause_interpretations']):
            if not isinstance(item, dict):
                logger.error(f"Validation failed: clause_interpretations[{idx}] must be a dict, got {type(item)}")
                return False

            # Check required fields in each clause interpretation
            if 'clause' not in item or not item['clause']:
                logger.error(f"Validation failed: clause_interpretations[{idx}] missing or empty 'clause' field")
                return False

            if 'interpretation' not in item or not item['interpretation']:
                logger.error(f"Validation failed: clause_interpretations[{idx}] missing or empty 'interpretation' field")
                return False

            # Validate types
            if not isinstance(item['clause'], str):
                logger.error(f"Validation failed: clause_interpretations[{idx}]['clause'] must be a string")
                return False

            if not isinstance(item['interpretation'], str):
                logger.error(f"Validation failed: clause_interpretations[{idx}]['interpretation'] must be a string")
                return False

    logger.info("Analysis response validation passed")
    return True


def analyze_jurisdiction(contract_text: str, contract_id: int) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Analyze contract through UK contract law lens using OpenAI GPT-4o.

    This function performs comprehensive jurisdiction analysis including:
    - Jurisdiction detection and confirmation
    - Identification of applicable UK statutes
    - Mapping of relevant legal principles
    - Overall enforceability assessment under UK law
    - Clause-specific interpretations with legal reasoning
    - Recommendations for UK law compliance

    Args:
        contract_text: The full contract text to analyze
        contract_id: Database ID of the contract being analyzed

    Returns:
        Tuple containing:
        - Dictionary with analysis results (jurisdiction, statutes, principles, etc.)
        - Error message string if analysis failed, None if successful

    Example:
        >>> analysis, error = analyze_jurisdiction(contract_text, contract_id=1)
        >>> if error:
        ...     print(f"Analysis failed: {error}")
        >>> else:
        ...     print(f"Jurisdiction: {analysis['jurisdiction_confirmed']}")
        ...     print(f"Confidence: {analysis['confidence']}")
        ...     for statute in analysis['applicable_statutes']:
        ...         print(f"  - {statute}")

    Response Structure:
        {
            'contract_id': 1,
            'jurisdiction_confirmed': 'England and Wales',
            'confidence': 'high',
            'applicable_statutes': ['Consumer Rights Act 2015', 'UCTA 1977', ...],
            'legal_principles': ['Freedom of contract', 'Contra proferentem', ...],
            'enforceability_assessment': 'The contract appears generally enforceable...',
            'key_considerations': ['Limitation clause may be subject to reasonableness...'],
            'clause_interpretations': [
                {
                    'clause': 'Clause 5 - Limitation of Liability',
                    'interpretation': 'Under UCTA 1977, this clause must satisfy...'
                }
            ],
            'recommendations': ['Consider adding explicit force majeure clause...']
        }
    """
    # Input validation
    if not contract_text or len(contract_text.strip()) < 100:
        error_msg = "Contract text is empty or too short for jurisdiction analysis (minimum 100 characters)"
        logger.warning(error_msg)
        return {}, error_msg

    # Token limit safety check
    original_length = len(contract_text)
    truncated = False
    if original_length > MAX_CONTRACT_CHARS:
        logger.warning(
            f"Contract {contract_id} exceeds safe size limit ({original_length} > {MAX_CONTRACT_CHARS} chars). "
            f"Truncating to {TRUNCATE_TO_CHARS} chars for jurisdiction analysis."
        )
        contract_text = contract_text[:TRUNCATE_TO_CHARS]
        truncated = True

    try:
        logger.info(
            f"Starting jurisdiction analysis for contract {contract_id} "
            f"(length: {len(contract_text)} chars{', truncated from ' + str(original_length) if truncated else ''})"
        )

        # Get or create OpenAI client (lazy initialization)
        client = get_openai_client()

        # Build prompts from UK config
        system_prompt = get_system_prompt()
        user_prompt = get_user_prompt(contract_text)

        logger.debug("Calling OpenAI API for jurisdiction analysis")

        # Call OpenAI API
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,  # Slightly higher than entity extraction for nuanced legal reasoning
            response_format={"type": "json_object"}  # Enforce JSON output (GPT-4o feature)
        )

        # Extract response
        response_content = completion.choices[0].message.content
        logger.debug(f"Received response from OpenAI (first 200 chars): {response_content[:200]}...")

        # Parse JSON
        response_data = json.loads(response_content)

        # Validate response structure
        if not _validate_analysis_response(response_data):
            error_msg = "OpenAI response failed validation - missing required fields or invalid structure"
            logger.error(error_msg)
            return {}, error_msg

        # Build analysis dict with validated data and defaults for optional fields
        # Normalize confidence to lowercase for consistency
        # Store both raw jurisdiction and normalized code
        raw_jurisdiction = response_data['jurisdiction_confirmed']
        normalized_jurisdiction = normalize_jurisdiction(raw_jurisdiction)

        analysis_data = {
            'contract_id': contract_id,
            'jurisdiction_confirmed': raw_jurisdiction,  # Keep human-readable in analysis
            'jurisdiction_code': normalized_jurisdiction,  # Add normalized code
            'confidence': response_data['confidence'].lower(),
            'applicable_statutes': response_data.get('applicable_statutes', []),
            'legal_principles': response_data.get('legal_principles', []),
            'enforceability_assessment': response_data['enforceability_assessment'],
            'key_considerations': response_data.get('key_considerations', []),
            'clause_interpretations': response_data.get('clause_interpretations', []),
            'recommendations': response_data.get('recommendations', [])
        }

        jurisdiction = analysis_data['jurisdiction_confirmed']
        confidence = analysis_data['confidence']
        logger.info(f"Successfully analyzed jurisdiction for contract {contract_id}: {jurisdiction} (confidence: {confidence})")

        return analysis_data, None

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse JSON response from OpenAI: {e}"
        logger.error(error_msg)
        return {}, error_msg

    except ValueError as e:
        # Catch configuration errors (missing API key, etc.)
        error_msg = str(e)
        logger.error(error_msg)
        return {}, error_msg

    except Exception as e:
        # Catch OpenAI API errors and any other unexpected errors
        error_msg = f"Jurisdiction analysis failed: {type(e).__name__}: {e}"
        logger.error(error_msg, exc_info=True)
        return {}, error_msg
