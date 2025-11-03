"""
Risk Analyzer Service

This module provides AI-powered risk assessment for legal contracts using OpenAI GPT-4o.
It detects and evaluates risky, unfair, or unusual clauses across multiple risk categories.

Risk Types Covered:
- termination_rights: Unfavorable termination clauses, unilateral termination, inadequate notice periods
- indemnity: Broad indemnification obligations, uncapped indemnities, one-sided indemnity clauses
- penalty: Excessive penalties, liquidated damages, punitive financial terms
- liability_cap: Low liability caps, exclusions of consequential damages, unfair limitation clauses
- payment_terms: Unfavorable payment schedules, late payment penalties, unclear pricing
- intellectual_property: IP ownership disputes, broad IP assignment, unclear licensing terms
- confidentiality: Overly broad confidentiality obligations, indefinite confidentiality periods
- warranty: Excessive warranties, warranty disclaimers, limited warranty protection
- force_majeure: Absence of force majeure clause, narrow force majeure definition
- dispute_resolution: Unfavorable jurisdiction, mandatory arbitration, venue selection issues

Risk Levels:
- high: Significant financial exposure, potential business disruption, legal non-compliance, heavily one-sided terms
- medium: Moderate financial impact, operational inconvenience, ambiguous terms requiring clarification
- low: Minor concerns, standard industry practice with slight unfavorability, easily mitigated risks

Usage Example:
    from app.services.risk_analyzer import analyze_risks

    contract_text = "..."
    clauses = [{"id": 1, "number": "5.2", "title": "Limitation of Liability", "text": "..."}]

    risks, error = analyze_risks(contract_text, contract_id=1, clauses=clauses)
    if error:
        print(f"Analysis failed: {error}")
    else:
        for risk in risks:
            print(f"{risk['risk_level'].upper()}: {risk['description']}")

Note:
- Requires OPENAI_API_KEY environment variable to be set
- Returns tuple of (result_list, error_message) for error handling
- Attempts to match clause references to actual clause IDs for database linking

Disclaimer:
This analysis is for informational purposes only and does not constitute legal advice.
Risk assessments are based on AI analysis and should be validated by qualified legal professionals.
"""

from typing import List, Dict, Any, Optional, Tuple
import json
import logging
import re

from app.services.openai_client import get_openai_client

# Initialize logger
logger = logging.getLogger(__name__)

# Model configuration
MODEL_NAME = "gpt-4o-mini"

# Token optimization settings
MAX_CONTRACT_TEXT_LENGTH = 80000  # Cap contract text at ~80k chars to prevent token overflow

# Risk type definitions
RISK_TYPES = [
    'termination_rights',
    'indemnity',
    'penalty',
    'liability_cap',
    'payment_terms',
    'intellectual_property',
    'confidentiality',
    'warranty',
    'force_majeure',
    'dispute_resolution'
]

# Risk level definitions
RISK_LEVELS = ['low', 'medium', 'high']


