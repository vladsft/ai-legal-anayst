"""
Pydantic schemas for API request/response models.

This module defines the API contract and is separate from SQLAlchemy ORM models
in app/models.py. This separation follows best practices for API design and allows
independent evolution of database schema and API responses.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List
from datetime import datetime


# Request Schemas

class ContractUploadRequest(BaseModel):
    """
    Request schema for uploading and processing a contract.

    This replaces the current UploadRequest in app/main.py.
    """
    text: str = Field(..., min_length=1, description="Full contract text content")
    title: Optional[str] = Field(None, description="Optional contract name/title")
    jurisdiction: Optional[str] = Field(None, description="Optional jurisdiction hint (e.g., 'UK', 'US', 'EU')")

    @field_validator('text')
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        """Validate that text is not empty or whitespace only."""
        if not v or not v.strip():
            raise ValueError('Contract text must not be empty')
        return v


# Response Schemas

class ClauseResponse(BaseModel):
    """
    Response schema representing a segmented clause in API responses.

    This schema is returned as part of the contract segmentation response
    and represents an individual clause extracted from the contract.
    """
    model_config = ConfigDict(from_attributes=True)

    clause_id: str = Field(..., description="UUID identifier for the clause")
    number: Optional[str] = Field(None, description="Clause number like '2.1' or '3.4.2'")
    title: Optional[str] = Field(None, description="Clause heading/title")
    text: str = Field(..., description="Clause body text content")


class EntityResponse(BaseModel):
    """
    Response schema representing an extracted entity from the contract.

    Entities are key pieces of information extracted using AI analysis,
    such as parties, dates, financial terms, governing laws, and obligations.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Database primary key")
    entity_type: str = Field(..., description="Type of entity (party/date/financial_term/governing_law/obligation)")
    value: str = Field(..., description="Extracted entity value")
    context: Optional[str] = Field(None, description="Surrounding text providing context")
    confidence: Optional[str] = Field(None, description="Extraction confidence level (high/medium/low)")
    extracted_at: datetime = Field(..., description="Timestamp when the entity was extracted")


class ContractSegmentResponse(BaseModel):
    """
    Response schema for the POST /contracts/segment endpoint.

    This is the main response returned after uploading and processing a contract.
    It includes the created contract ID, processing status, segmented clauses,
    and extracted entities.

    Status values:
    - 'completed': Both segmentation and entity extraction succeeded
    - 'completed_with_warnings': Segmentation succeeded but entity extraction failed (clauses still available)
    - 'failed': Processing failed entirely
    """
    contract_id: int = Field(..., description="Database ID of the created contract")
    status: str = Field(..., description="Processing status: 'completed', 'completed_with_warnings', or 'failed'")
    clauses: List[ClauseResponse] = Field(default_factory=list, description="List of segmented clauses")
    entities: List[EntityResponse] = Field(default_factory=list, description="List of extracted entities")
    message: str = Field(..., description="Success message with counts and details")


class EntitiesListResponse(BaseModel):
    """
    Response schema for the GET /contracts/{id}/entities endpoint.

    This response provides all extracted entities for a specific contract,
    along with statistics and breakdown by entity type.
    """
    contract_id: int = Field(..., description="Contract database ID")
    entities: List[EntityResponse] = Field(default_factory=list, description="List of entities")
    total_count: int = Field(..., description="Total number of entities")
    entity_types: dict = Field(default_factory=dict, description="Breakdown by type (e.g., {'party': 2, 'date': 5})")
