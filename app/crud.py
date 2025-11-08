"""
CRUD (Create, Read, Update, Delete) operations for database entities.

This module provides reusable database operations for contracts and clauses.
These functions abstract SQLAlchemy operations and will be used by FastAPI
endpoints throughout the application phases.

Error handling notes:
- Functions raise SQLAlchemy exceptions on database errors
- DuplicateClauseError is raised for unique constraint violations (duplicate clause IDs)
- FastAPI exception handlers will catch these and return appropriate HTTP responses
- Callers should wrap CRUD operations in try/except blocks as needed
"""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import func
from app.models import Contract, Clause, Entity, Summary, RiskAssessment, QAHistory
from app.services.embeddings import generate_embeddings_batch
import json
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Custom Exceptions
# ============================================================================


class DuplicateClauseError(ValueError):
    """
    Raised when attempting to create a clause that violates the unique
    constraint on (contract_id, clause_id).

    This exception is chained from the original IntegrityError to preserve
    DBAPI details while providing a more specific exception type for handlers.
    """
    pass


# ============================================================================
# Contract CRUD Operations
# ============================================================================


def create_contract(
    db: Session,
    title: Optional[str],
    text: str,
    jurisdiction: Optional[str] = None
) -> Contract:
    """
    Create a new contract record in the database.

    This will be called from the /contracts/segment endpoint in phase 1
    to persist uploaded contracts before segmentation.

    Args:
        db: Database session
        title: Optional contract name/title
        text: Full contract text content
        jurisdiction: Optional jurisdiction code (e.g., 'UK', 'US_NY')

    Returns:
        Contract: Created contract object with auto-generated ID

    Raises:
        SQLAlchemyError: On database operation failure
    """
    contract = Contract(
        title=title,
        text=text,
        jurisdiction=jurisdiction,
        status="pending"
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def get_contract(db: Session, contract_id: int) -> Optional[Contract]:
    """
    Retrieve a contract by ID.

    This will be used by all analysis endpoints to fetch contract data
    for entity extraction, risk assessment, summarization, and Q&A.

    Args:
        db: Database session
        contract_id: Contract primary key

    Returns:
        Contract object if found, None otherwise
    """
    return db.query(Contract).filter(Contract.id == contract_id).first()


def get_contracts(
    db: Session,
    skip: int = 0,
    limit: int = 100
) -> List[Contract]:
    """
    Retrieve all contracts with pagination.

    This enables listing all contracts, useful for future admin interface
    or contract management features.

    Args:
        db: Database session
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return

    Returns:
        List of contract objects
    """
    return db.query(Contract).offset(skip).limit(limit).all()


def update_contract_status(
    db: Session,
    contract_id: int,
    status: str,
    processed_at: Optional[datetime] = None
) -> Optional[Contract]:
    """
    Update contract processing status.

    This tracks progress through the processing pipeline (pending ->
    processing -> completed/failed). Useful for monitoring and error handling.

    Args:
        db: Database session
        contract_id: Contract primary key
        status: New status value (pending/processing/completed/failed)
        processed_at: Optional timestamp when processing completed

    Returns:
        Updated contract object if found, None otherwise
    """
    contract = get_contract(db, contract_id)
    if contract:
        contract.status = status
        if processed_at:
            contract.processed_at = processed_at
        db.commit()
        db.refresh(contract)
    return contract


def update_contract_jurisdiction(
    db: Session,
    contract_id: int,
    jurisdiction: str
) -> Optional[Contract]:
    """
    Update contract jurisdiction after analysis.

    This will be called from phase 2 jurisdiction analysis endpoint to
    store the detected jurisdiction code.

    Args:
        db: Database session
        contract_id: Contract primary key
        jurisdiction: Jurisdiction code (e.g., 'UK', 'US_NY')

    Returns:
        Updated contract object if found, None otherwise
    """
    contract = get_contract(db, contract_id)
    if contract:
        contract.jurisdiction = jurisdiction
        db.commit()
        db.refresh(contract)
    return contract


def delete_contract(db: Session, contract_id: int) -> bool:
    """
    Delete a contract and all related data.

    Cascade deletion automatically removes all related clauses, entities,
    risk assessments, summaries, and Q&A history records.

    Args:
        db: Database session
        contract_id: Contract primary key

    Returns:
        True if deleted, False if contract not found
    """
    contract = get_contract(db, contract_id)
    if contract:
        db.delete(contract)
        db.commit()
        return True
    return False


# ============================================================================
# Clause CRUD Operations
# ============================================================================


def create_clause(
    db: Session,
    contract_id: int,
    clause_id: str,
    number: Optional[str],
    title: Optional[str],
    text: str
) -> Clause:
    """
    Create a new clause record.

    This will be called from the updated /contracts/segment endpoint in
    phase 1 to persist segmented clauses to the database.

    IMPORTANT: This function enforces a unique constraint on (contract_id, clause_id).
    If a clause with the same contract_id and clause_id already exists, a
    DuplicateClauseError will be raised (chained from the original IntegrityError).
    Callers should handle this exception to detect duplicate clause insertions.

    Args:
        db: Database session
        contract_id: Parent contract ID
        clause_id: UUID identifier from segmentation logic
        number: Clause number (e.g., '2.1')
        title: Clause heading text
        text: Full clause body text

    Returns:
        Clause: Created clause object with auto-generated ID

    Raises:
        DuplicateClauseError: If clause with same (contract_id, clause_id) already exists
        IntegrityError: For other constraint violations
        SQLAlchemyError: On other database operation failures
    """
    clause = Clause(
        contract_id=contract_id,
        clause_id=clause_id,
        number=number,
        title=title,
        text=text
    )
    db.add(clause)
    try:
        db.commit()
        db.refresh(clause)
        return clause
    except IntegrityError as e:
        db.rollback()
        # Raise custom exception with context while preserving original IntegrityError
        if "uq_clauses_contract_clause" in str(e):
            raise DuplicateClauseError(
                f"Clause with clause_id '{clause_id}' already exists for contract {contract_id}. "
                f"The (contract_id, clause_id) pair must be unique."
            ) from e
        # Re-raise other integrity errors as-is to preserve DBAPI details
        raise


def get_clauses_by_contract(db: Session, contract_id: int) -> List[Clause]:
    """
    Retrieve all clauses for a contract.

    This retrieves segmented clauses for analysis, risk assessment,
    and semantic search operations.

    Args:
        db: Database session
        contract_id: Parent contract ID

    Returns:
        List of clause objects for the specified contract
    """
    return db.query(Clause).filter(Clause.contract_id == contract_id).all()


def bulk_create_clauses(db: Session, clauses: List[Clause]) -> None:
    """
    Efficiently insert multiple clauses in a single transaction and generate embeddings.

    This optimizes insertion of multiple clauses from segmentation,
    reducing database round-trips. After clause insertion, automatically generates
    OpenAI text-embedding-3-small vectors (1536 dimensions) for each clause to enable
    semantic search capabilities.

    IMPORTANT LIMITATIONS:
    - This function uses `bulk_save_objects()` which does NOT populate
      auto-generated primary keys (IDs) on the clause objects after insert.
    - SQLAlchemy events (e.g., before_insert, after_insert) will NOT fire.
    - If you need access to the generated IDs immediately after insertion,
      use `db.add_all(clauses); db.commit()` instead.
    - This is a performance optimization for cases where IDs are not needed
      immediately and events are not required.

    UNIQUE CONSTRAINT ENFORCEMENT:
    - This function enforces the unique constraint on (contract_id, clause_id).
    - If any clause violates the constraint, the entire transaction is rolled back
      and a DuplicateClauseError is raised (chained from the original IntegrityError).
    - Callers should handle DuplicateClauseError to detect duplicate clauses.

    EMBEDDING GENERATION:
    - After clause insertion, embeddings are automatically generated for all clauses
    - Uses OpenAI text-embedding-3-small (1536 dimensions) for semantic search
    - Embedding failures are non-fatal and logged as warnings
    - Clauses without embeddings can still be used but won't appear in semantic search

    Alternative approach when IDs are needed:
        for clause in clauses:
            db.add(clause)
        db.commit()
        # Now clause.id is populated for each clause

    Args:
        db: Database session
        clauses: List of Clause objects to insert

    Raises:
        DuplicateClauseError: If any clause violates unique constraint (contract_id, clause_id)
        IntegrityError: For other constraint violations
        SQLAlchemyError: On other database operation failures

    Note:
        Callers should not expect clause.id to be populated after this call.
        If IDs are needed, query the database again or use add_all() instead.
        Embedding generation is automatic and non-fatal (failures logged but don't raise exceptions).
    """
    try:
        db.bulk_save_objects(clauses)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        # Raise custom exception with context while preserving original IntegrityError
        if "uq_clauses_contract_clause" in str(e):
            raise DuplicateClauseError(
                "One or more clauses violate the unique constraint on (contract_id, clause_id). "
                "Ensure all clause_id values are unique within each contract. "
                "The entire batch has been rolled back."
            ) from e
        # Re-raise other integrity errors as-is to preserve DBAPI details
        raise

    # Generate embeddings for all clauses after successful insertion
    # Note: We need to query the clauses back to get their database IDs since bulk_save_objects
    # doesn't populate IDs on the objects
    logger.info(f"Generating embeddings for {len(clauses)} clauses")

    # Build a single IN filter to query all inserted clauses in one DB call
    clause_filters = [(clause.contract_id, clause.clause_id) for clause in clauses]

    # Query all inserted clauses using IN filter on (contract_id, clause_id)
    from sqlalchemy import tuple_
    db_clauses = db.query(Clause).filter(
        tuple_(Clause.contract_id, Clause.clause_id).in_(clause_filters)
    ).all()

    if len(db_clauses) != len(clauses):
        logger.warning(
            f"Retrieved {len(db_clauses)} clauses from database but expected {len(clauses)}"
        )

    # Build list of texts in order and call batch embedding generation
    clause_texts = [db_clause.text for db_clause in db_clauses]
    embeddings_list, errors_list = generate_embeddings_batch(clause_texts)

    # Iterate over results and set embeddings for successful items
    successful_embeddings = 0
    failed_embeddings = 0

    for i, (db_clause, embedding_vector, error) in enumerate(zip(db_clauses, embeddings_list, errors_list)):
        if error:
            # Log warning but don't fail - embeddings are optional
            logger.warning(
                f"Failed to generate embedding for clause {db_clause.clause_id} "
                f"(contract {db_clause.contract_id}): {error}"
            )
            failed_embeddings += 1
        else:
            # Update clause with embedding
            db_clause.embedding = embedding_vector
            successful_embeddings += 1

    # Commit all embedding updates once after the loop
    try:
        db.commit()
        logger.info(
            f"Embedding generation complete: {successful_embeddings} successful, "
            f"{failed_embeddings} failed out of {len(clauses)} total clauses"
        )
    except Exception as e:
        # If embedding updates fail, log but don't raise - clauses are already created
        logger.error(f"Failed to save embeddings to database: {str(e)}")
        db.rollback()


# ============================================================================
# Entity CRUD Operations
# ============================================================================


def create_entity(
    db: Session,
    contract_id: int,
    entity_type: str,
    value: str,
    context: Optional[str] = None,
    confidence: Optional[str] = None
) -> Entity:
    """
    Create a new entity record.

    This will be called from the updated /contracts/segment endpoint to
    persist extracted entities from OpenAI GPT-4o analysis.

    Args:
        db: Database session
        contract_id: Parent contract ID
        entity_type: Type of entity (party/date/financial_term/governing_law/obligation)
        value: Extracted entity value
        context: Optional surrounding text providing context
        confidence: Optional confidence level (high/medium/low)

    Returns:
        Entity: Created entity object with auto-generated ID

    Raises:
        ValueError: If entity_type is None or empty
        SQLAlchemyError: On database operation failure
    """
    if not entity_type:
        raise ValueError("entity_type is required and cannot be empty")

    entity = Entity(
        contract_id=contract_id,
        entity_type=entity_type.lower(),  # Normalize to lowercase for consistent querying
        value=value,
        context=context,
        confidence=confidence
    )
    db.add(entity)
    try:
        db.commit()
        db.refresh(entity)
    except SQLAlchemyError:
        db.rollback()
        raise
    return entity


def bulk_create_entities(db: Session, entities: List[Entity]) -> None:
    """
    Efficiently insert multiple entities in a single transaction.

    This optimizes insertion of multiple entities from extraction results,
    reducing database round-trips. Unlike bulk_save_objects, this uses
    add_all() to populate auto-generated IDs on entity objects.

    Args:
        db: Database session
        entities: List of Entity objects to insert

    Raises:
        IntegrityError: For constraint violations (e.g., foreign key)
        SQLAlchemyError: On other database operation failures

    Note:
        On failure, the entire transaction is rolled back. Handle exceptions
        appropriately in calling code.
    """
    try:
        db.add_all(entities)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise


def get_entities_by_contract(db: Session, contract_id: int) -> List[Entity]:
    """
    Retrieve all entities for a contract.

    This retrieves all extracted entities for the GET /contracts/{id}/entities
    endpoint, allowing users to view all entities found in a contract.

    Args:
        db: Database session
        contract_id: Parent contract ID

    Returns:
        List of entity objects for the specified contract
    """
    return db.query(Entity).filter(Entity.contract_id == contract_id).all()


def get_entities_by_type(
    db: Session,
    contract_id: int,
    entity_type: str
) -> List[Entity]:
    """
    Retrieve entities filtered by type for a specific contract.

    This enables filtering entities by type, useful for features like
    "show me all parties" or "show me all dates" in the contract.

    Args:
        db: Database session
        contract_id: Parent contract ID
        entity_type: Entity type to filter by (party/date/financial_term/governing_law/obligation)

    Returns:
        List of entity objects matching the type for the specified contract

    Note:
        Compares normalized lowercase entity_type. Since all writes normalize to lowercase
        (see create_entity), we can do direct comparison without SQL lower() for better performance.
        After running migration 001_normalize_entity_type.sql, all existing data will be lowercase.
        TODO: Migrate to DB Enum or CHECK constraint to enforce allowed entity types at schema level.

    Raises:
        ValueError: If entity_type is None or empty
    """
    if not entity_type:
        raise ValueError("entity_type is required and cannot be empty")

    # Direct comparison - data is normalized to lowercase on write
    return db.query(Entity).filter(
        Entity.contract_id == contract_id,
        Entity.entity_type == entity_type.lower()
    ).all()


def count_entities_by_type(db: Session, contract_id: int) -> dict:
    """
    Count entities by type for a contract.

    This provides statistics for the GET /contracts/{id}/entities endpoint
    response, showing how many entities of each type were extracted.

    Args:
        db: Database session
        contract_id: Parent contract ID

    Returns:
        Dictionary mapping entity types to counts (e.g., {'party': 2, 'date': 5})
    """
    results = db.query(
        Entity.entity_type,
        func.count(Entity.id)
    ).filter(
        Entity.contract_id == contract_id
    ).group_by(
        Entity.entity_type
    ).all()

    # Convert list of tuples to dictionary
    return {entity_type: count for entity_type, count in results}


# ============================================================================
# Summary CRUD Operations (used for jurisdiction analysis, summaries, etc.)
# ============================================================================


def create_summary(
    db: Session,
    contract_id: int,
    summary_type: str,
    content: str,
    role: Optional[str] = None
) -> Summary:
    """
    Create a new summary record.

    This creates a summary record that can be used for multiple purposes:
    - Jurisdiction analysis (summary_type='jurisdiction_analysis', role=None)
    - Role-specific summaries in future phase 4 (summary_type='role_specific', role='cfo'/'legal'/etc.)
    - Plain-language summaries (summary_type='plain_language', role=None)

    For jurisdiction analysis, use summary_type='jurisdiction_analysis' and role=None.
    The content should be a string - use json.dumps() for structured data.

    Args:
        db: Database session
        contract_id: Parent contract ID
        summary_type: Type of summary (e.g., 'jurisdiction_analysis', 'role_specific', 'plain_language')
        content: Summary content as string (use json.dumps() for structured data)
        role: Optional role for role-specific summaries (e.g., 'cfo', 'legal')

    Returns:
        Summary: Created summary object with auto-generated ID and timestamp

    Raises:
        IntegrityError: For foreign key violations (invalid contract_id)
        SQLAlchemyError: On other database operation failures
    """
    summary = Summary(
        contract_id=contract_id,
        summary_type=summary_type,
        content=content,
        role=role
    )
    db.add(summary)
    try:
        db.commit()
        db.refresh(summary)
    except Exception:
        db.rollback()
        raise
    return summary


def get_summaries_by_contract(
    db: Session,
    contract_id: int,
    summary_type: Optional[str] = None
) -> List[Summary]:
    """
    Retrieve all summaries for a contract, optionally filtered by type.

    This retrieves summaries from the database, with optional filtering by summary_type.
    For jurisdiction analysis, use summary_type='jurisdiction_analysis'.
    Returns most recent summaries first.

    Args:
        db: Database session
        contract_id: Parent contract ID
        summary_type: Optional summary type filter (e.g., 'jurisdiction_analysis')

    Returns:
        List of summary objects, ordered by created_at descending (most recent first)

    Example:
        >>> # Get all summaries for a contract
        >>> summaries = get_summaries_by_contract(db, contract_id=1)
        >>> # Get only jurisdiction analysis summaries
        >>> jurisdiction_summaries = get_summaries_by_contract(db, contract_id=1, summary_type='jurisdiction_analysis')
    """
    query = db.query(Summary).filter(Summary.contract_id == contract_id)

    if summary_type:
        query = query.filter(Summary.summary_type == summary_type)

    return query.order_by(Summary.created_at.desc()).all()


def get_latest_summary(
    db: Session,
    contract_id: int,
    summary_type: str
) -> Optional[Summary]:
    """
    Get the most recent summary of a specific type for a contract.

    This is useful for retrieving the latest jurisdiction analysis or other
    summary types. Returns None if no summary of that type exists.

    Args:
        db: Database session
        contract_id: Parent contract ID
        summary_type: Summary type to filter by (e.g., 'jurisdiction_analysis')

    Returns:
        Summary object or None if no summary of that type exists

    Example:
        >>> # Get the most recent jurisdiction analysis
        >>> latest = get_latest_summary(db, contract_id=1, summary_type='jurisdiction_analysis')
        >>> if latest:
        ...     print(f"Analysis from {latest.created_at}")
    """
    return db.query(Summary).filter(
        Summary.contract_id == contract_id,
        Summary.summary_type == summary_type
    ).order_by(Summary.created_at.desc()).first()


def delete_summaries_by_type(
    db: Session,
    contract_id: int,
    summary_type: str
) -> int:
    """
    Delete all summaries of a specific type for a contract.

    This is useful for clearing old analyses before creating new ones,
    or for implementing a "re-analyze" feature that clears previous results.

    Args:
        db: Database session
        contract_id: Parent contract ID
        summary_type: Summary type to delete (e.g., 'jurisdiction_analysis')

    Returns:
        int: Number of summaries deleted

    Example:
        >>> # Clear all jurisdiction analysis summaries for a contract
        >>> deleted = delete_summaries_by_type(db, contract_id=1, summary_type='jurisdiction_analysis')
        >>> print(f"Deleted {deleted} summaries")
    """
    deleted_count = db.query(Summary).filter(
        Summary.contract_id == contract_id,
        Summary.summary_type == summary_type
    ).delete()
    db.commit()
    return deleted_count


def create_jurisdiction_analysis(
    db: Session,
    contract_id: int,
    analysis_data: Dict[str, Any]
) -> Summary:
    """
    Convenience function for creating jurisdiction analysis records.

    This function automatically sets summary_type to 'jurisdiction_analysis'
    and serializes the analysis data to JSON for storage. This is the
    recommended way to store jurisdiction analysis results.

    Args:
        db: Database session
        contract_id: Parent contract ID
        analysis_data: Dictionary containing jurisdiction analysis results
                       (from app.services.jurisdiction_analyzer.analyze_jurisdiction)

    Returns:
        Summary: Created summary object with jurisdiction analysis data

    Raises:
        IntegrityError: For foreign key violations (invalid contract_id)
        SQLAlchemyError: On database operation failure

    Example:
        >>> from app.services.jurisdiction_analyzer import analyze_jurisdiction
        >>> analysis_data, error = analyze_jurisdiction(contract.text, contract.id)
        >>> if not error:
        ...     summary = create_jurisdiction_analysis(db, contract.id, analysis_data)
        ...     print(f"Jurisdiction analysis saved at {summary.created_at}")
    """
    json_content = json.dumps(analysis_data, indent=2)
    return create_summary(
        db=db,
        contract_id=contract_id,
        summary_type='jurisdiction_analysis',
        content=json_content,
        role=None
    )


def get_jurisdiction_analysis(
    db: Session,
    contract_id: int
) -> Tuple[Optional[Summary], Optional[Dict[str, Any]]]:
    """
    Convenience function for retrieving jurisdiction analysis.

    This function retrieves the most recent jurisdiction analysis for a contract
    and automatically parses the JSON content back into a dictionary.
    Returns both the Summary ORM object and the parsed analysis data.

    Args:
        db: Database session
        contract_id: Parent contract ID

    Returns:
        Tuple of (Summary object, parsed analysis dict) or (None, None) if not found

    Example:
        >>> summary, analysis_data = get_jurisdiction_analysis(db, contract_id=1)
        >>> if summary:
        ...     print(f"Jurisdiction: {analysis_data['jurisdiction_confirmed']}")
        ...     print(f"Confidence: {analysis_data['confidence']}")
        ...     print(f"Analyzed at: {summary.created_at}")
        >>> else:
        ...     print("No jurisdiction analysis found")
    """
    summary = get_latest_summary(
        db=db,
        contract_id=contract_id,
        summary_type='jurisdiction_analysis'
    )

    if summary:
        try:
            parsed_data = json.loads(summary.content)
            return summary, parsed_data
        except json.JSONDecodeError as e:
            # Delete corrupt cached record and commit
            logger.error(f"Invalid JSON in jurisdiction analysis {summary.id} for contract {contract_id}, purging: {str(e)}")
            db.delete(summary)
            db.commit()
            return None, None

    return None, None


# ============================================================================
# Risk Assessment CRUD Operations
# ============================================================================


def create_risk_assessment(
    db: Session,
    contract_id: int,
    risk_type: str,
    risk_level: str,
    description: str,
    justification: str,
    clause_id: Optional[int] = None,
    recommendation: Optional[str] = None
) -> RiskAssessment:
    """
    Create a risk assessment record from the risk analyzer service.

    This creates a risk assessment record that can be clause-specific (with clause_id)
    or contract-level (clause_id=None). Risk types and levels are normalized to
    lowercase for consistent querying.

    Args:
        db: Database session
        contract_id: Parent contract ID
        risk_type: Risk category (termination_rights/indemnity/penalty/liability_cap/etc.)
        risk_level: Severity level (low/medium/high)
        description: Clear explanation of the risk
        justification: Detailed reasoning for the risk level assessment
        clause_id: Optional clause database ID if risk is clause-specific
        recommendation: Optional specific actionable mitigation strategy

    Returns:
        RiskAssessment: Created risk assessment object with auto-generated ID and timestamp

    Raises:
        IntegrityError: For foreign key violations (invalid contract_id or clause_id)
        SQLAlchemyError: On other database operation failures

    Example:
        >>> risk = create_risk_assessment(
        ...     db, contract_id=1, risk_type='liability_cap', risk_level='high',
        ...     description='Low liability cap', justification='Cap is only 2% of contract value',
        ...     clause_id=5, recommendation='Negotiate to increase cap to 50%'
        ... )
    """
    # Normalize risk_type and risk_level: strip whitespace then lowercase
    # Handle None safely by only normalizing if value is truthy
    normalized_risk_type = risk_type.strip().lower() if risk_type else risk_type
    normalized_risk_level = risk_level.strip().lower() if risk_level else risk_level

    risk = RiskAssessment(
        contract_id=contract_id,
        clause_id=clause_id,
        risk_type=normalized_risk_type,  # Normalized: trimmed and lowercased
        risk_level=normalized_risk_level,  # Normalized: trimmed and lowercased
        description=description,
        justification=justification,
        recommendation=recommendation
    )
    db.add(risk)
    try:
        db.commit()
        db.refresh(risk)  # Refresh to get auto-generated ID and timestamp
    except Exception:
        db.rollback()
        raise
    return risk


def bulk_create_risk_assessments(db: Session, risk_assessments: List[RiskAssessment]) -> None:
    """
    Efficiently insert multiple risk assessments from analysis results.

    This optimizes insertion of multiple risk assessments from the risk analyzer,
    reducing database round-trips. Uses add_all() to populate auto-generated IDs
    and timestamps. The entire transaction is rolled back on failure.

    Args:
        db: Database session
        risk_assessments: List of RiskAssessment objects to insert

    Raises:
        IntegrityError: For constraint violations (e.g., foreign key)
        SQLAlchemyError: On other database operation failures

    Example:
        >>> risks = [
        ...     RiskAssessment(contract_id=1, risk_type='penalty', risk_level='medium', ...),
        ...     RiskAssessment(contract_id=1, risk_type='indemnity', risk_level='high', ...)
        ... ]
        >>> bulk_create_risk_assessments(db, risks)
    """
    try:
        db.add_all(risk_assessments)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise


def get_risk_assessments_by_contract(
    db: Session,
    contract_id: int,
    risk_level: Optional[str] = None
) -> List[RiskAssessment]:
    """
    Retrieve all risk assessments for a contract with optional filtering by risk level.

    Returns high-risk items first, then medium, then low. Most recent assessments
    first within each risk level. This ensures critical risks appear first.

    Args:
        db: Database session
        contract_id: Parent contract ID
        risk_level: Optional filter by risk level (low/medium/high)

    Returns:
        List of risk assessment objects ordered by severity and recency

    Example:
        >>> # Get all risks for a contract
        >>> all_risks = get_risk_assessments_by_contract(db, contract_id=1)
        >>> # Get only high-risk items
        >>> high_risks = get_risk_assessments_by_contract(db, contract_id=1, risk_level='high')
    """
    query = db.query(RiskAssessment).filter(RiskAssessment.contract_id == contract_id)

    if risk_level:
        normalized_risk_level = risk_level.strip().lower()
        query = query.filter(RiskAssessment.risk_level == normalized_risk_level)

    # Order by risk level using CASE expression to map severity to numeric order
    # (high=3, medium=2, low=1), then by assessed_at descending
    from sqlalchemy import case
    severity_order = case(
        (RiskAssessment.risk_level == 'high', 3),
        (RiskAssessment.risk_level == 'medium', 2),
        (RiskAssessment.risk_level == 'low', 1),
        else_=0
    )
    return query.order_by(
        severity_order.desc(),
        RiskAssessment.assessed_at.desc()
    ).all()


def get_risk_assessments_by_clause(db: Session, clause_id: int) -> List[RiskAssessment]:
    """
    Retrieve all risk assessments for a specific clause.

    This is useful for clause-level risk analysis, showing all risks identified
    in a particular clause. Returns high-risk items first.

    Args:
        db: Database session
        clause_id: Clause database ID

    Returns:
        List of risk assessment objects ordered by severity (high first)

    Example:
        >>> # Get all risks for a specific clause
        >>> clause_risks = get_risk_assessments_by_clause(db, clause_id=5)
    """
    from sqlalchemy import case
    severity_order = case(
        (RiskAssessment.risk_level == 'high', 3),
        (RiskAssessment.risk_level == 'medium', 2),
        (RiskAssessment.risk_level == 'low', 1),
        else_=0
    )
    return db.query(RiskAssessment).filter(
        RiskAssessment.clause_id == clause_id
    ).order_by(severity_order.desc()).all()


def count_risks_by_level(db: Session, contract_id: int) -> dict:
    """
    Count risks by severity level for a contract.

    This provides statistics for the risk analysis response, showing distribution
    of risks across severity levels. Used in RiskAnalysisResponse.risk_summary field.

    Args:
        db: Database session
        contract_id: Parent contract ID

    Returns:
        Dictionary mapping risk levels to counts (e.g., {'high': 2, 'medium': 5, 'low': 3})

    Example:
        >>> summary = count_risks_by_level(db, contract_id=1)
        >>> print(f"Found {summary.get('high', 0)} high-risk items")
    """
    results = db.query(
        RiskAssessment.risk_level,
        func.count(RiskAssessment.id)
    ).filter(
        RiskAssessment.contract_id == contract_id
    ).group_by(
        RiskAssessment.risk_level
    ).all()

    # Convert list of tuples to dictionary
    return {risk_level: count for risk_level, count in results}


def count_risks_by_type(db: Session, contract_id: int) -> dict:
    """
    Count risks by category for a contract.

    This provides a breakdown by risk category, showing which types of risks
    are most prevalent in the contract.

    Args:
        db: Database session
        contract_id: Parent contract ID

    Returns:
        Dictionary mapping risk types to counts (e.g., {'liability_cap': 2, 'termination_rights': 1})

    Example:
        >>> type_breakdown = count_risks_by_type(db, contract_id=1)
        >>> print(f"Found {type_breakdown.get('indemnity', 0)} indemnity risks")
    """
    results = db.query(
        RiskAssessment.risk_type,
        func.count(RiskAssessment.id)
    ).filter(
        RiskAssessment.contract_id == contract_id
    ).group_by(
        RiskAssessment.risk_type
    ).all()

    # Convert list of tuples to dictionary
    return {risk_type: count for risk_type, count in results}


def delete_risk_assessments_by_contract(db: Session, contract_id: int) -> int:
    """
    Delete all risk assessments for a contract.

    This is useful for clearing old analyses before re-analyzing, or for
    implementing a "re-analyze" feature that clears previous results.

    Args:
        db: Database session
        contract_id: Parent contract ID

    Returns:
        int: Number of risk assessments deleted

    Example:
        >>> # Clear all risk assessments for a contract
        >>> deleted = delete_risk_assessments_by_contract(db, contract_id=1)
        >>> print(f"Deleted {deleted} risk assessments")
    """
    deleted_count = db.query(RiskAssessment).filter(
        RiskAssessment.contract_id == contract_id
    ).delete()
    db.commit()
    return deleted_count


def get_high_risk_assessments(db: Session, contract_id: int) -> List[RiskAssessment]:
    """
    Convenience function to get only high-risk items for a contract.

    This provides quick access to critical risks without filtering manually.
    Equivalent to calling get_risk_assessments_by_contract with risk_level='high'.

    Args:
        db: Database session
        contract_id: Parent contract ID

    Returns:
        List of high-risk assessment objects

    Example:
        >>> # Get only critical risks
        >>> critical_risks = get_high_risk_assessments(db, contract_id=1)
        >>> for risk in critical_risks:
        ...     print(f"HIGH RISK: {risk.description}")
    """
    return get_risk_assessments_by_contract(db, contract_id, risk_level='high')


# ============================================================================
# Contract Summary CRUD Operations
# ============================================================================

def create_contract_summary(
    db: Session,
    contract_id: int,
    summary_data: Dict[str, Any],
    role: Optional[str] = None
) -> Summary:
    """
    Convenience function for creating contract summary records.

    This is the recommended way to store contract summary results from the
    summarizer service. Automatically sets the summary_type based on the
    role parameter and serializes summary data to JSON for storage.

    Args:
        db: Database session
        contract_id: Parent contract ID
        summary_data: Summary data dictionary from summarizer service
        role: Optional role perspective ('supplier', 'client', or None for neutral)

    Returns:
        Created Summary object with timestamp

    Raises:
        Exception: If database operation fails

    Usage:
        For neutral summaries (balanced perspective):
            summary = create_contract_summary(db, contract_id=1, summary_data=data, role=None)

        For role-specific summaries:
            summary = create_contract_summary(db, contract_id=1, summary_data=data, role='supplier')
            summary = create_contract_summary(db, contract_id=1, summary_data=data, role='client')

    Example:
        >>> from app.services.summarizer import summarize_contract
        >>> summary_data, error = summarize_contract(contract_text, 1, role='client')
        >>> if not error:
        ...     summary = create_contract_summary(db, 1, summary_data, role='client')
        ...     print(f"Summary stored with ID {summary.id}")
    """
    try:
        # Determine summary_type based on role
        if role is None:
            summary_type = 'contract_overview'
        else:
            summary_type = 'role_specific'

        # Serialize summary data to JSON
        json_content = json.dumps(summary_data, indent=2)

        # Create summary using generic function
        summary = create_summary(
            db=db,
            contract_id=contract_id,
            summary_type=summary_type,
            content=json_content,
            role=role
        )

        return summary

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create contract summary for contract {contract_id}: {str(e)}")
        raise


def get_contract_summary(
    db: Session,
    contract_id: int,
    role: Optional[str] = None
) -> Tuple[Optional[Summary], Optional[Dict[str, Any]]]:
    """
    Convenience function for retrieving contract summaries.

    Retrieves the most recent summary for the specified role. If role is None,
    returns the neutral/contract overview summary. If role is provided, returns
    the role-specific summary for that role.

    Args:
        db: Database session
        contract_id: Parent contract ID
        role: Optional role perspective ('supplier', 'client', or None for neutral)

    Returns:
        Tuple of (Summary ORM object, parsed summary data dict) or (None, None) if not found

    Usage:
        For neutral summary:
            summary, data = get_contract_summary(db, contract_id=1, role=None)

        For role-specific summary:
            summary, data = get_contract_summary(db, contract_id=1, role='supplier')
            summary, data = get_contract_summary(db, contract_id=1, role='client')

    Example:
        >>> summary, data = get_contract_summary(db, 1, role='client')
        >>> if summary:
        ...     print(f"Summary created at: {summary.created_at}")
        ...     print(f"Main summary: {data['summary']}")
        ...     print(f"Key points: {data['key_points']}")
        >>> else:
        ...     print("No summary found")
    """
    try:
        # Determine summary_type based on role
        if role is None:
            summary_type = 'contract_overview'
        else:
            summary_type = 'role_specific'

        # Query for the latest summary with appropriate filters
        query = db.query(Summary).filter(
            Summary.contract_id == contract_id,
            Summary.summary_type == summary_type
        )

        # Add role filter for role-specific summaries
        if role is not None:
            query = query.filter(Summary.role == role)

        # Get the most recent summary
        summary = query.order_by(Summary.created_at.desc()).first()

        if summary is None:
            return None, None

        # Parse JSON content back to dict
        try:
            parsed_data = json.loads(summary.content)
            return summary, parsed_data
        except json.JSONDecodeError as e:
            # Delete corrupt cached record and commit
            logger.error(f"Invalid JSON in contract summary {summary.id} for contract {contract_id}, purging: {str(e)}")
            db.delete(summary)
            db.commit()
            return None, None

    except Exception as e:
        logger.error(f"Failed to retrieve contract summary for contract {contract_id}: {str(e)}")
        return None, None


def get_all_contract_summaries(
    db: Session,
    contract_id: int
) -> List[Tuple[Summary, Dict[str, Any]]]:
    """
    Retrieve all summaries for a contract (both contract_overview and role_specific).

    This function is useful for listing all available summaries regardless of
    type or role. Returns both neutral and all role-specific summaries.

    Args:
        db: Database session
        contract_id: Parent contract ID

    Returns:
        List of tuples: [(Summary object, parsed data dict), ...]

    Example:
        >>> summaries = get_all_contract_summaries(db, contract_id=1)
        >>> for summary, data in summaries:
        ...     print(f"Type: {summary.summary_type}, Role: {summary.role}")
        ...     print(f"Created: {summary.created_at}")
        ...     print(f"Summary: {data['summary'][:100]}...")
    """
    try:
        # Query for all summaries of relevant types
        summaries = db.query(Summary).filter(
            Summary.contract_id == contract_id,
            Summary.summary_type.in_(['contract_overview', 'role_specific'])
        ).order_by(Summary.created_at.desc()).all()

        # Parse JSON content for each summary
        results = []
        for summary in summaries:
            try:
                parsed_data = json.loads(summary.content)
                results.append((summary, parsed_data))
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse summary {summary.id}: {str(e)}")
                continue

        return results

    except Exception as e:
        logger.error(f"Failed to retrieve all summaries for contract {contract_id}: {str(e)}")
        return []


# ============================================================================
# QA History CRUD Operations
# ============================================================================


def create_qa_record(
    db: Session,
    contract_id: int,
    question: str,
    answer: str,
    referenced_clause_ids: List[int],
    confidence: Optional[str] = None
) -> QAHistory:
    """
    Create a Q&A record from the qa_engine service.

    This function stores a question-answer interaction in the database, including
    the list of clause IDs that were referenced in generating the answer. The
    referenced_clause_ids list is automatically serialized to JSON for storage.

    Args:
        db: Database session
        contract_id: Parent contract ID
        question: User's natural language question
        answer: AI-generated answer (2-4 paragraphs)
        referenced_clause_ids: List of clause database IDs used to generate answer
        confidence: Optional answer confidence level (high/medium/low)

    Returns:
        QAHistory: Created Q&A history object with auto-generated ID and timestamp

    Raises:
        IntegrityError: For foreign key violations (invalid contract_id)
        SQLAlchemyError: On other database operation failures

    Example:
        >>> qa_record = create_qa_record(
        ...     db, contract_id=1, question="Can client terminate early?",
        ...     answer="Yes, client can terminate...", referenced_clause_ids=[5, 6, 7],
        ...     confidence="high"
        ... )
        >>> print(f"Q&A stored with ID {qa_record.id} at {qa_record.asked_at}")
    """
    # Convert referenced_clause_ids list to JSON string
    referenced_clauses_json = json.dumps(referenced_clause_ids)

    qa_history = QAHistory(
        contract_id=contract_id,
        question=question,
        answer=answer,
        referenced_clauses=referenced_clauses_json,
        confidence=confidence
    )

    db.add(qa_history)
    try:
        db.commit()
        db.refresh(qa_history)  # Refresh to get auto-generated ID and timestamp
        return qa_history
    except Exception:
        db.rollback()
        raise


def get_qa_history_by_contract(
    db: Session,
    contract_id: int,
    limit: int = 50
) -> List[QAHistory]:
    """
    Retrieve Q&A conversation history for a contract.

    Returns the most recent questions first, limited to prevent overwhelming
    responses. This provides conversation history for a contract's Q&A interactions.

    Args:
        db: Database session
        contract_id: Parent contract ID
        limit: Maximum number of Q&A records to return (default 50)

    Returns:
        List of QAHistory objects ordered by asked_at descending (most recent first)

    Example:
        >>> # Get last 20 Q&A interactions
        >>> qa_history = get_qa_history_by_contract(db, contract_id=1, limit=20)
        >>> for qa in qa_history:
        ...     print(f"Q: {qa.question}")
        ...     print(f"A: {qa.answer[:100]}...")
        ...     print(f"Asked at: {qa.asked_at}")
    """
    return db.query(QAHistory).filter(
        QAHistory.contract_id == contract_id
    ).order_by(
        QAHistory.asked_at.desc()
    ).limit(limit).all()


def get_qa_record(db: Session, qa_id: int) -> Optional[QAHistory]:
    """
    Retrieve a specific Q&A interaction by ID.

    This retrieves a single Q&A record for viewing or auditing purposes.

    Args:
        db: Database session
        qa_id: Q&A history primary key

    Returns:
        QAHistory object if found, None otherwise

    Example:
        >>> qa = get_qa_record(db, qa_id=1)
        >>> if qa:
        ...     print(f"Question: {qa.question}")
        ...     print(f"Answer: {qa.answer}")
    """
    return db.query(QAHistory).filter(QAHistory.id == qa_id).first()


def parse_referenced_clauses(referenced_clauses_json: Optional[str]) -> List[int]:
    """
    Helper function to parse JSON string back to list of clause IDs.

    This safely parses the referenced_clauses field from QAHistory objects,
    handling None values and JSON decode errors gracefully.

    Args:
        referenced_clauses_json: JSON string containing list of clause IDs

    Returns:
        List of clause IDs (empty list if None or parse error)

    Example:
        >>> qa = get_qa_record(db, qa_id=1)
        >>> clause_ids = parse_referenced_clauses(qa.referenced_clauses)
        >>> print(f"Referenced clauses: {clause_ids}")
    """
    if not referenced_clauses_json:
        return []

    try:
        clause_ids = json.loads(referenced_clauses_json)
        # Ensure it's a list of integers
        if isinstance(clause_ids, list):
            return [int(cid) for cid in clause_ids if isinstance(cid, (int, str)) and str(cid).isdigit()]
        return []
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.exception(f"Failed to parse referenced_clauses JSON: {str(e)}")
        return []