def _build_system_prompt() -> str:
    """
    Build the system prompt for risk analysis.

    Returns:
        Comprehensive system prompt instructing the model how to analyze contract risks
    """
    return """You are a legal risk analyst specializing in contract risk assessment.

Your task is to analyze the provided contract text for risky, unfair, or unusual clauses that could potentially harm one party or create legal/financial exposure.

Risk Types to Detect:
1. termination_rights: Unfavorable termination clauses, unilateral termination rights, inadequate notice periods, asymmetric termination terms
2. indemnity: Broad indemnification obligations, uncapped indemnities, one-sided indemnity clauses, unlimited indemnification scope
3. penalty: Excessive penalties, liquidated damages, punitive financial terms, unreasonable late fees
4. liability_cap: Low liability caps, exclusions of consequential damages, unfair limitation clauses, caps below contract value
5. payment_terms: Unfavorable payment schedules, late payment penalties, unclear pricing, unfair advance payment requirements
6. intellectual_property: IP ownership disputes, broad IP assignment clauses, unclear licensing terms, restrictive IP provisions
7. confidentiality: Overly broad confidentiality obligations, indefinite confidentiality periods, unreasonable non-disclosure terms
8. warranty: Excessive warranties, warranty disclaimers, limited warranty protection, disproportionate warranty obligations
9. force_majeure: Absence of force majeure clause, narrow force majeure definition, inadequate force majeure protection
10. dispute_resolution: Unfavorable jurisdiction clauses, mandatory arbitration in inconvenient locations, one-sided venue selection

Risk Levels:
- HIGH: Significant financial exposure (>50% of contract value), potential business disruption, legal non-compliance risk, heavily one-sided terms that could cause serious harm
- MEDIUM: Moderate financial impact (10-50% of contract value), operational inconvenience, ambiguous terms requiring clarification, somewhat unbalanced provisions
- LOW: Minor concerns (<10% of contract value), standard industry practice with slight unfavorability, easily mitigated risks, minor ambiguities

Output Format:
You must return a valid JSON object with the following structure:
{
  "risks": [
    {
      "risk_type": "one of the risk types listed above",
      "risk_level": "low, medium, or high",
      "clause_reference": "specific clause number/title where risk is found (e.g., 'Clause 5.2 - Limitation of Liability')",
      "description": "Clear 2-3 sentence explanation of the specific risk identified",
      "justification": "Detailed 3-5 sentence reasoning for the risk level assessment, citing specific contract language and explaining why this is problematic",
      "recommendation": "Specific 2-3 sentence actionable mitigation strategy (e.g., 'Negotiate to increase liability cap to 100% of contract value')"
    }
  ]
}

Instructions:
- Analyze ALL clauses thoroughly, not just the obvious risks
- Cite specific contract language in your justification
- Be confident in your assessments but note genuine ambiguities
- For each risk, provide a clear clause reference (number and title if available)
- Ensure justifications explain WHY something is risky, not just WHAT the clause says
- Recommendations must be specific and actionable
- Only include genuine risks - do not flag standard reasonable contract terms
- If the contract appears balanced and fair with no significant risks, return an empty risks array

Example Output:
{
  "risks": [
    {
      "risk_type": "liability_cap",
      "risk_level": "high",
      "clause_reference": "Clause 8.3 - Limitation of Liability",
      "description": "The limitation of liability clause caps all damages at £1,000, which is only 2% of the £50,000 contract value. This applies to all damages including direct losses.",
      "justification": "This represents a high risk because the liability cap is drastically below the contract value, leaving the client severely underprotected in case of breach or negligence. Industry standard typically sets liability caps at 100% of contract value or at minimum 50%. The cap covering even direct damages is unusually restrictive and could leave the client unable to recover actual losses. This heavily one-sided term creates significant financial exposure.",
      "recommendation": "Negotiate to increase the liability cap to at least £25,000 (50% of contract value) or preferably match the full contract value. Add carve-outs excluding fraud, willful misconduct, IP infringement, and confidentiality breaches from the cap. Consider separate caps for direct damages (100%) and indirect damages (50%)."
    }
  ]
}"""


