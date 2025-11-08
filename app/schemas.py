"""
Pydantic schemas for API request/response models.

This module defines the API contract and is separate from SQLAlchemy ORM models
in app/models.py. This separation follows best practices for API design and allows
independent evolution of database schema and API responses.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict
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


class QuestionRequest(BaseModel):
    """
    Request schema for asking questions about a contract.

    This is used by the POST /contracts/{id}/ask endpoint to enable
    interactive Q&A functionality using semantic search and AI.
    """
    question: str = Field(..., min_length=5, description="User's natural language question about the contract")

    @field_validator('question')
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        """Validate that question is not empty or whitespace only and meets minimum length."""
        if not v or not v.strip():
            raise ValueError('Question must not be empty')
        if len(v.strip()) < 5:
            raise ValueError('Question must be at least 5 characters long')
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


class JurisdictionAnalysisResponse(BaseModel):
    """
    Response schema for the POST /contracts/{id}/analyze-jurisdiction endpoint.

    This is the main response returned after performing UK contract law analysis.
    It includes jurisdiction detection, applicable statutes, legal principles,
    enforceability assessment, clause interpretations, and recommendations.

    The analysis is performed using OpenAI GPT-4o and provides comprehensive
    legal insights specific to UK (England and Wales) contract law.

    DISCLAIMER: This analysis is for informational purposes only and does NOT
    constitute legal advice. Consult qualified legal professionals for actual
    legal guidance on contract matters.
    """
    model_config = ConfigDict(from_attributes=True)

    contract_id: int = Field(..., description="Contract database ID")
    jurisdiction_confirmed: str = Field(..., description="Detected jurisdiction (e.g., 'England and Wales', 'UK', 'Scotland', 'Northern Ireland', or 'Unknown')")
    confidence: str = Field(..., description="Detection confidence level: 'high' (explicit law selection), 'medium' (strong indicators), or 'low' (uncertain)")
    applicable_statutes: List[str] = Field(default_factory=list, description="List of relevant UK statutes (e.g., 'Consumer Rights Act 2015', 'Unfair Contract Terms Act 1977')")
    legal_principles: List[str] = Field(default_factory=list, description="Key UK legal principles that apply (e.g., 'Freedom of contract', 'Contra proferentem rule')")
    enforceability_assessment: str = Field(..., description="Overall enforceability assessment under UK law (comprehensive 2-4 paragraph analysis)")
    key_considerations: List[str] = Field(default_factory=list, description="Important UK-specific legal points and potential issues")
    clause_interpretations: List[dict] = Field(default_factory=list, description="Clause-specific interpretations with 'clause' and 'interpretation' fields")
    recommendations: List[str] = Field(default_factory=list, description="Suggestions for improving UK law compliance")
    analyzed_at: datetime = Field(..., description="Timestamp when the analysis was performed")

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: str) -> str:
        """Validate that confidence is one of 'high', 'medium', or 'low' and normalize to lowercase."""
        if not v:
            raise ValueError('Confidence value must not be empty')
        normalized = v.lower()
        valid_values = ['high', 'medium', 'low']
        if normalized not in valid_values:
            raise ValueError(f"Confidence must be one of {valid_values}, got '{v}'")
        return normalized


class JurisdictionSummaryResponse(BaseModel):
    """
    Response schema for simplified jurisdiction analysis summaries.

    This is a condensed version of JurisdictionAnalysisResponse, useful for
    listing or displaying jurisdiction information without full analysis details.
    Contains only the key summary information.
    """
    model_config = ConfigDict(from_attributes=True)

    contract_id: int = Field(..., description="Contract database ID")
    jurisdiction: str = Field(..., description="Confirmed jurisdiction")
    confidence: str = Field(..., description="Detection confidence level: 'high', 'medium', or 'low'")
    enforceability: str = Field(..., description="Brief enforceability summary (first 200 characters)")
    analyzed_at: datetime = Field(..., description="Timestamp when the analysis was performed")


class RiskAssessmentResponse(BaseModel):
    """
    Response schema representing a single risk assessment.

    This represents one identified risk in a contract, including its category,
    severity level, detailed analysis, and actionable recommendations.
    Can be clause-specific (with clause_id) or contract-level (clause_id=None).
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Database primary key")
    contract_id: int = Field(..., description="Contract database ID")
    clause_id: Optional[int] = Field(None, description="Clause database ID if risk is clause-specific, None for contract-level risks")
    risk_type: str = Field(..., description="Risk category (termination_rights/indemnity/penalty/liability_cap/payment_terms/intellectual_property/confidentiality/warranty/force_majeure/dispute_resolution)")
    risk_level: str = Field(..., description="Severity level: 'low', 'medium', or 'high'")
    description: str = Field(..., description="Clear 2-3 sentence explanation of the risk")
    justification: str = Field(..., description="Detailed 3-5 sentence reasoning for the risk level assessment")
    recommendation: Optional[str] = Field(None, description="Specific actionable mitigation strategy")
    assessed_at: datetime = Field(..., description="Timestamp when the assessment was performed")

    @field_validator('risk_level')
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        """Validate that risk_level is one of 'low', 'medium', or 'high' and normalize to lowercase."""
        if not v:
            raise ValueError('Risk level must not be empty')
        normalized = v.lower()
        valid_values = ['low', 'medium', 'high']
        if normalized not in valid_values:
            raise ValueError(f"Risk level must be one of {valid_values}, got '{v}'")
        return normalized

    @field_validator('risk_type')
    @classmethod
    def validate_risk_type(cls, v: str) -> str:
        """Validate that risk_type is one of the defined risk types and normalize to lowercase."""
        if not v:
            raise ValueError('Risk type must not be empty')
        normalized = v.lower()
        valid_types = [
            'termination_rights', 'indemnity', 'penalty', 'liability_cap',
            'payment_terms', 'intellectual_property', 'confidentiality',
            'warranty', 'force_majeure', 'dispute_resolution'
        ]
        if normalized not in valid_types:
            raise ValueError(f"Risk type must be one of {valid_types}, got '{v}'")
        return normalized


