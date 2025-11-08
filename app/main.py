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
    EntitiesListResponse,
    JurisdictionAnalysisResponse,
    RiskAnalysisResponse,
    RiskAssessmentResponse,
    ContractSummaryResponse,
    QuestionRequest,
    QAResponse
)

# Service imports
from app.services.entity_extractor import extract_entities
from app.services.jurisdiction_analyzer import analyze_jurisdiction
from app.services.risk_analyzer import analyze_risks
from app.services.summarizer import summarize_contract
from app.services.qa_engine import answer_question

# CRUD and model imports
from app import crud
from app.models import Entity, Clause as ClauseModel, RiskAssessment

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
                detail="Duplicate clause detected. Contract processing failed."
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

        # 7. Best-effort jurisdiction detection if not provided
        jurisdiction_failed = False
        if req.jurisdiction is None:
            try:
                logger.info(f"No jurisdiction provided, attempting automatic detection for contract {contract.id}")
                jurisdiction_data, jurisdiction_error = analyze_jurisdiction(req.text, contract.id)

                if not jurisdiction_error and 'jurisdiction_code' in jurisdiction_data:
                    # Update contract jurisdiction field with normalized code
                    jurisdiction_code = jurisdiction_data['jurisdiction_code']
                    logger.info(f"Auto-detected jurisdiction for contract {contract.id}: {jurisdiction_code}")
                    crud.update_contract_jurisdiction(db, contract.id, jurisdiction_code)
                else:
                    logger.warning(f"Auto jurisdiction detection failed for contract {contract.id}: {jurisdiction_error}")
                    jurisdiction_failed = True
            except Exception as e:
                # Don't fail the entire upload if jurisdiction detection fails
                logger.warning(f"Exception during auto jurisdiction detection for contract {contract.id}: {e}")
                jurisdiction_failed = True

        # 8. Update status based on extraction success
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
    except Exception:
        logger.exception("Contract processing failed")

        # Update contract status to failed if contract was created
        if contract:
            try:
                crud.update_contract_status(db, contract.id, 'failed')
            except Exception:
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


