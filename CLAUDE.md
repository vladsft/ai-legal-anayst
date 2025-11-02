# CLAUDE.md

This file provides comprehensive guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI Legal Contract Analyst** is an AI-powered legal contract analysis system that provides:
- Automated contract clause segmentation
- AI-powered entity extraction (parties, dates, financial terms, laws, obligations)
- Jurisdiction-aware legal analysis (UK contract law focus)
- Comprehensive risk assessment across 10 risk categories
- Database persistence with PostgreSQL + pgvector for future semantic search

**Current Status**: Phase 3 complete (Risk Analysis). System is production-ready for contract processing, entity extraction, UK jurisdiction analysis, and risk assessment.

## Architecture Overview

### Technology Stack

- **FastAPI**: Modern async Python web framework (v0.104+)
- **PostgreSQL 14+**: Relational database with pgvector extension
- **pgvector**: Vector similarity search for semantic analysis (text-embedding-3-small, 1536 dimensions)
- **SQLAlchemy 2.0**: Modern ORM with type hints and declarative base
- **OpenAI GPT-4o**: AI model for entity extraction, jurisdiction analysis, and risk assessment
- **Pydantic v2**: Data validation and settings management
- **Uvicorn**: ASGI server with hot reload support

### System Architecture

```
┌─────────────────┐
│   FastAPI App   │  - 5 endpoints (health, segment, entities, jurisdiction, risks)
│   (app/main.py) │  - Regex-based clause segmentation
└────────┬────────┘
         │
         ├──> Services (app/services/)
         │    ├── entity_extractor.py    - OpenAI GPT-4o entity extraction
         │    ├── jurisdiction_analyzer.py - UK law analysis with statute identification
         │    ├── risk_analyzer.py       - 10-category risk detection
         │    └── openai_client.py       - Shared OpenAI client (thread-safe)
         │
         ├──> CRUD Layer (app/crud.py)
         │    - Database operations for all entities
         │    - Bulk inserts, filtering, aggregation
         │    - Transaction management
         │
         ├──> Database (app/database.py, app/models.py)
         │    - 6 tables: contracts, clauses, entities, risk_assessments, summaries, qa_history
         │    - pgvector extension for embeddings
         │    - Cascade delete relationships
         │
         └──> Configuration (app/config.py)
              - Pydantic settings with environment variables
              - Lazy initialization, cached instances
```

## Core Modules

### 1. [app/main.py](app/main.py) - FastAPI Application & Endpoints

**Purpose**: Main application entry point with API endpoints and core segmentation logic.

**Key Functions**:

- **`segment_contract(text: str) -> List[dict]`** (lines 60-107)
  - Pure function for clause segmentation using regex
  - No AI/database calls - intentionally kept simple
  - Uses `HEADING_RX` to match numbered headings (e.g., "2.1 Termination")
  - Uses `BULLET_JOIN_RX` to prevent splitting bullet points
  - Returns list of dicts with `clause_id` (UUID), `number`, `title`, `text`
  - Handles documents with no headings (returns single clause)

**API Endpoints**:

1. **`GET /health`** (lines 113-123)
   - Health check endpoint
   - Returns service status and version

2. **`POST /contracts/segment`** (lines 125-319)
   - Main contract processing endpoint
   - **Request**: `ContractUploadRequest` with `text` (required), `title`, `jurisdiction` (optional)
   - **Processing Flow**:
     1. Creates contract in database (`crud.create_contract`)
     2. Updates status to 'processing'
     3. Segments contract into clauses (`segment_contract`)
     4. Persists clauses to database (`crud.bulk_create_clauses`)
     5. Extracts entities using OpenAI GPT-4o (`extract_entities`)
     6. Persists entities to database (`crud.bulk_create_entities`)
     7. Auto-detects jurisdiction if not provided (`analyze_jurisdiction`)
     8. Updates contract status to 'completed' or 'completed_with_warnings'
   - **Response**: `ContractSegmentResponse` with contract_id, status, clauses, entities, message
   - **Error Handling**:
     - Returns 409 Conflict for duplicate clause IDs
     - Returns 500 for processing failures
     - Partial success: clauses saved even if entity extraction fails

