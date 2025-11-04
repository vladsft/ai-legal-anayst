"""
Contract Summarization Service

This module provides plain-language summarization of legal contracts using OpenAI GPT-4o-mini.
Translates complex legal jargon into clear, accessible language for non-lawyers.

Role Options:
    - 'supplier': Summary from supplier/vendor perspective highlighting obligations, risks, and opportunities
    - 'client': Summary from client/buyer perspective highlighting protections, rights, and concerns
    - 'neutral' or None: Balanced overview without favoring either party

Usage Example:
    from app.services.summarizer import summarize_contract

    # Neutral summary
    summary, error = summarize_contract(contract_text, contract_id=1)

    # Client perspective
    summary, error = summarize_contract(contract_text, contract_id=1, role='client')

    if error:
        print(f"Error: {error}")
    else:
        print(f"Summary: {summary['summary']}")
        print(f"Key Points: {summary['key_points']}")

Requirements:
    - OPENAI_API_KEY environment variable must be set
    - Contract text should be at least 100 characters

Error Handling:
    Returns tuple (result_dict, error_message):
    - On success: (summary_dict, None)
    - On failure: ({}, error_message_string)

Legal Disclaimer:
    Summaries are for informational purposes only and do NOT constitute legal advice.
    AI-generated summaries may not capture all nuances or important details.
    Always review full contracts and consult qualified legal professionals.
"""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.services.openai_client import get_openai_client

# Module-level setup
logger = logging.getLogger(__name__)

# Model configuration
MODEL_NAME = "gpt-4o-mini"  # Cost-optimized model for summarization
MAX_CONTRACT_TEXT_LENGTH = 80000  # Same as risk_analyzer for consistency

# Valid role options
VALID_ROLES = ['supplier', 'client', 'neutral']


def _build_system_prompt(role: Optional[str]) -> str:
    """
    Build role-specific system prompt for contract summarization.

    Args:
        role: Optional role perspective ('supplier', 'client', 'neutral', or None)

    Returns:
        System prompt string tailored to the specified role
    """
    base_prompt = """You are an expert legal contract analyst specializing in creating plain-language summaries of legal contracts.

Your task is to translate complex legal jargon into clear, accessible language that non-lawyers can understand. Focus on extracting and explaining the most important information in a straightforward, concise manner.

"""

    # Add role-specific perspective
    if role == 'supplier':
        role_context = """Focus on what matters to the SUPPLIER/VENDOR:
- Highlight supplier obligations, deliverables, and performance requirements
- Emphasize payment terms, timing, and conditions
- Point out supplier rights, protections, and limitations of liability
- Identify risks and potential issues for the supplier
- Note any favorable or unfavorable terms from supplier perspective
"""
    elif role == 'client':
        role_context = """Focus on what matters to the CLIENT/BUYER:
- Highlight client protections, rights, and entitlements
- Emphasize what the client is receiving and guarantees
- Point out client obligations and payment commitments
- Identify risks and potential issues for the client
- Note any favorable or unfavorable terms from client perspective
"""
    else:  # neutral or None
        role_context = """Provide a BALANCED, NEUTRAL perspective:
- Present information objectively without favoring either party
- Highlight key terms and conditions fairly
- Explain obligations and rights for all parties equally
- Identify potential concerns for all stakeholders
- Maintain impartiality throughout the summary
"""

    output_format = """
Provide your analysis as a structured JSON object with the following fields:

{
    "summary": "Main plain-language summary (3-5 well-structured paragraphs explaining the contract's purpose, key terms, and overall structure)",
    "key_points": ["List of 5-10 most important points from the contract, in order of significance"],
    "parties": "Brief description of the parties involved (who is contracting with whom)",
    "key_dates": ["List of important dates, deadlines, milestones, and time periods"],
    "financial_terms": "Clear summary of payment terms, amounts, schedules, and any financial penalties or incentives",
    "obligations": {
        "supplier": ["Key obligations and responsibilities of the supplier/vendor"],
        "client": ["Key obligations and responsibilities of the client/buyer"]
    },
    "rights": {
        "supplier": ["Key rights and protections for the supplier"],
        "client": ["Key rights and protections for the client"]
    },
    "termination": "Explanation of how and when the contract can be terminated, including notice periods and conditions",
    "risks": ["Top 3-5 risks or concerns to be aware of - brief overview, not detailed legal analysis"],
    "confidence": "Your confidence in the summary quality: 'high', 'medium', or 'low'"
}

Guidelines:
- Use clear, simple language that a non-lawyer can understand
- Avoid legal jargon where possible; if you must use legal terms, explain them
- Be concise but comprehensive - capture all important information
- Use specific examples and numbers rather than vague statements
- Structure information logically and prioritize what matters most
- Ensure the summary is actionable and useful for decision-making
- If information is not present in the contract, use null or omit that field

Remember: Your goal is to make this contract accessible and understandable to someone without legal training.
"""

    return base_prompt + role_context + output_format