class RiskAnalysisResponse(BaseModel):
    """
    Response schema for the POST /contracts/{id}/analyze-risks endpoint.

    This is the main response returned after performing comprehensive risk analysis.
    It includes all identified risks, total risk count, and a summary breakdown
    showing the distribution of risks across severity levels.

    The risk_summary field provides a quick overview (e.g., {'high': 2, 'medium': 5, 'low': 3})
    without needing to iterate through all risks.

    DISCLAIMER: This analysis is for informational purposes only and does NOT
    constitute legal advice. Consult qualified legal professionals for actual
    legal guidance on contract risks and mitigation strategies.
    """
    contract_id: int = Field(..., description="Contract database ID")
    risks: List[RiskAssessmentResponse] = Field(default_factory=list, description="List of identified risks")
    total_risks: int = Field(..., description="Total number of risks found")
    risk_summary: dict = Field(default_factory=dict, description="Breakdown by severity level (e.g., {'high': 2, 'medium': 5, 'low': 3})")
    analyzed_at: datetime = Field(..., description="Timestamp when the analysis was performed")


class RiskFilterParams(BaseModel):
    """
    Optional filter parameters for querying risk assessments.

    This schema enables filtering risks in GET endpoints by severity level,
    risk type, or specific clause. All fields are optional.
    """
    risk_level: Optional[str] = Field(None, description="Filter by risk level: 'low', 'medium', or 'high'")
    risk_type: Optional[str] = Field(None, description="Filter by risk type (e.g., 'termination_rights', 'indemnity')")
    clause_id: Optional[int] = Field(None, description="Filter by specific clause database ID")

    @field_validator('risk_level')
    @classmethod
    def validate_risk_level(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize risk_level if provided."""
        if v is None:
            return v
        normalized = v.lower()
        valid_values = ['low', 'medium', 'high']
        if normalized not in valid_values:
            raise ValueError(f"Risk level must be one of {valid_values}, got '{v}'")
        return normalized

    @field_validator('risk_type')
    @classmethod
    def validate_risk_type(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize risk_type if provided."""
        if v is None:
            return v
        normalized = v.lower()
        valid_types = [
            'termination_rights', 'indemnity', 'penalty', 'liability_cap',
            'payment_terms', 'intellectual_property', 'confidentiality',
            'warranty', 'force_majeure', 'dispute_resolution'
        ]
        if normalized not in valid_types:
            raise ValueError(f"Risk type must be one of {valid_types}, got '{v}'")
        return normalized


class ContractSummaryResponse(BaseModel):
    """
    Response schema for the POST /contracts/{id}/summarize endpoint.

    This is the main response returned after generating a plain-language summary.
    It includes a clear, accessible translation of the contract's key terms,
    parties, dates, financial information, obligations, rights, and risks.

    The summary can be neutral (balanced perspective) or role-specific (highlighting
    concerns from supplier or client perspective).

    DISCLAIMER: This summary is for informational purposes only and does NOT
    constitute legal advice. AI-generated summaries may not capture all nuances
    or important details. Always review full contracts and consult qualified
    legal professionals for actual legal guidance.
    """
    model_config = ConfigDict(from_attributes=True)

    contract_id: int = Field(..., description="Contract database ID")
    summary_type: str = Field(..., description="Type of summary: 'contract_overview' (neutral) or 'role_specific' (supplier/client perspective)")
    role: Optional[str] = Field(None, description="Role perspective if role-specific: 'supplier', 'client', or None for neutral")
    summary: str = Field(..., description="Main plain-language summary (3-5 well-structured paragraphs explaining the contract's purpose, key terms, and overall structure)")
    key_points: List[str] = Field(..., description="List of 5-10 most important points from the contract, in order of significance")
    parties: Optional[str] = Field(None, description="Brief description of the parties involved (who is contracting with whom)")
    key_dates: Optional[List[str]] = Field(None, description="List of important dates, deadlines, milestones, and time periods")
    financial_terms: Optional[str] = Field(None, description="Clear summary of payment terms, amounts, schedules, and any financial penalties or incentives")
    obligations: Optional[Dict[str, List[str]]] = Field(None, description="Key obligations by party (e.g., {'supplier': [...], 'client': [...]})")
    rights: Optional[Dict[str, List[str]]] = Field(None, description="Key rights and protections by party (e.g., {'supplier': [...], 'client': [...]})")
    termination: Optional[str] = Field(None, description="Explanation of how and when the contract can be terminated, including notice periods and conditions")
    risks: Optional[List[str]] = Field(None, description="Top 3-5 risks or concerns to be aware of (brief overview, not detailed legal analysis)")
    confidence: Optional[str] = Field(None, description="Confidence in the summary quality: 'high', 'medium', or 'low'")
    created_at: datetime = Field(..., description="Timestamp when the summary was generated")

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        """Validate that role is one of 'supplier', 'client', 'neutral' or None, and normalize to lowercase.

        Note: 'neutral' is converted to None to match storage representation.
        """
        if v is None:
            return v
        normalized = v.lower()
        valid_values = ['supplier', 'client', 'neutral']
        if normalized not in valid_values:
            raise ValueError(f"Role must be one of {valid_values} or None, got '{v}'")
        # Convert 'neutral' to None to match storage representation
        if normalized == 'neutral':
            return None
        return normalized

    @field_validator('summary_type')
    @classmethod
    def validate_summary_type(cls, v: str) -> str:
        """Validate that summary_type is one of 'contract_overview' or 'role_specific' and normalize to lowercase."""
        if not v:
            raise ValueError('Summary type must not be empty')
        normalized = v.lower()
        valid_values = ['contract_overview', 'role_specific']
        if normalized not in valid_values:
            raise ValueError(f"Summary type must be one of {valid_values}, got '{v}'")
        return normalized

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: Optional[str]) -> Optional[str]:
        """Validate that confidence is one of 'high', 'medium', or 'low' and normalize to lowercase."""
        if v is None:
            return v
        normalized = v.lower()
        valid_values = ['high', 'medium', 'low']
        if normalized not in valid_values:
            raise ValueError(f"Confidence must be one of {valid_values}, got '{v}'")
        return normalized