3. **`GET /contracts/{contract_id}/entities`** (lines 322-386)
   - Retrieves extracted entities for a contract
   - Optional `entity_type` query parameter for filtering
   - Returns entities with total count and type breakdown
   - Returns 404 if contract not found

4. **`POST /contracts/{contract_id}/analyze-jurisdiction`** (lines 389-509)
   - Analyzes contract through UK contract law lens
   - **Caching**: Returns cached analysis if available (stored in `summaries` table)
   - **OpenAI Analysis**: Identifies statutes, principles, enforceability, clause interpretations
   - Updates contract's `jurisdiction` field with normalized code
   - Returns 404 if contract not found, 400 for short contracts, 500 for analysis failures

5. **`POST /contracts/{contract_id}/analyze-risks`** (lines 512-692)
   - Comprehensive risk assessment across 10 categories
   - **Caching**: Returns cached risks if available (stored in `risk_assessments` table)
   - **Risk Categories**: termination_rights, indemnity, penalty, liability_cap, payment_terms, intellectual_property, confidentiality, warranty, force_majeure, dispute_resolution
   - **Risk Levels**: low, medium, high with detailed justifications
   - Links risks to specific clauses via `clause_id`
   - Returns risk summary with severity distribution

**Regex Patterns**:
- `HEADING_RX` (line 54): `r'(?m)^\s*(\d+(?:\.\d+)*)\s+([A-Z][^\n]{0,100})\s*$'`
  - Matches numbered headings at start of line
  - Captures number (e.g., "2.1") and title (e.g., "Termination")
  - Requires title to start with capital letter, max 100 chars
- `BULLET_JOIN_RX` (line 58): `r'\n(?=[•\-–]\s)'`
  - Prevents splitting bullet points into separate clauses

---

### 2. [app/models.py](app/models.py) - Database Schema (SQLAlchemy ORM)

**Purpose**: Defines 6 database tables with relationships and constraints.

**Tables**:

1. **`Contract`** (lines 24-82)
   - Stores uploaded contract documents
   - **Fields**: id (PK), title, text, jurisdiction, uploaded_at, processed_at, status
   - **Status values**: 'pending', 'processing', 'completed', 'completed_with_warnings', 'failed'
   - **Relationships**: clauses, entities, risk_assessments, summaries, qa_history (all with cascade delete)

2. **`Clause`** (lines 85-128)
   - Individual segmented clauses from contracts
   - **Fields**: id (PK), contract_id (FK), clause_id (UUID), number, title, text, embedding (Vector[1536]), created_at
   - **Unique Constraint**: `uq_clauses_contract_clause` on (contract_id, clause_id)
   - **Indexes**: ix_clauses_contract_id, ix_clauses_clause_id
   - **Embedding**: OpenAI text-embedding-3-small (1536 dimensions) for semantic search

3. **`Entity`** (lines 131-165)
   - Extracted entities from contracts (parties, dates, etc.)
   - **Fields**: id (PK), contract_id (FK), entity_type, value, context, confidence, extracted_at
   - **Entity Types**: party, date, financial_term, governing_law, obligation (normalized to lowercase)
   - **Index**: ix_entities_contract_id_type for filtered queries

4. **`RiskAssessment`** (lines 168-208)
   - Risk assessment results
   - **Fields**: id (PK), contract_id (FK), clause_id (FK, optional), risk_type, risk_level, description, justification, recommendation, assessed_at
   - **Risk Types**: termination_rights, indemnity, penalty, liability_cap, payment_terms, intellectual_property, confidentiality, warranty, force_majeure, dispute_resolution
   - **Risk Levels**: low, medium, high (normalized to lowercase)
   - **Index**: ix_risk_assessments_contract_risk (contract_id, risk_level)