def _validate_summary_response(response: Dict[str, Any]) -> bool:
    """
    Validate the structure and content of the AI summary response.

    Args:
        response: Parsed JSON response from OpenAI

    Returns:
        True if response is valid, False otherwise
    """
    # Check required fields
    if 'summary' not in response:
        logger.error("Validation failed: Missing 'summary' field")
        return False

    if 'key_points' not in response:
        logger.error("Validation failed: Missing 'key_points' field")
        return False

    # Validate summary is non-empty string
    if not isinstance(response['summary'], str) or not response['summary'].strip():
        logger.error("Validation failed: 'summary' must be a non-empty string")
        return False

    # Validate key_points is a list with at least 3 items
    if not isinstance(response['key_points'], list) or len(response['key_points']) < 3:
        logger.error("Validation failed: 'key_points' must be a list with at least 3 items")
        return False

    # Validate optional fields have correct types if present
    optional_string_fields = ['parties', 'financial_terms', 'termination', 'confidence']
    for field in optional_string_fields:
        if field in response and response[field] is not None:
            if not isinstance(response[field], str):
                logger.error(f"Validation failed: '{field}' must be a string if present")
                return False

    optional_list_fields = ['key_dates', 'risks']
    for field in optional_list_fields:
        if field in response and response[field] is not None:
            if not isinstance(response[field], list):
                logger.error(f"Validation failed: '{field}' must be a list if present")
                return False

    optional_dict_fields = ['obligations', 'rights']
    for field in optional_dict_fields:
        if field in response and response[field] is not None:
            if not isinstance(response[field], dict):
                logger.error(f"Validation failed: '{field}' must be a dict if present")
                return False

    return True


