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
from app.models import Contract, Clause, Entity, Summary
import json


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
    Efficiently insert multiple clauses in a single transaction.

    This optimizes insertion of multiple clauses from segmentation,
    reducing database round-trips.

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
    except IntegrityError as e:
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
    except Exception as e:
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
            # Log error but return the summary object with None for data
            # This allows caller to see that analysis exists but couldn't be parsed
            return summary, None

    return None, None