5. **`Summary`** (lines 211-243)
   - Stores various summary types (jurisdiction analysis, future summaries)
   - **Fields**: id (PK), contract_id (FK), summary_type, role, content (JSON), created_at
   - **Summary Types**: 'jurisdiction_analysis' (used for caching UK law analysis), 'role_specific' (future), 'plain_language' (future)
   - **Index**: ix_summaries_contract_role

6. **`QAHistory`** (lines 246-280)
   - Question-answer interaction history (future phase)
   - **Fields**: id (PK), contract_id (FK), question, answer, referenced_clauses (JSON), confidence, asked_at
   - **Index**: ix_qa_history_contract_id

**Cascade Deletion**: All child tables have `ondelete="CASCADE"` for clean data removal.

---

### 3. [app/crud.py](app/crud.py) - Database Operations

**Purpose**: Reusable CRUD operations with proper error handling and transaction management.

**Key Functions**:

**Contracts** (lines 45-198):
- `create_contract(db, title, text, jurisdiction)` - Creates contract with 'pending' status
- `get_contract(db, contract_id)` - Retrieves contract by ID
- `get_contracts(db, skip=0, limit=100)` - Pagination support
- `update_contract_status(db, contract_id, status, processed_at)` - Tracks processing state
- `update_contract_jurisdiction(db, contract_id, jurisdiction)` - Updates after analysis
- `delete_contract(db, contract_id)` - Cascade deletes all related data

**Clauses** (lines 205-336):
- `create_clause(db, contract_id, clause_id, number, title, text)` - Single insert
  - Raises `DuplicateClauseError` if (contract_id, clause_id) already exists
- `get_clauses_by_contract(db, contract_id)` - Retrieves all clauses
- `bulk_create_clauses(db, clauses)` - Efficient batch insert
  - **Important**: Does NOT populate auto-generated IDs on objects
  - Raises `DuplicateClauseError` on unique constraint violation

**Entities** (lines 343-473):
- `create_entity(db, contract_id, entity_type, value, context, confidence)` - Single insert
  - Normalizes entity_type to lowercase
- `get_entities_by_contract(db, contract_id)` - All entities
- `get_entities_by_type(db, contract_id, entity_type)` - Filtered by type
- `count_entities_by_type(db, contract_id)` - Aggregation for statistics
- `bulk_create_entities(db, entities)` - Batch insert with IDs populated

**Jurisdiction Analysis** (lines 507-737):
- `create_summary(db, contract_id, summary_type, content, role)` - Generic summary storage
- `get_summaries_by_contract(db, contract_id, summary_type)` - Filtered retrieval
- `get_latest_summary(db, contract_id, summary_type)` - Most recent
- `create_jurisdiction_analysis(db, contract_id, analysis_data)` - Convenience wrapper (JSON serialization)
- `get_jurisdiction_analysis(db, contract_id)` - Returns (Summary, parsed_dict) tuple

**Risk Assessments** (lines 744-1019):
- `create_risk_assessment(db, contract_id, risk_type, risk_level, description, justification, clause_id, recommendation)` - Single insert
  - Normalizes risk_type and risk_level to lowercase
- `get_risk_assessments_by_contract(db, contract_id, risk_level)` - Filtered by level
  - **Sorting**: High → Medium → Low, then by assessed_at desc
- `get_risk_assessments_by_clause(db, clause_id)` - Clause-specific risks
- `count_risks_by_level(db, contract_id)` - Aggregation for summary
- `count_risks_by_type(db, contract_id)` - Category breakdown
- `bulk_create_risk_assessments(db, risk_assessments)` - Batch insert
- `delete_risk_assessments_by_contract(db, contract_id)` - For re-analysis
- `get_high_risk_assessments(db, contract_id)` - Convenience filter

**Custom Exceptions**:
- `DuplicateClauseError` (lines 29-37) - Raised on unique constraint violation for (contract_id, clause_id)

---