@app.post("/contracts/{contract_id}/analyze-jurisdiction", response_model=JurisdictionAnalysisResponse)
def analyze_contract_jurisdiction(
    contract_id: int,
    db: Session = Depends(get_db)
) -> JurisdictionAnalysisResponse:
    """
    Analyze a contract through UK contract law lens.

    This endpoint performs comprehensive jurisdiction analysis including:
    - Jurisdiction detection and confirmation (UK, England and Wales, etc.)
    - Identification of applicable UK statutes (Consumer Rights Act, UCTA, etc.)
    - Mapping of relevant legal principles (formation, interpretation, unfair terms, etc.)
    - Overall enforceability assessment under UK contract law
    - Clause-specific interpretations with legal reasoning
    - Recommendations for UK law compliance

    The analysis is performed using OpenAI GPT-4o with UK legal expertise.
    Results are cached in the database - subsequent requests return cached data
    without calling the OpenAI API again.

    Args:
        contract_id: Contract database ID
        db: Database session (injected)

    Returns:
        JurisdictionAnalysisResponse with comprehensive UK law analysis

    Raises:
        HTTPException: 404 if contract not found, 500 if analysis fails

    DISCLAIMER:
        This analysis is for informational purposes only and does NOT constitute
        legal advice. Always consult qualified legal professionals for actual
        legal guidance on contract matters.
    """
    try:
        logger.info(f"Starting jurisdiction analysis for contract {contract_id}")

        # 1. Validate contract exists
        contract = crud.get_contract(db, contract_id)
        if not contract:
            logger.warning(f"Contract {contract_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract {contract_id} not found"
            )

        # 2. Check for existing cached analysis
        summary, cached_analysis = crud.get_jurisdiction_analysis(db, contract_id)

        if summary and cached_analysis:
            # Return cached analysis
            logger.info(f"Returning cached jurisdiction analysis for contract {contract_id}")
            return JurisdictionAnalysisResponse(
                contract_id=contract_id,
                jurisdiction_confirmed=cached_analysis['jurisdiction_confirmed'],
                confidence=cached_analysis['confidence'],
                applicable_statutes=cached_analysis.get('applicable_statutes', []),
                legal_principles=cached_analysis.get('legal_principles', []),
                enforceability_assessment=cached_analysis['enforceability_assessment'],
                key_considerations=cached_analysis.get('key_considerations', []),
                clause_interpretations=cached_analysis.get('clause_interpretations', []),
                recommendations=cached_analysis.get('recommendations', []),
                analyzed_at=summary.created_at
            )

        # 3. Perform jurisdiction analysis using OpenAI
        logger.info(f"No cached analysis found, performing new analysis for contract {contract_id}")
        analysis_data, error = analyze_jurisdiction(contract.text, contract_id)

        # Check if analysis failed
        if error:
            logger.error(f"Jurisdiction analysis failed for contract {contract_id}: {error}")
            # Return 400 Bad Request for short/empty text errors, 500 for other errors
            if "too short for jurisdiction analysis" in error or "empty" in error.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Jurisdiction analysis failed: {error}"
            )

        # 4. Update contract jurisdiction field with normalized code
        if 'jurisdiction_code' in analysis_data:
            jurisdiction_code = analysis_data['jurisdiction_code']
            logger.info(f"Updating contract {contract_id} jurisdiction to: {jurisdiction_code}")
            crud.update_contract_jurisdiction(db, contract_id, jurisdiction_code)

        # 5. Store analysis results in database
        logger.info(f"Storing jurisdiction analysis for contract {contract_id}")
        summary = crud.create_jurisdiction_analysis(db, contract_id, analysis_data)

        # 6. Build and return response
        return JurisdictionAnalysisResponse(
            contract_id=contract_id,
            jurisdiction_confirmed=analysis_data['jurisdiction_confirmed'],
            confidence=analysis_data['confidence'],
            applicable_statutes=analysis_data.get('applicable_statutes', []),
            legal_principles=analysis_data.get('legal_principles', []),
            enforceability_assessment=analysis_data['enforceability_assessment'],
            key_considerations=analysis_data.get('key_considerations', []),
            clause_interpretations=analysis_data.get('clause_interpretations', []),
            recommendations=analysis_data.get('recommendations', []),
            analyzed_at=summary.created_at
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to analyze jurisdiction for contract {contract_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze jurisdiction"
        )


@app.post("/contracts/{contract_id}/analyze-risks", response_model=RiskAnalysisResponse)
def analyze_contract_risks(
    contract_id: int,
    db: Session = Depends(get_db)
) -> RiskAnalysisResponse:
    """
    Analyze contract for risky, unfair, or unusual clauses.

    This endpoint performs comprehensive risk assessment including:
    - Detection of 10 risk categories: termination rights, indemnities, penalties,
      liability caps, payment terms, intellectual property, confidentiality,
      warranties, force majeure, and dispute resolution
    - Risk level assignment (low/medium/high) with detailed justifications
    - Clause-specific risk linking for easy reference
    - Actionable recommendations for risk mitigation

    The analysis is performed using OpenAI GPT-4o with contract risk expertise.
    Results are cached in the database - subsequent requests return cached data
    without calling the OpenAI API again.

    Args:
        contract_id: Contract database ID
        db: Database session (injected)

    Returns:
        RiskAnalysisResponse with all identified risks, risk summary, and analysis timestamp

    Raises:
        HTTPException: 404 if contract not found, 500 if analysis fails

    DISCLAIMER:
        This analysis is for informational purposes only and does NOT constitute
        legal advice. Risk assessments are based on AI analysis and should be
        validated by qualified legal professionals.
    """
    try:
        logger.info(f"Starting risk analysis for contract {contract_id}")

        # 1. Validate contract exists
        contract = crud.get_contract(db, contract_id)
        if not contract:
            logger.warning(f"Contract {contract_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract {contract_id} not found"
            )

        # 2. Check for existing cached analysis
        existing_risks = crud.get_risk_assessments_by_contract(db, contract_id)

        if existing_risks:
            # Return cached analysis
            logger.info(f"Returning cached risk analysis for contract {contract_id} ({len(existing_risks)} risks)")

            # Convert to response models
            risk_responses = [
                RiskAssessmentResponse.model_validate(risk)
                for risk in existing_risks
            ]

            # Get risk summary and normalize to include all levels with default 0
            risk_summary = crud.count_risks_by_level(db, contract_id)
            risk_summary = {
                'high': risk_summary.get('high', 0),
                'medium': risk_summary.get('medium', 0),
                'low': risk_summary.get('low', 0)
            }

            # Get most recent assessed_at timestamp
            analyzed_at = max(risk.assessed_at for risk in existing_risks)

            return RiskAnalysisResponse(
                contract_id=contract_id,
                risks=risk_responses,
                total_risks=len(risk_responses),
                risk_summary=risk_summary,
                analyzed_at=analyzed_at
            )

        # 3. Retrieve clauses for context
        clauses = crud.get_clauses_by_contract(db, contract_id)

        # Convert clause ORM objects to dictionaries for the risk analyzer
        clause_dicts = [
            {
                "id": clause.id,
                "clause_id": clause.clause_id,
                "number": clause.number,
                "title": clause.title,
                "text": clause.text
            }
            for clause in clauses
        ]

        # 4. Perform risk analysis using OpenAI
        logger.info(f"No cached analysis found, performing new risk analysis for contract {contract_id}")
        risk_data_list, error = analyze_risks(contract.text, contract_id, clause_dicts)

        # Check if analysis failed
        if error:
            logger.error(f"Risk analysis failed for contract {contract_id}: {error}")
            # Return 400 Bad Request for short/empty text errors, 500 for other errors
            if "too short for risk analysis" in error or "empty" in error.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Risk analysis failed: {error}"
            )

        # 5. Store risk assessments
        if risk_data_list:
            # Convert risk data dictionaries to SQLAlchemy RiskAssessment instances
            risk_models = []
            for risk_dict in risk_data_list:
                risk_model = RiskAssessment(
                    contract_id=contract_id,
                    clause_id=risk_dict.get('clause_id'),
                    risk_type=risk_dict['risk_type'],
                    risk_level=risk_dict['risk_level'],
                    description=risk_dict['description'],
                    justification=risk_dict['justification'],
                    recommendation=risk_dict.get('recommendation')
                )
                risk_models.append(risk_model)

            logger.info(f"Storing {len(risk_models)} risk assessments for contract {contract_id}")
            crud.bulk_create_risk_assessments(db, risk_models)

            # Refresh each risk assessment to materialize auto-generated fields (id, assessed_at)
            for risk in risk_models:
                db.refresh(risk)

            logger.info(f"Successfully stored {len(risk_models)} risk assessments")

            # Convert to response models
            risk_responses = [
                RiskAssessmentResponse.model_validate(risk)
                for risk in risk_models
            ]

            # Get risk summary and normalize to include all levels with default 0
            risk_summary = crud.count_risks_by_level(db, contract_id)
            risk_summary = {
                'high': risk_summary.get('high', 0),
                'medium': risk_summary.get('medium', 0),
                'low': risk_summary.get('low', 0)
            }

            # Get most recent assessed_at timestamp
            analyzed_at = max(risk.assessed_at for risk in risk_models)

            return RiskAnalysisResponse(
                contract_id=contract_id,
                risks=risk_responses,
                total_risks=len(risk_responses),
                risk_summary=risk_summary,
                analyzed_at=analyzed_at
            )
        else:
            # No risks found (well-balanced contract)
            logger.info(f"No risks identified for contract {contract_id}")
            return RiskAnalysisResponse(
                contract_id=contract_id,
                risks=[],
                total_risks=0,
                risk_summary={'high': 0, 'medium': 0, 'low': 0},
                analyzed_at=datetime.utcnow()
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to analyze risks for contract {contract_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze risks"
        )


@app.post("/contracts/{contract_id}/summarize", response_model=ContractSummaryResponse)
def summarize_contract_endpoint(
    contract_id: int,
    role: Optional[str] = None,
    db: Session = Depends(get_db)
) -> ContractSummaryResponse:
    """
    Generate a plain-language summary of a contract.

    This endpoint translates complex legal jargon into clear, accessible language
    that non-lawyers can understand. It extracts key information such as parties,
    dates, financial terms, obligations, rights, termination conditions, and risks.

    The summary can be generated from different perspectives:
    - **Neutral** (default): Balanced overview without favoring either party
    - **Supplier**: Highlights supplier obligations, risks, and opportunities
    - **Client**: Highlights client protections, rights, and concerns

    Results are cached in the database. Subsequent requests with the same role
    return cached data without calling OpenAI API again, providing faster responses
    and reducing costs.

    **Args:**
    - `contract_id` (int): Database ID of the contract to summarize
    - `role` (Optional[str]): Role perspective ('supplier', 'client', 'neutral', or omit for neutral)

    **Returns:**
    - `ContractSummaryResponse`: Comprehensive plain-language summary with:
        - Main summary (3-5 paragraphs)
        - Key points (5-10 most important items)
        - Parties involved
        - Important dates and deadlines
        - Financial terms and payment information
        - Obligations for each party
        - Rights and protections for each party
        - Termination conditions
        - Top risks to be aware of

    **HTTP Status Codes:**
    - 200 OK: Summary generated or retrieved successfully
    - 400 Bad Request: Invalid role parameter or contract text too short
    - 404 Not Found: Contract does not exist
    - 500 Internal Server Error: Summarization failed (OpenAI error, parsing error, etc.)

    **Example Usage:**
    ```bash
    # Neutral summary
    curl -X POST http://localhost:8000/contracts/1/summarize

    # Client perspective
    curl -X POST "http://localhost:8000/contracts/1/summarize?role=client"

    # Supplier perspective
    curl -X POST "http://localhost:8000/contracts/1/summarize?role=supplier"
    ```

    **DISCLAIMER:**
    This summary is for informational purposes only and does NOT constitute legal advice.
    AI-generated summaries may not capture all nuances or important details. Always review
    the full contract and consult qualified legal professionals for actual legal guidance.
    """
    try:
        # Validate contract exists
        contract = crud.get_contract(db, contract_id)
        if contract is None:
            logger.warning(f"Contract {contract_id} not found for summarization")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract {contract_id} not found"
            )

        # Validate and normalize role parameter
        # Service layer will handle 'neutral' -> None conversion
        if role is not None:
            role = role.strip().lower()
            valid_roles = ['supplier', 'client', 'neutral']
            if role not in valid_roles:
                logger.warning(f"Invalid role parameter: {role}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid role: {role}. Must be one of: {', '.join(valid_roles)}"
                )

        # Service layer converts 'neutral' -> None, match that for cache/storage consistency
        storage_role = None if role == 'neutral' else role

        logger.info(f"Processing summarization request for contract {contract_id} with role: {role or 'neutral'}")

        # Check for existing cached summary
        existing_summary, existing_data = crud.get_contract_summary(db, contract_id, storage_role)

        if existing_summary is not None:
            logger.info(f"Returning cached summary for contract {contract_id} (role: {role or 'neutral'})")

            # Build response from cached data
            return ContractSummaryResponse(
                contract_id=contract_id,
                summary_type=existing_data.get('summary_type', 'contract_overview'),
                role=role,
                summary=existing_data['summary'],
                key_points=existing_data['key_points'],
                parties=existing_data.get('parties'),
                key_dates=existing_data.get('key_dates'),
                financial_terms=existing_data.get('financial_terms'),
                obligations=existing_data.get('obligations'),
                rights=existing_data.get('rights'),
                termination=existing_data.get('termination'),
                risks=existing_data.get('risks'),
                confidence=existing_data.get('confidence'),
                created_at=existing_summary.created_at
            )

        # Perform summarization
        # Service layer will convert 'neutral' -> None and handle storage decisions
        logger.info(f"Generating new summary for contract {contract_id} (role: {role or 'neutral'})")
        summary_data, error = summarize_contract(contract.text, contract_id, role)

        # Check for errors
        if error is not None:
            logger.error(f"Summarization failed for contract {contract_id}: {error}")

            # Check for specific error types
            if "too short" in error.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to generate summary: {error}"
                )

        # Store summary results in database
        logger.info(f"Storing summary for contract {contract_id} (role: {role or 'neutral'})")
        stored_summary = crud.create_contract_summary(db, contract_id, summary_data, storage_role)

        # Build response
        response = ContractSummaryResponse(
            contract_id=contract_id,
            summary_type=summary_data.get('summary_type', 'contract_overview'),
            role=role,
            summary=summary_data['summary'],
            key_points=summary_data['key_points'],
            parties=summary_data.get('parties'),
            key_dates=summary_data.get('key_dates'),
            financial_terms=summary_data.get('financial_terms'),
            obligations=summary_data.get('obligations'),
            rights=summary_data.get('rights'),
            termination=summary_data.get('termination'),
            risks=summary_data.get('risks'),
            confidence=summary_data.get('confidence'),
            created_at=stored_summary.created_at
        )

        logger.info(
            f"Successfully generated and stored summary for contract {contract_id} "
            f"(role: {role or 'neutral'}, type: {response.summary_type})"
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to summarize contract {contract_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate summary"
        )


# --------------------------
# Interactive Q&A Endpoint
# --------------------------

@app.post("/contracts/{contract_id}/ask", response_model=QAResponse)
def ask_contract_question(
    contract_id: int,
    req: QuestionRequest,
    db: Session = Depends(get_db)
) -> QAResponse:
    """
    Answer natural language questions about a contract using semantic search and AI.

    This endpoint enables interactive question-answering about contract content using
    semantic search with pgvector and GPT-4o-mini. The system:
    1. Generates an embedding for your question using OpenAI text-embedding-3-small
    2. Searches for the most relevant clauses using pgvector L2 distance similarity
    3. Retrieves the top 5 most similar clauses as context
    4. Uses GPT-4o-mini to generate a comprehensive answer based on the context
    5. Returns the answer with clause references and confidence level
    6. Stores the Q&A interaction in the database for future reference

    **Args:**
    - `contract_id` (int): Database ID of the contract to ask about
    - `question` (str): Natural language question about the contract (minimum 5 characters)

    **Returns:**
    - `QAResponse`: Comprehensive answer with:
        - Answer text (2-4 paragraphs)
        - List of clause database IDs used to generate the answer
        - Confidence level (high/medium/low)
        - Timestamp of the interaction

    **HTTP Status Codes:**
    - 200 OK: Question answered successfully
    - 400 Bad Request: Question too short or no clause embeddings found
    - 404 Not Found: Contract does not exist
    - 500 Internal Server Error: Q&A failed (OpenAI error, embedding error, etc.)

    **Example Usage:**
    ```bash
    curl -X POST http://localhost:8000/contracts/1/ask \\
      -H "Content-Type: application/json" \\
      -d '{"question": "Can the client terminate the contract early?"}'

    curl -X POST http://localhost:8000/contracts/1/ask \\
      -H "Content-Type: application/json" \\
      -d '{"question": "What are the payment terms and deadlines?"}'

    curl -X POST http://localhost:8000/contracts/1/ask \\
      -H "Content-Type: application/json" \\
      -d '{"question": "Who is responsible for maintaining confidentiality?"}'
    ```

    **How It Works:**
    1. **Question Embedding**: Generates a 1536-dimensional vector for your question
    2. **Semantic Search**: Uses pgvector's L2 distance to find 5 most relevant clauses
    3. **Context Building**: Formats retrieved clauses as context for the AI
    4. **Answer Generation**: GPT-4o-mini generates comprehensive answer from context
    5. **Clause Linking**: Returns database IDs of clauses used in the answer
    6. **History Storage**: Stores the Q&A interaction for future reference

    **Use Cases:**
    - **Quick Contract Review**: Get instant answers without reading entire contract
    - **Due Diligence**: Ask targeted questions about specific terms
    - **Negotiation Prep**: Understand key provisions before discussions
    - **Compliance Check**: Verify specific obligations and requirements
    - **Risk Assessment**: Ask about termination rights, liability, penalties

    **DISCLAIMER:**
    Answers are for informational purposes only and do NOT constitute legal advice.
    AI-generated answers are based on semantic search and may not capture all relevant
    clauses or nuances. Always review the full contract and consult qualified legal
    professionals for actual legal guidance.
    """
    try:
        # Validate contract exists
        contract = crud.get_contract(db, contract_id)
        if contract is None:
            logger.warning(f"Contract {contract_id} not found for Q&A")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Contract {contract_id} not found"
            )

        logger.info(f"Processing Q&A request for contract {contract_id}: {req.question[:100]}...")

        # Check for clauses with embeddings
        clauses = crud.get_clauses_by_contract(db, contract_id)
        clauses_with_embeddings = [c for c in clauses if c.embedding is not None]

        if not clauses_with_embeddings:
            logger.warning(f"No clause embeddings found for contract {contract_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No clause embeddings found. Contract may not have been fully processed. Please try re-uploading the contract."
            )

        logger.info(f"Found {len(clauses_with_embeddings)} clauses with embeddings for contract {contract_id}")

        # Perform Q&A
        qa_data, error = answer_question(db, contract_id, req.question, contract.text)

        # Check for errors
        if error is not None:
            logger.error(f"Q&A failed for contract {contract_id}: {error}")

            # Check for specific error types
            if "too short" in error.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error
                )
            elif "no clauses found" in error.lower() or "missing embeddings" in error.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=error
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to answer question: {error}"
                )

        # Extract data from qa_data
        answer = qa_data['answer']
        referenced_clause_ids = qa_data.get('referenced_clause_ids', [])
        confidence = qa_data.get('confidence')

        # Store Q&A history
        logger.info(f"Storing Q&A record for contract {contract_id}")
        qa_record = crud.create_qa_record(
            db, contract_id, req.question, answer, referenced_clause_ids, confidence
        )

        logger.info(
            f"Successfully answered question for contract {contract_id} "
            f"(referenced {len(referenced_clause_ids)} clauses, confidence: {confidence})"
        )

        # Build response
        response = QAResponse(
            id=qa_record.id,
            contract_id=contract_id,
            question=req.question,
            answer=answer,
            referenced_clauses=referenced_clause_ids,
            confidence=confidence,
            asked_at=qa_record.asked_at
        )

        return response

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Failed to answer question for contract {contract_id}: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to answer question"
        )