def _validate_risk_response(response: Dict[str, Any]) -> bool:
    """
    Validate the structure and content of the risk analysis response.

    Args:
        response: The parsed JSON response from OpenAI

    Returns:
        True if response is valid, False otherwise
    """
    # Check risks array exists
    if "risks" not in response:
        logger.error("Response missing 'risks' key")
        return False

    if not isinstance(response["risks"], list):
        logger.error("'risks' must be a list")
        return False

    # Validate each risk
    for idx, risk in enumerate(response["risks"]):
        # Check required fields exist
        required_fields = ["risk_type", "risk_level", "description", "justification"]
        for field in required_fields:
            if field not in risk:
                logger.error(f"Risk {idx} missing required field: {field}")
                return False

            if not isinstance(risk[field], str) or not risk[field].strip():
                logger.error(f"Risk {idx} field '{field}' must be a non-empty string")
                return False

        # Validate and normalize risk_type (strip whitespace then lowercase)
        normalized_type = risk["risk_type"].strip().lower()
        if normalized_type not in RISK_TYPES:
            logger.error(f"Risk {idx} has invalid risk_type: {risk['risk_type']}")
            return False
        risk["risk_type"] = normalized_type  # Update with normalized value

        # Validate and normalize risk_level (strip whitespace then lowercase)
        normalized_level = risk["risk_level"].strip().lower()
        if normalized_level not in RISK_LEVELS:
            logger.error(f"Risk {idx} has invalid risk_level: {risk['risk_level']}")
            return False
        risk["risk_level"] = normalized_level  # Update with normalized value

        # Check optional fields are strings if present
        if "clause_reference" in risk and not isinstance(risk["clause_reference"], str):
            logger.error(f"Risk {idx} clause_reference must be a string")
            return False

        if "recommendation" in risk and not isinstance(risk["recommendation"], str):
            logger.error(f"Risk {idx} recommendation must be a string")
            return False

    return True


def _match_clause_reference(clause_ref: str, clauses: List[Dict[str, Any]]) -> Optional[int]:
    """
    Attempt to match a clause reference string to an actual clause ID.

    Args:
        clause_ref: The clause reference string from the risk analysis (e.g., "Clause 5.2 - Limitation of Liability")
        clauses: List of clause dictionaries with id, number, title, text fields

    Returns:
        The clause database ID if a match is found, None otherwise
    """
    if not clause_ref or not clauses:
        return None

    clause_ref_lower = clause_ref.lower()

    # First, try exact title match (case-insensitive, trimmed)
    for clause in clauses:
        if clause.get("title"):
            if clause["title"].strip().lower() == clause_ref_lower.strip():
                logger.debug(f"Matched clause reference '{clause_ref}' to clause {clause['id']} by exact title")
                return clause["id"]

    # Try matching by clause number using exact regex extraction
    # Extract the first clause-like number pattern (e.g., "5.2", "10", "3.1.4")
    number_pattern = r'\b(\d+(?:\.\d+)*)\b'
    match = re.search(number_pattern, clause_ref)

    if match:
        extracted_number = match.group(1)
        for clause in clauses:
            if clause.get("number") and clause["number"].strip() == extracted_number:
                logger.debug(f"Matched clause reference '{clause_ref}' to clause {clause['id']} by exact number '{extracted_number}'")
                return clause["id"]

    # Fallback: Try matching by clause title (case-insensitive substring match)
    for clause in clauses:
        if clause.get("title"):
            title_lower = clause["title"].lower()
            if title_lower in clause_ref_lower or clause_ref_lower in title_lower:
                logger.debug(f"Matched clause reference '{clause_ref}' to clause {clause['id']} by title substring '{clause['title']}'")
                return clause["id"]

    logger.debug(f"Could not match clause reference '{clause_ref}' to any clause")
    return None