### 4. [app/services/entity_extractor.py](app/services/entity_extractor.py) - AI Entity Extraction

**Purpose**: Extracts structured entities from contracts using OpenAI GPT-4o.

**Model**: gpt-4o with temperature=0.1 (deterministic), JSON mode enabled

**Entity Types** (line 40):
- `party`: Companies, individuals, organizations
- `date`: Effective dates, deadlines, milestones
- `financial_term`: Monetary amounts, payment terms, fees
- `governing_law`: Jurisdictions, applicable laws
- `obligation`: Duties and responsibilities

**Key Function**:
- **`extract_entities(contract_text: str) -> Tuple[List[Dict], Optional[str]]`** (lines 122-238)
  - **Input Validation**: Minimum 50 characters
  - **Returns**: `(list_of_entities, error_message)` tuple
    - On success: `([{entity_type, value, context, confidence}, ...], None)`
    - On failure: `([], "error message")`
  - **Output Fields**: entity_type, value (1-10 words), context (1-2 sentences), confidence (high/medium/low)
  - **Validation**: Filters invalid entity types, defaults confidence to "medium", truncates long contexts (>500 chars)
  - **Error Handling**: Returns empty list + error message on failures (API errors, JSON parsing, validation)

**System Prompt** (lines 43-119):
- Instructs AI to act as legal contract analyst
- Defines each entity type with examples
- Specifies JSON output format
- Emphasizes accuracy over quantity

---

### 5. [app/services/jurisdiction_analyzer.py](app/services/jurisdiction_analyzer.py) - UK Law Analysis

**Purpose**: Analyzes contracts through UK contract law lens using OpenAI GPT-4o.

**Model**: gpt-4o with temperature=0.2 (slight creativity for legal reasoning), JSON mode enabled

**Key Function**:
- **`analyze_jurisdiction(contract_text: str, contract_id: int) -> Tuple[Dict, Optional[str]]`** (lines 195-342)
  - **Input Validation**: Minimum 100 characters
  - **Token Limit Protection**: Truncates contracts >200k chars to 150k chars
  - **Returns**: `(analysis_dict, error_message)` tuple
  - **Analysis Components**:
    - `jurisdiction_confirmed`: Human-readable (e.g., "England and Wales")
    - `jurisdiction_code`: Normalized code (e.g., "UK_EW") for database storage
    - `confidence`: high/medium/low (normalized to lowercase)
    - `applicable_statutes`: List of UK statutes (e.g., ["Consumer Rights Act 2015"])
    - `legal_principles`: List of principles (e.g., ["Freedom of contract"])
    - `enforceability_assessment`: Comprehensive 2-4 paragraph analysis
    - `key_considerations`: Important UK-specific legal points
    - `clause_interpretations`: Array of {clause, interpretation} objects
    - `recommendations`: Suggestions for UK law compliance
  - **Validation**: Checks required fields, confidence level, list field types, clause interpretation structure

**Jurisdiction Normalization** (lines 78-128):
- **`normalize_jurisdiction(jurisdiction: str) -> str`** - Maps freeform strings to canonical codes
- **Mapping** (lines 66-75):
  - 'england and wales', 'uk', 'united kingdom', 'england', 'wales' → 'UK_EW'
  - 'scotland' → 'UK_SC'
  - 'northern ireland' → 'UK_NI'
  - 'unknown', None, empty → 'UNKNOWN'
  - Unmapped values → returned as-is (trimmed)

**Prompts**: Uses templates from [app/jurisdictions/uk_config.py](app/jurisdictions/uk_config.py) (lines 270-272)

---

### 6. [app/services/risk_analyzer.py](app/services/risk_analyzer.py) - Risk Assessment

**Purpose**: Detects risky, unfair, or unusual clauses across 10 risk categories.

**Model**: gpt-4o with temperature=0.2 (balanced consistency/nuance), JSON mode enabled, max_tokens=4096