def summarize_contract(
    contract_text: str,
    contract_id: int,
    role: Optional[str] = None
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Generate a plain-language summary of a legal contract using OpenAI GPT-4o-mini.

    This function translates complex legal jargon into clear, accessible language.
    Supports role-specific perspectives to highlight relevant information for different stakeholders.

    Args:
        contract_text: Full text of the contract to summarize
        contract_id: Database ID of the contract
        role: Optional role perspective ('supplier', 'client', 'neutral', or None for neutral)

    Returns:
        Tuple of (summary_dict, error_message):
        - On success: (summary_dict with all fields, None)
        - On failure: ({}, error_message_string)

    Summary Dict Fields:
        - summary: Main plain-language summary (3-5 paragraphs)
        - key_points: List of 5-10 most important points
        - parties: Brief description of parties involved
        - key_dates: Important dates and deadlines
        - financial_terms: Payment terms and amounts
        - obligations: Key obligations by party
        - rights: Key rights by party
        - termination: Termination conditions
        - risks: Top 3-5 risks to be aware of
        - contract_id: Contract database ID
        - role: Role used for perspective
        - summary_type: 'contract_overview' or 'role_specific'

    Example:
        summary, error = summarize_contract(contract_text, 1, role='client')
        if error:
            print(f"Error: {error}")
        else:
            print(summary['summary'])
            print(summary['key_points'])
    """
    try:
        # Input validation - check text length
        if not contract_text or len(contract_text.strip()) < 100:
            error_msg = "Contract text is too short for summarization (minimum 100 characters)"
            logger.warning(f"Contract {contract_id}: {error_msg}")
            return {}, error_msg

        # Validate and normalize role parameter
        if role is not None:
            role = role.strip().lower()
            if role not in VALID_ROLES:
                error_msg = f"Invalid role: {role}. Must be one of: {', '.join(VALID_ROLES)}"
                logger.error(f"Contract {contract_id}: {error_msg}")
                return {}, error_msg

            # Treat 'neutral' as None (default behavior)
            if role == 'neutral':
                role = None

        # Log the summarization request
        logger.info(f"Starting summarization for contract {contract_id} with role: {role or 'neutral'}")

        # Truncate contract text if needed to prevent token overflow
        if len(contract_text) > MAX_CONTRACT_TEXT_LENGTH:
            logger.warning(
                f"Contract {contract_id} text ({len(contract_text)} chars) exceeds maximum "
                f"({MAX_CONTRACT_TEXT_LENGTH} chars). Truncating."
            )
            contract_text = contract_text[:MAX_CONTRACT_TEXT_LENGTH]

        # Get OpenAI client (lazy initialization, thread-safe)
        client = get_openai_client()

        # Build system prompt with role-specific instructions
        system_prompt = _build_system_prompt(role)

        # Build user prompt with contract text and role context
        if role:
            user_prompt = f"""Please analyze the following contract from the {role.upper()} perspective and provide a comprehensive plain-language summary.

Contract Text:
{contract_text}

Remember to focus on what matters most to the {role}, while maintaining clarity and accessibility for non-lawyers."""
        else:
            user_prompt = f"""Please analyze the following contract and provide a comprehensive plain-language summary with a balanced, neutral perspective.

Contract Text:
{contract_text}

Remember to maintain objectivity and clarity for non-lawyers."""

        # Call OpenAI API
        logger.info(f"Calling OpenAI API (model: {MODEL_NAME}) for contract {contract_id}")

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Balanced consistency with natural language
            max_tokens=2048,  # Keep summaries concise and focused
            response_format={"type": "json_object"}  # Structured JSON output
        )

        logger.info(f"OpenAI API call completed for contract {contract_id}")

        # Extract and parse response
        response_content = completion.choices[0].message.content
        summary_data = json.loads(response_content)

        # Validate response structure
        if not _validate_summary_response(summary_data):
            error_msg = "AI response validation failed - incomplete or invalid summary structure"
            logger.error(f"Contract {contract_id}: {error_msg}")
            return {}, error_msg

        # Add metadata to response
        summary_data['contract_id'] = contract_id
        summary_data['role'] = role
        summary_data['summary_type'] = 'role_specific' if role else 'contract_overview'

        # Log successful summarization
        logger.info(
            f"Successfully generated {summary_data['summary_type']} summary for contract {contract_id} "
            f"(role: {role or 'neutral'}, confidence: {summary_data.get('confidence', 'unknown')})"
        )

        return summary_data, None

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse AI response as JSON: {str(e)}"
        logger.error(f"Contract {contract_id}: {error_msg}", exc_info=True)
        return {}, error_msg

    except ValueError as e:
        error_msg = f"Configuration or validation error: {str(e)}"
        logger.error(f"Contract {contract_id}: {error_msg}", exc_info=True)
        return {}, error_msg

    except Exception as e:
        error_msg = f"Unexpected error during summarization: {str(e)}"
        logger.error(f"Contract {contract_id}: {error_msg}", exc_info=True)
        return {}, error_msg
