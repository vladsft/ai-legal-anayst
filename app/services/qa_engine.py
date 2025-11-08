"""
Q&A Engine Service

This module provides interactive question-answering capabilities using semantic search
and GPT-4o-mini. It combines pgvector similarity search with AI-powered answer generation
to enable natural language queries about contract content.

How It Works:
    1. Generate query embedding: Convert user's question to vector using text-embedding-3-small
    2. Semantic search: Find top 5 most similar clauses using pgvector L2 distance
    3. Build context: Format retrieved clauses as context for AI
    4. Generate answer: Use GPT-4o-mini to generate comprehensive answer from context
    5. Link clauses: Return database IDs of clauses used in the answer

Model: GPT-4o-mini with temperature 0.2
Search: pgvector L2 distance similarity (top 5 clauses)
Embeddings: text-embedding-3-small (1536 dimensions)

Usage Example:
    from app.services.qa_engine import answer_question
    from app.database import get_db

    db = next(get_db())
    question = "Can the client terminate the contract early?"
    contract_text = "..."

    qa_data, error = answer_question(db, contract_id=1, question=question, contract_text=contract_text)
    if error:
        print(f"Q&A failed: {error}")
    else:
        print(f"Answer: {qa_data['answer']}")
        print(f"Referenced clauses: {qa_data['referenced_clause_ids']}")
        print(f"Confidence: {qa_data['confidence']}")

Requirements:
    - OPENAI_API_KEY must be configured in environment variables
    - Clauses must have embeddings generated (done automatically during upload)
    - Contract must exist in database with segmented clauses

Error Handling:
    - Returns tuple (result, error_message) for clear error handling
    - On success: (qa_dict, None)
    - On failure: ({}, error_message_string)

Legal Disclaimer:
    Answers are for informational purposes only and do NOT constitute legal advice.
    AI-generated answers are based on semantic search and may not capture all relevant
    clauses or nuances. Always review the full contract and consult qualified legal
    professionals for actual legal guidance.
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.services.openai_client import get_openai_client
from app.services.embeddings import generate_embedding
from app.models import Clause

# Module-level logger
logger = logging.getLogger(__name__)

# OpenAI model configuration
MODEL_NAME = "gpt-4o-mini"

# Semantic search configuration
TOP_K_CLAUSES = 5  # Number of most similar clauses to retrieve
SIMILARITY_THRESHOLD = 0.7  # Minimum similarity score (0-1 range, not currently enforced)

# Input validation
MIN_QUESTION_LENGTH = 10  # Minimum characters for a valid question (matches embedding requirement)

# Context building
MAX_CONTEXT_LENGTH = 6000  # Maximum context length in characters (leave room for answer)


def _build_system_prompt() -> str:
    """
    Build comprehensive system prompt for Q&A assistant.

    Returns:
        System prompt string instructing GPT-4o-mini on Q&A behavior
    """
    return """You are a legal contract Q&A assistant that answers questions about contracts using provided clause context.

Your task is to:
1. Carefully read the question and the provided contract clauses
2. Identify which clauses are relevant to answering the question
3. Synthesize a clear, comprehensive answer based on the clause content
4. Cite specific clauses used in your answer
5. Assess your confidence based on clause relevance and clarity

Output Format (JSON):
{
  "answer": "Clear, comprehensive answer to the question (2-4 paragraphs). Cite specific clause numbers when referencing terms.",
  "confidence": "high/medium/low",
  "referenced_clause_indices": [list of 0-based indices of clauses used in the answer],
  "explanation": "Brief explanation of how you derived the answer and why you chose this confidence level"
}

Confidence Levels:
- HIGH: Answer is directly supported by clear, unambiguous clauses; all aspects of question are addressed
- MEDIUM: Answer is supported by clauses but requires some interpretation; some aspects may be implicit
- LOW: Answer is partially supported or requires significant interpretation; relevant clauses are vague or incomplete