**Risk Categories** (lines 64-75):
- `termination_rights`: Unfavorable termination, unilateral terms, inadequate notice
- `indemnity`: Broad indemnification, uncapped indemnities, one-sided clauses
- `penalty`: Excessive penalties, liquidated damages, punitive terms
- `liability_cap`: Low caps, exclusions of consequential damages, unfair limitations
- `payment_terms`: Unfavorable schedules, late payment penalties, unclear pricing
- `intellectual_property`: IP ownership disputes, broad assignment, unclear licensing
- `confidentiality`: Overly broad obligations, indefinite periods
- `warranty`: Excessive warranties, disclaimers, limited protection
- `force_majeure`: Absence of clause, narrow definition
- `dispute_resolution`: Unfavorable jurisdiction, mandatory arbitration, venue issues

**Risk Levels** (lines 104-107):
- `high`: Significant financial exposure (>50% contract value), business disruption, legal non-compliance
- `medium`: Moderate financial impact (10-50%), operational inconvenience, ambiguous terms
- `low`: Minor concerns (<10%), standard practice with slight unfavorability

**Key Functions**:

1. **`analyze_risks(contract_text: str, contract_id: int, clauses: List[Dict]) -> Tuple[List[Dict], Optional[str]]`** (lines 237-391)
   - **Input Validation**: Minimum 100 characters
   - **Token Optimization**: Truncates contracts >80k chars
   - **Clause Context**: Passes clause numbers and titles (NOT full text) to reduce token usage
   - **Returns**: `(list_of_risks, error_message)` tuple
   - **Risk Data**: Each dict contains contract_id, clause_id (matched), risk_type, risk_level, description, justification, recommendation
   - **Clause Matching**: Attempts to link each risk to specific clause using `_match_clause_reference()`

2. **`_match_clause_reference(clause_ref: str, clauses: List[Dict]) -> Optional[int]`** (lines 203-248)
   - Matches AI-generated clause references to database clause IDs
   - **Three-tier matching strategy**:
     1. **Exact title match** (case-insensitive, trimmed) - highest priority
     2. **Exact number match** - uses regex `\b(\d+(?:\.\d+)*)\b` to extract first clause number, compares exactly (prevents "1" matching "10")
     3. **Substring title match** - fallback for fuzzy matching
   - Returns clause database ID or None

**Token Optimization**:
- `MAX_CONTRACT_TEXT_LENGTH = 80000` (line 61) - ~20k tokens
- Removed clause text previews in recent optimization (keeps only numbers and titles)

---

### 7. [app/services/openai_client.py](app/services/openai_client.py) - Shared OpenAI Client

**Purpose**: Centralized, thread-safe OpenAI client management.

**Key Function**:
- **`get_openai_client() -> OpenAI`** (lines 35-91)
  - **Lazy Initialization**: Client created on first call, not at import time
  - **Caching**: Single shared instance stored in `_client_cache`
  - **Thread Safety**: Uses double-checked locking with `threading.Lock()`
    - First check without lock (fast path for already-initialized)
    - Second check with lock (ensures no race condition during initialization)
  - **Error Handling**: Raises `ValueError` if OPENAI_API_KEY not configured

**Benefits**:
- Prevents import-time failures when env vars missing
- Avoids repeated client instantiation overhead
- Thread-safe for concurrent requests
- Single source of truth for client configuration

---

### 8. [app/database.py](app/database.py) - Database Connection

**Purpose**: SQLAlchemy engine, session factory, and pgvector setup.

**Key Components**:

1. **`engine`** (lines 22-28)
   - Created from `settings.database_url`
   - **Echo mode**: SQL logging in development only
   - **Pool settings**: `pool_pre_ping=True`, `pool_size=5`, `max_overflow=10`

2. **`SessionLocal`** (lines 31-35)
   - Session factory with `autocommit=False`, `autoflush=False`

3. **`Base`** (lines 39-41)
   - SQLAlchemy 2.0 declarative base for all ORM models

