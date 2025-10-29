# Import FastAPI (web framework) and supporting classes
from fastapi import FastAPI, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
import re
from uuid import uuid4
from datetime import datetime
import logging

# Database imports
from sqlalchemy.orm import Session
from app.database import get_db

# Schema imports
from app.schemas import (
    ContractUploadRequest,
    ContractSegmentResponse,
    ClauseResponse,
    EntityResponse,
    EntitiesListResponse
)

# Service imports
from app.services.entity_extractor import extract_entities

# CRUD and model imports
from app import crud
from app.models import Entity, Clause as ClauseModel

# Logging setup
logger = logging.getLogger(__name__)

# Initialize the FastAPI application
app = FastAPI(
    title="AI Legal Contract Analyst",
    version="0.1.0",
    description="AI-powered legal contract analysis with entity extraction, clause segmentation, and more."
)

# --------------------------
# Clause Segmentation Logic
# --------------------------

# Regex that detects numbered headings in contracts.
# Example it matches:
#   "2 Term"
#   "2.1 Termination for Convenience"
# Captures: the number ("2.1") and the title ("Termination for Convenience").
HEADING_RX = re.compile(r'(?m)^\s*(\d+(?:\.\d+)*)\s+([A-Z][^\n]{0,100})\s*$')

# Regex to join lines that are bullets (•, -, –) back together
# (to prevent splitting a single bullet point into multiple clauses).
BULLET_JOIN_RX = re.compile(r'\n(?=[•\-–]\s)')

def segment_contract(text: str) -> List[dict]:
    """
    Splits the raw contract text into clauses based on numbered headings.
    Returns a list of clause dictionaries with clause_id, number, title, and text.

    NOTE: This function intentionally remains pure for segmentation only.
    It does not call GPT-4o or perform entity extraction. Entity extraction
    is orchestrated separately in the /contracts/segment endpoint after
    segmentation completes, allowing for clear separation of concerns between
    regex-based clause splitting and AI-powered semantic analysis.
    """
    # First: normalize bullet lists so they stay inside the same clause
    text = BULLET_JOIN_RX.sub('\n', text)

    # Find all numbered headings using regex
    matches = list(HEADING_RX.finditer(text))

    # If no headings are found, treat the entire document as one big clause
    if not matches:
        return [{
            "clause_id": str(uuid4()),
            "number": None,
            "title": None,
            "text": text.strip()
        }]

    clauses: List[dict] = []
    for i, m in enumerate(matches):
        # Start of clause is right after the heading we matched
        start = m.end()
        # End of clause is the start of the next heading, or end of document
        end = matches[i+1].start() if i+1 < len(matches) else len(text)

        # Clause number (e.g. "2.1")
        number = m.group(1).strip()
        # Clause title (e.g. "Termination for Convenience")
        title = m.group(2).strip()
        # The body text of the clause (between this heading and the next one)
        body = text[start:end].strip()

        # Create a clause dictionary and add it to the list
        clauses.append({
            "clause_id": str(uuid4()),  # generate a random unique ID
            "number": number,
            "title": title,
            "text": body
        })
    return clauses

# --------------------------
# API Endpoint
# --------------------------

@app.get("/health")
def health_check():
    """
    Health check endpoint to verify the service is running.
    Returns status and service information.
    """
    return {
        "status": "healthy",
        "service": "AI Legal Analyst MVP",
        "version": "0.1.0"
    }

