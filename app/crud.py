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
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import Contract, Clause


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