4. **`get_db()`** (lines 44-64)
   - FastAPI dependency for database sessions
   - Yields session, ensures cleanup in finally block

5. **`enable_pgvector_extension()`** (lines 67-100)
   - Enables pgvector extension in PostgreSQL
   - **Error Handling**:
     - Detects missing extension → provides installation instructions
     - Detects permission errors → provides superuser fix command

6. **`init_db()`** (lines 103-127)
   - **DEPRECATED**: Delegates to `app.db_init.init_database()` for backwards compatibility

---

### 9. [app/config.py](app/config.py) - Configuration Management

**Purpose**: Pydantic-based settings with environment variable loading.

**`Settings` Class** (lines 21-61):
- **Fields**:
  - `openai_api_key` (required): OpenAI API key
  - `database_url` (required): PostgreSQL connection string
  - `environment` (default: "development"): Application environment
  - `log_level` (default: "INFO"): Logging level
  - `app_name`, `app_version`: Application metadata
- **Config**: Loads from `.env` file, case-insensitive

**`get_settings()`** (lines 64-75):
- Returns cached `Settings` instance (uses `@lru_cache`)
- Prevents repeated environment variable parsing

---

### 10. [app/schemas.py](app/schemas.py) - API Request/Response Models

**Purpose**: Pydantic v2 models for API contracts (separate from database models).

**Request Schemas**:

1. **`ContractUploadRequest`** (lines 16-32)
   - `text` (required, min_length=1): Full contract text
   - `title` (optional): Contract name/title
   - `jurisdiction` (optional): Jurisdiction hint (e.g., "UK", "US")
   - Custom validator ensures text is not empty/whitespace

**Response Schemas**:

1. **`ClauseResponse`** (lines 37-49) - Segmented clause
2. **`EntityResponse`** (lines 52-66) - Extracted entity
3. **`ContractSegmentResponse`** (lines 69-87) - Main upload response
4. **`EntitiesListResponse`** (lines 89-99) - Entity retrieval
5. **`JurisdictionAnalysisResponse`** (lines 102-140) - UK law analysis
6. **`RiskAssessmentResponse`** (lines 160-206) - Single risk
7. **`RiskAnalysisResponse`** (lines 209-228) - Full risk analysis

**All response models use `model_config = ConfigDict(from_attributes=True)` for ORM compatibility.**

---

### 11. [app/jurisdictions/uk_config.py](app/jurisdictions/uk_config.py) - UK Legal Configuration

**Purpose**: UK-specific legal knowledge base and prompt templates.

**Legal Principles** (lines 27-64): formation, interpretation, unfair_terms, termination, remedies, governing_law

**UK Statutes** (lines 71-129): Consumer Rights Act 2015, UCTA 1977, Sale of Goods Act 1979, Supply of Goods and Services Act 1982, Contracts (Rights of Third Parties) Act 1999, Late Payment of Commercial Debts Act 1998

**Common Clauses** (lines 136-174): limitation_of_liability, termination_clauses, force_majeure, entire_agreement, jurisdiction_clauses, indemnity_clauses

**Prompt Templates** (lines 181-263): System prompt with comprehensive UK law analyst instructions

---

### 12. [app/db_init.py](app/db_init.py) - Database Initialization Script

**Purpose**: Sets up PostgreSQL database with pgvector and creates all tables.

**Run as**: `python -m app.db_init` (idempotent)

**Key Functions**:
- `create_tables()` - Creates all 6 tables
- `create_vector_index()` - Creates IVFFlat index on clauses.embedding
- `init_database()` - Main initialization orchestration

---

## Development Guidelines

### Running the Application

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Run development server
python3 -m uvicorn app.main:app --reload
```

API: http://localhost:8000
Docs: http://localhost:8000/docs

### Environment Configuration

Required variables in `.env`:
```
OPENAI_API_KEY=sk-...           # Required for AI features
DATABASE_URL=postgresql://...   # PostgreSQL connection string
ENVIRONMENT=development          # development/staging/production
LOG_LEVEL=INFO                  # DEBUG/INFO/WARNING/ERROR/CRITICAL
```

### Database Commands

```bash
# Initialize database (run once)
python -m app.db_init