Example Output:
{
  "answer": "Yes, the client can terminate the contract early under specific conditions outlined in Clause 8.2. The contract allows for early termination with 30 days written notice if the supplier fails to meet performance standards or breaches material terms. Additionally, Clause 8.3 permits termination for convenience with 90 days notice, though this requires payment of a termination fee equal to 25% of remaining contract value.",
  "confidence": "high",
  "referenced_clause_indices": [1, 2],
  "explanation": "The answer is directly supported by two clear termination clauses that explicitly address the question. Both clauses provide specific conditions, notice periods, and consequences."
}

Important Guidelines:
- referenced_clause_indices should contain 0-based indices (0, 1, 2, etc.) corresponding to the clauses provided in the context
- Only include indices of clauses that were actually used to derive the answer
- Be accurate and precise - only reference information actually present in the clauses
- If the answer is not found in the provided clauses, state that clearly
- Use clear, professional language suitable for legal contract discussion
- Always cite specific clause numbers when referencing contract terms
- Be comprehensive but concise (2-4 paragraphs maximum)
- If the question is ambiguous or has multiple interpretations, address the most likely interpretation
"""


def _search_similar_clauses(
    db: Session,
    contract_id: int,
    query_embedding: List[float],
    top_k: int = TOP_K_CLAUSES
) -> List[Clause]:
    """
    Search for most similar clauses using pgvector L2 distance.

    This performs semantic similarity search using pgvector's L2 distance operator
    to find clauses most relevant to the user's question.

    Args:
        db: Database session
        contract_id: Contract database ID
        query_embedding: Question embedding vector (1536 dimensions)
        top_k: Number of most similar clauses to retrieve (default 5)

    Returns:
        List of Clause objects ordered by similarity (most similar first)

    Note:
        Uses pgvector's L2 distance operator (<->) for similarity search.
        Only returns clauses that have embeddings (embedding IS NOT NULL).
    """
    # Query clauses with embeddings, ordered by L2 distance to query embedding
    clauses = db.query(Clause).filter(
        Clause.contract_id == contract_id,
        Clause.embedding.isnot(None)
    ).order_by(
        Clause.embedding.l2_distance(query_embedding)
    ).limit(top_k).all()

    logger.debug(f"Found {len(clauses)} similar clauses for contract {contract_id}")
    return clauses


def _parse_answer_for_clause_mentions(
    answer: str,
    number_to_id_mapping: Dict[str, int],
    title_to_id_mapping: Dict[str, int]
) -> List[int]:
    """
    Parse the answer text for mentions of clause numbers or titles.

    This lightweight heuristic attempts to identify which clauses were actually
    referenced in the answer by looking for clause number patterns and title mentions.

    Args:
        answer: The generated answer text
        number_to_id_mapping: Map of clause numbers to database IDs
        title_to_id_mapping: Map of clause titles to database IDs

    Returns:
        List of clause database IDs mentioned in the answer
    """
    mentioned_clause_ids = []

    # Search for clause number patterns in the answer text
    # Matches patterns like "Clause 2.1", "clause 8", "Section 3.4", etc.
    clause_number_pattern = r'\b(?:[Cc]lause|[Ss]ection)\s+(\d+(?:\.\d+)*)\b'
    matches = re.finditer(clause_number_pattern, answer)

    for match in matches:
        clause_number = match.group(1)
        if clause_number in number_to_id_mapping:
            db_id = number_to_id_mapping[clause_number]
            if db_id not in mentioned_clause_ids:
                mentioned_clause_ids.append(db_id)

    # Search for clause title mentions (case-insensitive partial match)
    for title, db_id in title_to_id_mapping.items():
        # Only check titles with at least 3 characters to avoid false positives
        if len(title) >= 3 and title.lower() in answer.lower():
            if db_id not in mentioned_clause_ids:
                mentioned_clause_ids.append(db_id)

    return mentioned_clause_ids


def _validate_qa_response(response: Dict[str, Any]) -> bool:
    """
    Validate Q&A response structure from GPT-4o-mini.

    Args:
        response: Parsed JSON response from OpenAI

    Returns:
        True if response is valid, False otherwise
    """
    # Check required fields
    if not response.get("answer"):
        logger.error("Q&A response missing 'answer' field")
        return False

    if not isinstance(response.get("answer"), str):
        logger.error("Q&A response 'answer' field must be string")
        return False

    # Validate confidence level
    confidence = response.get("confidence", "").lower()
    if confidence not in ["high", "medium", "low"]:
        logger.error(f"Invalid confidence level: {confidence} (must be high/medium/low)")
        return False

    # Validate referenced_clause_indices (optional but must be list if present)
    if "referenced_clause_indices" in response:
        if not isinstance(response["referenced_clause_indices"], list):
            logger.error("Q&A response 'referenced_clause_indices' must be list")
            return False

    return True


def answer_question(
    db: Session,
    contract_id: int,
    question: str,
    contract_text: str
) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Answer a natural language question about a contract using semantic search and AI.

    This function orchestrates the entire Q&A process:
    1. Validates question input
    2. Generates embedding for the question
    3. Searches for most similar clauses using pgvector
    4. Builds context from retrieved clauses
    5. Uses GPT-4o-mini to generate answer from context
    6. Returns structured Q&A data with clause references

    Args:
        db: Database session
        contract_id: Contract database ID
        question: User's natural language question
        contract_text: Full contract text (for context if needed)

    Returns:
        Tuple of (qa_dict, error_message):
            - On success: (qa_data_dict, None)
            - On failure: ({}, error_message_string)

        qa_data_dict contains:
            - answer: Comprehensive answer to the question
            - confidence: Confidence level (high/medium/low)
            - referenced_clause_ids: List of clause database IDs used
            - explanation: Brief explanation of answer derivation
            - contract_id: Contract database ID

    Example:
        >>> qa_data, error = answer_question(db, 1, "What are the payment terms?", contract_text)
        >>> if error:
        ...     print(f"Failed: {error}")
        ... else:
        ...     print(f"Answer: {qa_data['answer']}")
        ...     print(f"Confidence: {qa_data['confidence']}")
        ...     print(f"Referenced clauses: {qa_data['referenced_clause_ids']}")
    """
    try:
        # Input validation
        if not question or len(question.strip()) < MIN_QUESTION_LENGTH:
            error_msg = f"Question too short (minimum {MIN_QUESTION_LENGTH} characters)"
            logger.warning(error_msg)
            return {}, error_msg

        question = question.strip()
        logger.info(f"Processing Q&A for contract {contract_id}: {question[:100]}...")

        # Generate query embedding
        query_embedding, embedding_error = generate_embedding(question)
        if embedding_error:
            error_msg = f"Failed to generate question embedding: {embedding_error}"
            logger.error(error_msg)
            return {}, error_msg

        logger.debug("Successfully generated query embedding")

        # Semantic search for similar clauses
        similar_clauses = _search_similar_clauses(db, contract_id, query_embedding, TOP_K_CLAUSES)

        if not similar_clauses:
            error_msg = "No clause embeddings found for this contract. Contract may not have been fully processed."
            logger.warning(error_msg)
            return {}, error_msg

        logger.info(f"Retrieved {len(similar_clauses)} similar clauses")

        # Build context from retrieved clauses with ordered list and mapping
        context_parts = []
        index_to_id_mapping = {}  # Map 0-based indices to database IDs
        number_to_id_mapping = {}  # Map clause numbers to database IDs
        title_to_id_mapping = {}  # Map clause titles to database IDs

        for i, clause in enumerate(similar_clauses):
            # Format: "[0] Clause 2.1 - Termination:\n<text>\n\n"
            clause_number = clause.number or f"Clause {i+1}"
            clause_title = clause.title or "Untitled"
            context_parts.append(f"[{i}] {clause_number} - {clause_title}:\n{clause.text}\n")

            # Store mappings for later reference
            index_to_id_mapping[i] = clause.id
            if clause.number:
                number_to_id_mapping[clause.number] = clause.id
            if clause.title:
                title_to_id_mapping[clause.title] = clause.id

        context = "\n".join(context_parts)

        # Truncate context if too long
        if len(context) > MAX_CONTEXT_LENGTH:
            context = context[:MAX_CONTEXT_LENGTH]
            logger.warning(f"Context truncated to {MAX_CONTEXT_LENGTH} characters")

        # Get OpenAI client
        try:
            client = get_openai_client()
        except ValueError as e:
            error_msg = f"OpenAI client configuration error: {str(e)}"
            logger.error(error_msg)
            return {}, error_msg

        # Build prompts
        system_prompt = _build_system_prompt()
        user_prompt = f"""Question: {question}

Relevant Contract Clauses:
{context}

Please answer the question based on the provided clauses. Return your response in the JSON format specified in the system prompt."""

        # Call OpenAI API
        logger.debug("Calling OpenAI API for answer generation")
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,  # Balance between consistency and natural language
            max_tokens=1024,  # Answers should be concise (2-4 paragraphs)
            response_format={"type": "json_object"}  # Structured JSON output
        )

        # Extract and parse response
        response_content = completion.choices[0].message.content
        logger.debug(f"Received OpenAI response: {len(response_content)} characters")

        qa_response = json.loads(response_content)

        # Validate response structure
        if not _validate_qa_response(qa_response):
            error_msg = "Invalid Q&A response structure from OpenAI"
            logger.error(error_msg)
            return {}, error_msg

        # Normalize confidence to lowercase
        qa_response["confidence"] = qa_response.get("confidence", "medium").lower()

        # Map clause references to database IDs with refined selection logic
        # Prefer model-provided references, then text parsing heuristic, then top-K fallback
        referenced_clause_ids = []
        ai_clause_indices = qa_response.get("referenced_clause_indices", [])
        answer_text = qa_response.get("answer", "")

        if ai_clause_indices:
            # Priority 1: Use model-provided indices
            for idx in ai_clause_indices:
                if isinstance(idx, int):
                    # Try 0-based first (as specified in prompt)
                    if idx in index_to_id_mapping:
                        db_id = index_to_id_mapping[idx]
                        if db_id not in referenced_clause_ids:
                            referenced_clause_ids.append(db_id)
                    # Try 1-based as fallback (in case model uses 1-based indexing)
                    elif (idx - 1) in index_to_id_mapping and idx > 0:
                        db_id = index_to_id_mapping[idx - 1]
                        if db_id not in referenced_clause_ids:
                            referenced_clause_ids.append(db_id)
                    else:
                        logger.warning(f"Invalid clause index {idx} (max index: {len(similar_clauses) - 1})")
            logger.info(f"Using {len(referenced_clause_ids)} model-provided clause indices")
        else:
            # Priority 2: Attempt lightweight heuristic - parse answer for clause mentions
            parsed_clause_ids = _parse_answer_for_clause_mentions(
                answer_text,
                number_to_id_mapping,
                title_to_id_mapping
            )

            if parsed_clause_ids:
                referenced_clause_ids = parsed_clause_ids
                logger.info(
                    f"No indices provided, parsed {len(referenced_clause_ids)} clause mentions from answer text"
                )
            else:
                # Priority 3: Last fallback - use top 2-3 most similar clauses
                fallback_count = min(3, len(similar_clauses))
                referenced_clause_ids = [similar_clauses[i].id for i in range(fallback_count)]
                logger.info(
                    f"No references found, using top {fallback_count} most similar clauses as fallback"
                )

        qa_response["referenced_clause_ids"] = referenced_clause_ids
        qa_response["contract_id"] = contract_id

        logger.info(
            f"Successfully generated answer with {len(referenced_clause_ids)} referenced clauses "
            f"(confidence: {qa_response['confidence']})"
        )

        return qa_response, None

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse OpenAI JSON response: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {}, error_msg

    except ValueError as e:
        error_msg = f"Configuration error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {}, error_msg

    except Exception as e:
        error_msg = f"Unexpected error during Q&A: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {}, error_msg