def analyze_risks(
    contract_text: str,
    contract_id: int,
    clauses: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Analyze a contract for risky, unfair, or unusual clauses using OpenAI GPT-4o.

    This function performs comprehensive risk assessment across 10 risk categories:
    termination rights, indemnities, penalties, liability caps, payment terms,
    intellectual property, confidentiality, warranties, force majeure, and dispute resolution.

    Args:
        contract_text: The full contract text to analyze
        contract_id: The database ID of the contract
        clauses: List of clause dictionaries with id, number, title, text fields
                 (used for matching clause references)

    Returns:
        Tuple of (risk_data_list, error_message):
        - On success: (list of risk dictionaries, None)
        - On failure: ([], error message string)

        Each risk dictionary contains:
        - contract_id: The contract database ID
        - clause_id: The clause database ID if matched, None for contract-level risks
        - risk_type: One of the defined risk types
        - risk_level: 'low', 'medium', or 'high'
        - description: Clear explanation of the risk
        - justification: Detailed reasoning for the risk level
        - recommendation: Actionable mitigation strategy

    Raises:
        Does not raise exceptions - returns errors as tuple values
    """
    try:
        # Input validation
        if not contract_text or len(contract_text.strip()) < 100:
            error_msg = "Contract text is too short for risk analysis (minimum 100 characters)"
            logger.warning(error_msg)
            return [], error_msg

        original_length = len(contract_text)
        logger.info(f"Starting risk analysis for contract {contract_id} ({original_length} chars, {len(clauses)} clauses)")

        # Truncate contract text if it exceeds maximum length to prevent token overflow
        if original_length > MAX_CONTRACT_TEXT_LENGTH:
            contract_text = contract_text[:MAX_CONTRACT_TEXT_LENGTH]
            logger.warning(f"Contract text truncated from {original_length} to {MAX_CONTRACT_TEXT_LENGTH} chars for token optimization")

        # Build clause structure metadata (numbers and titles only) for better clause reference accuracy
        clause_structure = "\n\nContract Clause Structure:\n"
        for clause in clauses:
            number = clause.get("number", "")
            title = clause.get("title", "")
            clause_structure += f"Clause {number} - {title}\n"

        user_prompt = f"""Analyze the following contract for risky, unfair, or unusual clauses.

CONTRACT TEXT:
{contract_text}

{clause_structure}

Provide a comprehensive risk assessment following the instructions in the system prompt."""

        # Get OpenAI client and make API call
        client = get_openai_client()

        logger.info(f"Calling OpenAI API with model {MODEL_NAME} for risk analysis")

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,  # Balance between consistency and nuanced assessment
            max_tokens=4096,  # Limit response length to prevent excessive token usage
            response_format={"type": "json_object"}
        )

        logger.info("OpenAI API call completed successfully")

        # Parse response
        response_content = completion.choices[0].message.content
        response_data = json.loads(response_content)

        # Validate response structure
        if not _validate_risk_response(response_data):
            error_msg = "OpenAI response failed validation"
            logger.error(error_msg)
            return [], error_msg

        risks = response_data["risks"]
        logger.info(f"Successfully parsed {len(risks)} risks from OpenAI response")

        # Enhance risk data with contract_id and clause matching
        risk_data_list = []
        for risk in risks:
            # Normalize risk_type and risk_level (strip whitespace then lowercase)
            risk["risk_type"] = risk["risk_type"].strip().lower()
            risk["risk_level"] = risk["risk_level"].strip().lower()

            # Add contract_id
            risk["contract_id"] = contract_id

            # Attempt to match clause reference to actual clause ID
            clause_ref = risk.get("clause_reference", "")
            clause_id = _match_clause_reference(clause_ref, clauses)
            risk["clause_id"] = clause_id

            # Truncate long descriptions/justifications if needed
            if len(risk["description"]) > 2000:
                risk["description"] = risk["description"][:1997] + "..."

            if len(risk["justification"]) > 2000:
                risk["justification"] = risk["justification"][:1997] + "..."

            # Ensure recommendation exists
            if "recommendation" not in risk or not risk["recommendation"]:
                risk["recommendation"] = ""
            elif len(risk["recommendation"]) > 2000:
                risk["recommendation"] = risk["recommendation"][:1997] + "..."

            risk_data_list.append(risk)

        # Log severity breakdown
        risk_counts = {"high": 0, "medium": 0, "low": 0}
        for risk in risk_data_list:
            level = risk["risk_level"]
            if level in risk_counts:
                risk_counts[level] += 1

        logger.info(f"Risk analysis complete: {len(risk_data_list)} total risks - {risk_counts['high']} high, {risk_counts['medium']} medium, {risk_counts['low']} low")

        return risk_data_list, None

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse OpenAI response as JSON: {str(e)}"
        logger.error(error_msg)
        return [], error_msg

    except ValueError as e:
        error_msg = f"Configuration error: {str(e)}"
        logger.error(error_msg)
        return [], error_msg

    except Exception as e:
        error_msg = f"Unexpected error during risk analysis: {str(e)}"
        logger.exception(error_msg)
        return [], error_msg
