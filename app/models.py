"""
SQLAlchemy ORM models for AI Legal Analyst database schema.

This module defines six core database tables with proper relationships:
- Contract: Stores uploaded contract documents
- Clause: Individual segmented clauses from contracts
- Entity: Extracted entities (parties, dates, terms, etc.)
- RiskAssessment: Risk analysis results for contracts and clauses
- Summary: Plain-language summaries from different perspectives
- QAHistory: Question-answer interactions for contract queries

All models use SQLAlchemy 2.0 declarative base with proper type hints,
relationships, and cascade deletion for data integrity.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.database import Base


class Contract(Base):
    """
    Represents a legal contract document uploaded to the system.

    A contract contains multiple clauses, entities, risk assessments,
    summaries, and Q&A interactions. Cascading deletes ensure all
    related data is removed when a contract is deleted.

    Attributes:
        id: Primary key
        title: Optional contract name/title
        text: Full contract text content
        jurisdiction: Jurisdiction code (e.g., 'UK', 'US_NY')
        uploaded_at: Timestamp when contract was uploaded
        processed_at: Timestamp when analysis completed
        status: Processing status (pending/processing/completed/failed)
        clauses: Related clause records
        entities: Related entity records
        risk_assessments: Related risk assessment records
        summaries: Related summary records
        qa_history: Related Q&A records
    """

    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[Optional[str]] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text)
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(100))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), default="pending")

    # Relationships with cascade delete
    clauses: Mapped[List["Clause"]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    entities: Mapped[List["Entity"]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    risk_assessments: Mapped[List["RiskAssessment"]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    summaries: Mapped[List["Summary"]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    qa_history: Mapped[List["QAHistory"]] = relationship(
        back_populates="contract",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


class Clause(Base):
    """
    Represents an individual clause segmented from a contract.

    Clauses are identified by numbered headings (e.g., "2.1 Termination")
    and include vector embeddings for semantic search capabilities.

    Attributes:
        id: Primary key
        contract_id: Foreign key to parent contract
        clause_id: UUID identifier from segmentation logic
        number: Clause number (e.g., '2.1')
        title: Clause heading text
        text: Full clause body text
        embedding: OpenAI embedding vector (1536 dimensions)
        created_at: Timestamp when clause was created
        contract: Parent contract relationship
        risk_assessments: Related risk assessment records
    """

    __tablename__ = "clauses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"))
    clause_id: Mapped[str] = mapped_column(String(100))
    number: Mapped[Optional[str]] = mapped_column(String(50))
    title: Mapped[Optional[str]] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Optional[Vector]] = mapped_column(Vector(1536))  # text-embedding-3-small dimensions
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    contract: Mapped["Contract"] = relationship(back_populates="clauses")
    risk_assessments: Mapped[List["RiskAssessment"]] = relationship(
        back_populates="clause",
        passive_deletes=True
    )

    # Indexes and constraints for performance and data integrity
    __table_args__ = (
        Index("ix_clauses_contract_id", "contract_id"),
        Index("ix_clauses_clause_id", "clause_id"),
        UniqueConstraint("contract_id", "clause_id", name="uq_clauses_contract_clause"),
    )


class Entity(Base):
    """
    Represents an extracted entity from a contract.

    Entities include parties, dates, financial terms, governing law,
    obligations, and other key information extracted using NER.

    Attributes:
        id: Primary key
        contract_id: Foreign key to parent contract
        entity_type: Entity category (party/date/financial_term/etc.)
        value: Extracted entity value
        context: Surrounding text for context
        confidence: Extraction confidence level (high/medium/low)
        extracted_at: Timestamp when entity was extracted
        contract: Parent contract relationship
    """

    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"))
    entity_type: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(Text)
    context: Mapped[Optional[str]] = mapped_column(Text)
    confidence: Mapped[Optional[str]] = mapped_column(String(20))
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    contract: Mapped["Contract"] = relationship(back_populates="entities")

    # Indexes for filtered queries
    __table_args__ = (
        Index("ix_entities_contract_id_type", "contract_id", "entity_type"),
    )


class RiskAssessment(Base):
    """
    Represents a risk assessment for a contract or specific clause.

    Risk assessments identify potential issues such as unfavorable
    termination rights, indemnity clauses, penalties, and liability caps.

    Attributes:
        id: Primary key
        contract_id: Foreign key to parent contract
        clause_id: Optional foreign key to specific clause
        risk_type: Risk category (termination_rights/indemnity/etc.)
        risk_level: Severity level (low/medium/high)
        description: Risk explanation
        justification: Reasoning for risk assessment
        recommendation: Suggested mitigation strategy
        assessed_at: Timestamp when assessment was performed
        contract: Parent contract relationship
        clause: Optional parent clause relationship
    """

    __tablename__ = "risk_assessments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"))
    clause_id: Mapped[Optional[int]] = mapped_column(ForeignKey("clauses.id", ondelete="CASCADE"))
    risk_type: Mapped[str] = mapped_column(String(100))
    risk_level: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    justification: Mapped[str] = mapped_column(Text)
    recommendation: Mapped[Optional[str]] = mapped_column(Text)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    contract: Mapped["Contract"] = relationship(back_populates="risk_assessments")
    clause: Mapped[Optional["Clause"]] = relationship(back_populates="risk_assessments")

    # Indexes for filtering high-risk items
    __table_args__ = (
        Index("ix_risk_assessments_contract_risk", "contract_id", "risk_level"),
    )


class Summary(Base):
    """
    Represents a plain-language summary of a contract.

    Summaries can be general overviews or role-specific perspectives
    (supplier, client, neutral) to highlight relevant information.

    Attributes:
        id: Primary key
        contract_id: Foreign key to parent contract
        summary_type: Summary category (contract_overview/role_specific)
        role: Perspective (supplier/client/neutral)
        content: Plain-language summary text
        created_at: Timestamp when summary was generated
        contract: Parent contract relationship
    """

    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"))
    summary_type: Mapped[str] = mapped_column(String(50))
    role: Mapped[Optional[str]] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    contract: Mapped["Contract"] = relationship(back_populates="summaries")

    # Indexes for role-specific queries
    __table_args__ = (
        Index("ix_summaries_contract_role", "contract_id", "role"),
    )


class QAHistory(Base):
    """
    Represents a question-answer interaction for a contract.

    QA history enables conversational queries about contracts with
    references to specific clauses used in generating answers.

    Attributes:
        id: Primary key
        contract_id: Foreign key to parent contract
        question: User's natural language query
        answer: AI-generated answer
        referenced_clauses: JSON array of clause IDs used in answer
        confidence: Answer confidence level
        asked_at: Timestamp when question was asked
        contract: Parent contract relationship
    """

    __tablename__ = "qa_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    referenced_clauses: Mapped[Optional[str]] = mapped_column(Text)  # JSON string of clause IDs
    confidence: Mapped[Optional[str]] = mapped_column(String(20))
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    contract: Mapped["Contract"] = relationship(back_populates="qa_history")

    # Indexes for conversation history
    __table_args__ = (
        Index("ix_qa_history_contract_id", "contract_id"),
    )