class SummaryListResponse(BaseModel):
    """
    Response schema for listing all summaries for a contract.

    This schema is useful for a future GET endpoint that retrieves all available
    summaries (both neutral and role-specific) for a given contract. Enables
    clients to see all perspectives that have been generated.
    """
    contract_id: int = Field(..., description="Contract database ID")
    summaries: List[ContractSummaryResponse] = Field(default_factory=list, description="List of summaries (neutral and role-specific)")
    total_count: int = Field(..., description="Total number of summaries available")


class QAResponse(BaseModel):
    """
    Response schema for the POST /contracts/{id}/ask endpoint.

    This is the main response returned after asking a question about a contract.
    It includes the AI-generated answer, list of clause IDs used to generate the
    answer, confidence level, and timestamps for the interaction.

    The referenced_clauses field contains database IDs of clauses that were used
    to generate the answer, enabling clients to fetch full clause text for verification.

    DISCLAIMER: This answer is for informational purposes only and does NOT
    constitute legal advice. AI-generated answers are based on semantic search
    and may not capture all relevant clauses or nuances. Always review the full
    contract and consult qualified legal professionals for actual legal guidance.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Database primary key of the Q&A record")
    contract_id: int = Field(..., description="Contract database ID")
    question: str = Field(..., description="User's natural language question")
    answer: str = Field(..., description="AI-generated comprehensive answer (2-4 paragraphs)")
    referenced_clauses: List[int] = Field(default_factory=list, description="List of clause database IDs used to generate the answer")
    confidence: Optional[str] = Field(None, description="Answer confidence level: 'high' (directly supported by clear clauses), 'medium' (requires interpretation), or 'low' (partially supported or vague)")
    asked_at: datetime = Field(..., description="Timestamp when the question was asked")

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: Optional[str]) -> Optional[str]:
        """Validate that confidence is one of 'high', 'medium', or 'low' and normalize to lowercase."""
        if v is None:
            return v
        normalized = v.lower()
        valid_values = ['high', 'medium', 'low']
        if normalized not in valid_values:
            raise ValueError(f"Confidence must be one of {valid_values}, got '{v}'")
        return normalized


class QAHistoryResponse(BaseModel):
    """
    Response schema for listing Q&A conversation history for a contract.

    This schema is useful for a future GET endpoint that retrieves the Q&A
    conversation history for a given contract. Enables clients to review
    previously asked questions and their answers.
    """
    contract_id: int = Field(..., description="Contract database ID")
    qa_history: List[QAResponse] = Field(default_factory=list, description="List of Q&A interactions ordered by most recent first")
    total_count: int = Field(..., description="Total number of Q&A records available")