# Verify setup
psql -d legal_analyst -c '\dt'
psql -d legal_analyst -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

### Testing the API

```bash
# Upload contract
curl -X POST http://localhost:8000/contracts/segment \
  -H "Content-Type: application/json" \
  -d '{"text":"1 Term\nThis agreement lasts 12 months.", "title":"Test", "jurisdiction":"UK"}'

# Get entities
curl http://localhost:8000/contracts/1/entities

# Analyze jurisdiction
curl -X POST http://localhost:8000/contracts/1/analyze-jurisdiction

# Analyze risks
curl -X POST http://localhost:8000/contracts/1/analyze-risks
```

### Code Style & Patterns

**Error Handling**:
- Services return `(result, error_message)` tuples (not exceptions)
- CRUD raises exceptions, endpoints catch and convert to HTTP errors

**Database Operations**:
- Always use CRUD functions (never raw SQLAlchemy in endpoints)
- Use `bulk_create_*` for batch inserts
- Normalize enums to lowercase (entity_type, risk_type, risk_level)

**OpenAI Integration**:
- Always use `get_openai_client()` (never create new client)
- Enable JSON mode: `response_format={"type": "json_object"}`
- Set appropriate temperature (0.1 for extraction, 0.2 for reasoning)
- Validate AI responses before using/storing

**API Responses**:
- Use Pydantic response models with `ConfigDict(from_attributes=True)`
- Return 404 for missing resources, 400 for invalid input, 409 for conflicts, 500 for errors

### Important Implementation Details

**Clause Segmentation**:
- Regex-based, no AI calls
- `HEADING_RX` expects numbered headings with capital letter start
- Documents with no headings return single clause

**Entity Extraction**:
- Minimum 50 characters required
- Confidence defaults to "medium" if missing
- Context truncated to 500 characters

**Jurisdiction Analysis**:
- Minimum 100 characters required
- Contracts >200k chars truncated to 150k
- Results cached in `summaries` table
- Jurisdiction normalized to canonical codes (UK_EW, UK_SC, UK_NI, UNKNOWN)

**Risk Analysis**:
- Minimum 100 characters required
- Contracts >80k chars truncated
- Results cached in `risk_assessments` table
- Clause matching uses 3-tier strategy (exact title → exact number → substring title)
- Risks sorted by severity (high → medium → low)

**Thread Safety**:
- OpenAI client uses double-checked locking
- Database sessions are request-scoped

## Project Structure

```
ai-legal-anayst/
├── app/
│   ├── main.py                      # FastAPI app + endpoints + segmentation
│   ├── models.py                    # 6 SQLAlchemy ORM models
│   ├── schemas.py                   # Pydantic request/response models
│   ├── crud.py                      # Database operations
│   ├── database.py                  # Engine, session factory, pgvector
│   ├── config.py                    # Pydantic settings
│   ├── db_init.py                   # Database initialization
│   ├── services/
│   │   ├── entity_extractor.py     # OpenAI entity extraction
│   │   ├── jurisdiction_analyzer.py # UK law analysis
│   │   ├── risk_analyzer.py        # 10-category risk detection
│   │   └── openai_client.py        # Shared thread-safe client
│   └── jurisdictions/
│       └── uk_config.py             # UK legal principles + prompts
├── migrations/
│   └── 001_normalize_entity_type.sql
├── .env                             # Environment variables (not in git)
├── requirements.txt                 # Python dependencies
├── README.md                        # User-facing documentation
└── CLAUDE.md                        # This file (developer guidance)
```

## Legal Disclaimer

**This analysis is for informational purposes only and does NOT constitute legal advice.**

Risk assessments are based on AI analysis and should be validated by qualified legal professionals.

---

**For detailed user documentation, API examples, and setup instructions, see [README.md](README.md).**