@app.post("/contracts/segment", response_model=ContractSegmentResponse)
def upload_and_segment(
    req: ContractUploadRequest,
    db: Session = Depends(get_db)
) -> ContractSegmentResponse:
    """
    Upload and process a contract: segment into clauses and extract entities.

    This endpoint:
    1. Creates a contract record in the database
    2. Segments the contract text into numbered clauses
    3. Extracts entities using OpenAI GPT-4o (parties, dates, financial terms, etc.)
    4. Persists all data to the database
    5. Returns the contract ID, clauses, and extracted entities

    Args:
        req: Contract upload request with text, optional title, and jurisdiction
        db: Database session (injected)

    Returns:
        ContractSegmentResponse with contract ID, status, clauses, and entities

    Raises:
        HTTPException: 500 if processing fails
    """
    contract = None
    try:
        logger.info("Starting contract processing")

        # 1. Create contract record
        contract = crud.create_contract(
            db,
            title=req.title,
            text=req.text,
            jurisdiction=req.jurisdiction
        )
        logger.info(f"Created contract with ID: {contract.id}")

        # 2. Update status to processing
        crud.update_contract_status(db, contract.id, 'processing')

        # 3. Segment clauses
        clause_dicts = segment_contract(req.text)
        logger.info(f"Segmented contract into {len(clause_dicts)} clauses")

        # 4. Convert to SQLAlchemy models and persist
        clause_models = []
        for clause_dict in clause_dicts:
            clause_model = ClauseModel(
                contract_id=contract.id,
                clause_id=clause_dict["clause_id"],
                number=clause_dict.get("number"),
                title=clause_dict.get("title"),
                text=clause_dict["text"]
            )
            clause_models.append(clause_model)

        # Use CRUD helper for consistent constraint handling
        try:
            crud.bulk_create_clauses(db, clause_models)
            logger.info(f"Persisted {len(clause_models)} clauses to database")
        except crud.DuplicateClauseError as e:
            logger.error(f"Duplicate clause detected: {e}", exc_info=True)
            # Update contract to terminal failed state
            try:
                crud.update_contract_status(db, contract.id, 'failed')
                logger.info(f"Updated contract {contract.id} status to 'failed'")
            except Exception as status_err:
                logger.error(f"Failed to update contract status to 'failed': {status_err}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e)
            )

        # 5. Extract entities using OpenAI
        entity_dicts, extraction_error = extract_entities(req.text)

        # Track if entity extraction had issues
        extraction_failed = extraction_error is not None

        if extraction_failed:
            logger.warning(f"Entity extraction failed: {extraction_error}")
        else:
            logger.info(f"Extracted {len(entity_dicts)} entities from contract")

        # 6. Convert to SQLAlchemy models and persist
        entity_models = []
        for entity_dict in entity_dicts:
            entity_model = Entity(
                contract_id=contract.id,
                entity_type=entity_dict["entity_type"].lower(),  # Normalize to lowercase
                value=entity_dict["value"],
                context=entity_dict.get("context"),
                confidence=entity_dict.get("confidence", "medium")
            )
            entity_models.append(entity_model)

        if entity_models:
            crud.bulk_create_entities(db, entity_models)
            # Refresh each entity to materialize auto-generated fields (id, extracted_at)
            for entity in entity_models:
                db.refresh(entity)
            logger.info(f"Persisted {len(entity_models)} entities to database")

        # 7. Update status based on extraction success
        if extraction_failed:
            # Set status to completed_with_warnings if extraction failed but segmentation succeeded
            final_status = 'completed_with_warnings'
        else:
            final_status = 'completed'

        crud.update_contract_status(
            db,
            contract.id,
            final_status,
            processed_at=datetime.utcnow()
        )

        # 8. Build response
        # Convert SQLAlchemy models to Pydantic response models
        clause_responses = [
            ClauseResponse(
                clause_id=c.clause_id,
                number=c.number,
                title=c.title,
                text=c.text
            )
            for c in clause_models
        ]

        entity_responses = [
            EntityResponse.model_validate(e)
            for e in entity_models
        ]

        # Build message with warning if extraction failed
        if extraction_failed:
            message = (
                f"Contract segmentation completed successfully. "
                f"Found {len(clause_responses)} clauses. "
                f"WARNING: Entity extraction failed ({extraction_error}). "
                f"Extracted {len(entity_responses)} entities before failure."
            )
        else:
            message = (
                f"Contract processed successfully. "
                f"Found {len(clause_responses)} clauses and {len(entity_responses)} entities."
            )

        return ContractSegmentResponse(
            contract_id=contract.id,
            status=final_status,
            clauses=clause_responses,
            entities=entity_responses,
            message=message
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like 409 Conflict) without converting to 500
        raise
    except Exception as e:
        logger.exception("Contract processing failed")

        # Update contract status to failed if contract was created
        if contract:
            try:
                crud.update_contract_status(db, contract.id, 'failed')
            except Exception as status_err:
                logger.exception("Failed to update contract status")

        # Return error response
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while processing contract"
        )


@app.get("/contracts/{contract_id}/entities", response_model=EntitiesListResponse)
def get_contract_entities(
    contract_id: int,
    entity_type: Optional[str] = None,
    db: Session = Depends(get_db)
) -> EntitiesListResponse:
    """
    Retrieve all extracted entities for a specific contract.

    This endpoint provides:
    - All entities extracted from the contract
    - Statistics and breakdown by entity type
    - Optional filtering by entity type

    Args:
        contract_id: Contract database ID
        entity_type: Optional entity type filter (party/date/financial_term/governing_law/obligation)
        db: Database session (injected)

    Returns:
        EntitiesListResponse with entities, counts, and type breakdown

    Raises:
        HTTPException: 404 if contract not found, 500 if retrieval fails
    """
    try:
        # 1. Validate contract exists
        contract = crud.get_contract(db, contract_id)
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract {contract_id} not found"
            )

        # 2. Retrieve entities (filtered or all)
        if entity_type:
            entities = crud.get_entities_by_type(db, contract_id, entity_type)
        else:
            entities = crud.get_entities_by_contract(db, contract_id)

        # 3. Get type counts
        entity_type_counts = crud.count_entities_by_type(db, contract_id)

        # 4. Build response
        entity_responses = [
            EntityResponse.model_validate(e)
            for e in entities
        ]

        return EntitiesListResponse(
            contract_id=contract_id,
            entities=entity_responses,
            total_count=len(entity_responses),
            entity_types=entity_type_counts
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve entities: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve entities"
        )

