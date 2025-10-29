# AI Legal Contract Analyst

An AI-powered system for reading, interpreting, and contextualizing legal contracts with jurisdiction-aware analysis, focused on UK contract law.

## Features

- **Contract Parsing**: Automated segmentation of contracts into individual clauses with database persistence
- **AI-Powered Entity Recognition**: Intelligent extraction of parties, dates, financial terms, governing laws, and obligations using OpenAI GPT-4o
- **Risk Analysis**: AI-powered assessment of contractual risks and obligations *(planned)*
- **Plain-Language Summaries**: Convert complex legal language into accessible explanations *(planned)*
- **Interactive Q&A**: Ask questions about contract terms and receive contextualized answers *(planned)*

## Prerequisites

- Python 3.11 or higher
- PostgreSQL 14+ with pgvector extension
- OpenAI API account (**TODO**: See Configuration section below)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ai-legal-anayst
```

### 2. Create and Activate Virtual Environment

**Linux/macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install PostgreSQL and pgvector

**Ubuntu/Debian:**
```bash
sudo apt-get install postgresql postgresql-contrib
# Install pgvector extension (follow instructions at: https://github.com/pgvector/pgvector)
```

**macOS (using Homebrew):**
```bash
brew install postgresql
# Install pgvector extension
```

## Configuration

### **⚠️ TODO: Obtain OpenAI API Key**

> **IMPORTANT**: Before running the application, you must obtain an OpenAI API key:
>
> 1. Visit **https://platform.openai.com/api-keys**
> 2. Create a new API key (or use an existing one)
> 3. Copy the key - it will start with `sk-`
> 4. **Keep this key secret** and never commit it to version control
> 5. Follow the setup steps below to configure it

### Setup Steps

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and configure the following variables:**

   - **`OPENAI_API_KEY`**: ⚠️ **REQUIRED** - Paste your OpenAI API key here (obtained from step above). Entity extraction will not work without this.
   - **`DATABASE_URL`**: Configure your PostgreSQL connection string
     - Format: `postgresql://username:password@localhost:5432/database_name`
     - Example: `postgresql://postgres:mypassword@localhost:5432/legal_analyst`
   - **`ENVIRONMENT`**: Set to `development`, `staging`, or `production` (default: `development`)
   - **`LOG_LEVEL`**: Set logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` (default: `INFO`)

   **Note**: Entity extraction uses the GPT-4o model. Ensure you have sufficient API credits in your OpenAI account.

3. **Verify your `.env` file is in `.gitignore`** (it should be by default) to prevent accidentally committing secrets.

## Database Setup

### 1. Install PostgreSQL

Ensure PostgreSQL 14+ is installed and running on your system.

**macOS (using Homebrew):**
```bash
brew install postgresql@14
brew services start postgresql@14
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql-14 postgresql-contrib-14
sudo systemctl start postgresql
```

**Windows:**
Download and install from [PostgreSQL official website](https://www.postgresql.org/download/windows/)

### 2. Install pgvector Extension

⚠️ **IMPORTANT**: The pgvector extension is required for semantic search functionality.

**macOS (using Homebrew):**
```bash
brew install pgvector
```

**Ubuntu/Debian:**
Follow compilation instructions at [pgvector GitHub](https://github.com/pgvector/pgvector#installation)

**Docker:**
Use pgvector-enabled PostgreSQL image:
```bash
docker run -d --name postgres-pgvector \
  -e POSTGRES_PASSWORD=mypassword \
  -p 5432:5432 \
  ankane/pgvector
```

**Official Documentation**: https://github.com/pgvector/pgvector

### 3. Create Database

Create the PostgreSQL database for the application:

```bash
createdb legal_analyst
```

Or using psql:
```bash
psql -U postgres -c "CREATE DATABASE legal_analyst;"
```

### 4. Initialize Database Schema

Run the initialization script to enable pgvector and create all required tables:

```bash
python -m app.db_init
```

**What this script does:**
- Enables the pgvector extension for vector similarity search
- Creates all required tables:
  - `contracts`: Stores uploaded contract documents
  - `clauses`: Individual segmented clauses with embeddings
  - `entities`: Extracted entities (parties, dates, terms, etc.)
  - `risk_assessments`: Risk analysis results
  - `summaries`: Plain-language summaries
  - `qa_history`: Question-answer interaction history

**Note**: This script is safe to run multiple times (idempotent operation).

### 5. Verify Setup

**Check that tables were created:**
```bash
psql -d legal_analyst -c '\dt'
```

Expected output: List of 6 tables (contracts, clauses, entities, risk_assessments, summaries, qa_history)

**Verify pgvector extension:**
```bash
psql -d legal_analyst -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

### Troubleshooting

**If pgvector extension fails:**
- Ensure pgvector is installed on your PostgreSQL server (not just the Python package)
- Verify your database user has `CREATE EXTENSION` privilege
- To manually enable: `psql -U postgres -d legal_analyst -c 'CREATE EXTENSION vector;'`

**If connection fails:**
- Verify `DATABASE_URL` in `.env` file matches your PostgreSQL configuration
- Test connection: `psql <your-database-url>`
- Ensure PostgreSQL is running: `pg_isready`

**If database does not exist:**
- Create it first: `createdb legal_analyst`

**If permission errors:**
- Ensure your PostgreSQL user has appropriate privileges
- Grant privileges: `psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE legal_analyst TO <your_user>;"`

## Running the Application

⚠️ **Prerequisites**: Ensure the database has been initialized (see Database Setup above) before starting the API.

Start the development server:

```bash
uvicorn app.main:app --reload
```

The application will be available at:
- **API**: http://localhost:8000
- **Interactive Documentation (Swagger UI)**: http://localhost:8000/docs - Interactive testing of all endpoints

## API Endpoints

### Health Check

**`GET /health`** - Verify service is running

Returns status and version information.

### Contract Processing

**`POST /contracts/segment`** - Upload and process a contract

**Request Body:**

```json
{
  "text": "<contract text>",
  "title": "<optional contract title>",
  "jurisdiction": "<optional jurisdiction hint, e.g., 'UK', 'US'>"
}
```

**Response:**

```json
{
  "contract_id": 1,
  "status": "completed",
  "clauses": [
    {
      "clause_id": "uuid-string",
      "number": "1",
      "title": "Term",
      "text": "This agreement lasts 12 months."
    }
  ],
  "entities": [
    {
      "id": 1,
      "entity_type": "date",
      "value": "12 months",
      "context": "This agreement lasts 12 months.",
      "confidence": "high",
      "extracted_at": "2025-10-28T10:00:00Z"
    }
  ],
  "message": "Contract processed successfully. Found 3 clauses and 5 entities."
}
```

**Status Values:**
- `completed` - Both clause segmentation and entity extraction succeeded
- `completed_with_warnings` - Clause segmentation succeeded but entity extraction failed (clauses are still available; check message for details)
- `failed` - Processing failed entirely

**Success Response (HTTP 200):**
```json
{
  "contract_id": 1,
  "status": "completed",
  "clauses": [...],
  "entities": [...],
  "message": "Contract processed successfully. Found 3 clauses and 5 entities."
}
```

**Partial Success Response (HTTP 200):**
```json
{
  "contract_id": 1,
  "status": "completed_with_warnings",
  "clauses": [
    {
      "clause_id": "uuid-string",
      "number": "1",
      "title": "Term",
      "text": "This agreement lasts 12 months."
    }
  ],
  "entities": [],
  "message": "Contract segmented into clauses, but entity extraction failed: Entity extraction failed: APITimeoutError: Request timed out."
}
```

**Error Responses:**

- **409 Conflict** - Duplicate clause ID detected (rare edge case)
  ```json
  {
    "detail": "Duplicate clause ID '123e4567-e89b-12d3-a456-426614174000' already exists for contract 1"
  }
  ```

- **500 Internal Server Error** - Processing failure (database error, unexpected exception)
  ```json
  {
    "detail": "Failed to process contract: <error description>"
  }
  ```

**Upstream Service Errors (OpenAI):**

When entity extraction encounters OpenAI API issues, the endpoint returns `completed_with_warnings` (HTTP 200) with clauses but empty entities:

- **Rate Limit (OpenAI 429)**:
  ```json
  {
    "contract_id": 1,
    "status": "completed_with_warnings",
    "clauses": [...],
    "entities": [],
    "message": "Contract segmented into clauses, but entity extraction failed: Entity extraction failed: RateLimitError: You exceeded your current quota"
  }
  ```

- **OpenAI API Timeout**:
  ```json
  {
    "contract_id": 1,
    "status": "completed_with_warnings",
    "clauses": [...],
    "entities": [],
    "message": "Contract segmented into clauses, but entity extraction failed: Entity extraction failed: APITimeoutError: Request timed out."
  }
  ```

- **OpenAI Service Error (5xx)**:
  ```json
  {
    "contract_id": 1,
    "status": "completed_with_warnings",
    "clauses": [...],
    "entities": [],
    "message": "Contract segmented into clauses, but entity extraction failed: Entity extraction failed: APIError: The server had an error while processing your request"
  }
  ```

**Database Connection Errors:**

If the database is unavailable during initial contract creation, the endpoint returns HTTP 500:
```json
{
  "detail": "Failed to process contract: (psycopg2.OperationalError) could not connect to server"
}
```

**Client Guidance:**

1. **Always check the `status` field** to determine processing outcome:
   - `completed`: Use both clauses and entities
   - `completed_with_warnings`: Use clauses; entities array will be empty; check `message` for reason
   - `failed`: Processing failed entirely

2. **Check array lengths**: Even with status `completed`, arrays may be empty if no clauses/entities were found

3. **Retry Logic**:
   - For OpenAI rate limits (429): Implement exponential backoff (wait 60s, 120s, 240s)
   - For OpenAI timeouts: Retry immediately (timeout may be transient)
   - For 500 errors: Retry with exponential backoff (5s, 10s, 20s)
   - For 409 conflicts: Do not retry (indicates data integrity issue)

4. **Timeouts**: Set client timeout to at least 60 seconds (entity extraction via OpenAI can take 10-30s for large contracts)

**FastAPI Response Models:**

The endpoint uses Pydantic models for validation:
```python
class ContractSegmentResponse(BaseModel):
    contract_id: int
    status: str  # "completed" | "completed_with_warnings" | "failed"
    clauses: List[ClauseResponse]
    entities: List[EntityResponse]
    message: str
```

See `/docs` (Swagger UI) or `/redoc` (ReDoc) for interactive API documentation with live examples.

**What this endpoint does:**
- Persists the contract to the database
- Segments the contract into numbered clauses using regex-based pattern matching (`segment_contract()` function)
- Extracts entities using OpenAI GPT-4o (parties, dates, financial terms, governing laws, obligations)
- Stores all data for future analysis and retrieval

**Architecture Note:** Clause segmentation and entity extraction are intentionally separated. The `segment_contract()` function remains pure for regex-based clause splitting, while AI-powered entity extraction is orchestrated separately in the endpoint, enabling clear separation of concerns between structural parsing and semantic analysis.

**Production-Readiness Considerations:**

1. **OpenAI HTTP Timeouts** (Not yet implemented - TODO):
   - **Connect timeout**: 10 seconds (time to establish connection)
   - **Request timeout**: 60 seconds (total time for request/response)
   - Configure in `app/services/entity_extractor.py` when initializing the OpenAI client:
     ```python
     client = OpenAI(
         api_key=settings.openai_api_key,
         timeout=httpx.Timeout(10.0, read=60.0)  # connect=10s, read=60s
     )
     ```

2. **Retry Policy with Exponential Backoff** (Not yet implemented - TODO):
   - **Max attempts**: 3 (default)
   - **Backoff strategy**: Exponential with jitter (e.g., 2^attempt * random(0.5, 1.5) seconds)
   - **Retryable errors**:
     - OpenAI 429 (rate limit)
     - OpenAI 500/502/503/504 (server errors)
     - Network timeouts (ConnectTimeout, ReadTimeout)
   - **Non-retryable errors**: 400 (bad request), 401 (auth), 413 (payload too large)
   - Implementation: Use `tenacity` library in `app/services/entity_extractor.py`:
     ```python
     from tenacity import retry, stop_after_attempt, wait_exponential_jitter, retry_if_exception_type

     @retry(
         stop=stop_after_attempt(3),
         wait=wait_exponential_jitter(initial=2, max=30, jitter=1.5),
         retry=retry_if_exception_type((RateLimitError, APITimeoutError, InternalServerError))
     )
     def extract_entities(contract_text: str):
         ...
     ```

3. **Idempotency Keys for Non-Idempotent Writes** (Not yet implemented - TODO):
   - **Requirement**: Clients should send `Idempotency-Key` header with unique identifier (e.g., UUID) for each `POST /contracts/segment` request
   - **Server behavior**: Deduplicate requests with the same key within a 24-hour window (store key + response hash in cache/database)
   - **Header format**: `Idempotency-Key: <uuid-v4>`
   - **Implementation location**: Add middleware in `app/main.py` to check/store idempotency keys before processing
   - **Example**:
     ```bash
     curl -X POST http://localhost:8000/contracts/segment \
       -H "Content-Type: application/json" \
       -H "Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000" \
       -d '{"text": "..."}'
     ```
   - If duplicate key is detected, return cached response with HTTP 200 (not 409) to maintain idempotency semantics

**References:**
- [OpenAI Python Client Timeouts](https://github.com/openai/openai-python#timeouts)
- [Tenacity Retry Library](https://tenacity.readthedocs.io/)
- [Idempotency Keys Pattern](https://stripe.com/docs/api/idempotent_requests)

### Entity Retrieval

**`GET /contracts/{id}/entities`** - Retrieve all extracted entities for a contract

**Optional Query Parameter:**
- `entity_type` - Filter by specific type (party/date/financial_term/governing_law/obligation). Case-insensitive.

**Success Response (HTTP 200):**
```json
{
  "contract_id": 1,
  "entities": [
    {
      "id": 1,
      "entity_type": "party",
      "value": "Acme Corporation",
      "context": "This Agreement is entered into between Acme Corporation and Beta Inc.",
      "confidence": "high",
      "extracted_at": "2025-10-28T10:00:00Z"
    }
  ],
  "total_count": 10,
  "entity_types": {
    "party": 2,
    "date": 5,
    "financial_term": 2,
    "obligation": 1
  }
}
```

**Empty Result (HTTP 200):**
If no entities exist for the contract or filter criteria:
```json
{
  "contract_id": 1,
  "entities": [],
  "total_count": 0,
  "entity_types": {}
}
```

**Error Responses:**

- **404 Not Found** - Contract does not exist
  ```json
  {
    "detail": "Contract 999 not found"
  }
  ```

- **500 Internal Server Error** - Database error or unexpected exception
  ```json
  {
    "detail": "Failed to retrieve entities"
  }
  ```

**Client Guidance:**

1. **Always check `total_count`**: A value of 0 means no entities were extracted (possibly due to extraction failure during upload or no entities present in text)

2. **Empty `entities` array is valid**: Contracts may legitimately have no entities, or entity extraction may have failed during upload (check contract's `status` field via the upload response or database)

3. **Case-insensitive filtering**: The `entity_type` parameter accepts any case variation ("Party", "PARTY", "party" all work)

4. **Retry Logic**:
   - For 404 errors: Do not retry (contract doesn't exist)
   - For 500 errors: Retry with exponential backoff (2s, 4s, 8s)

**FastAPI Response Models:**

```python
class EntitiesListResponse(BaseModel):
    contract_id: int
    entities: List[EntityResponse]
    total_count: int
    entity_types: dict  # Type counts, e.g., {"party": 2, "date": 5}
```

## Example Usage

### 1. Start the server
```bash
uvicorn app.main:app --reload
```

### 2. Upload and process a contract
```bash
curl -X POST http://localhost:8000/contracts/segment \
  -H "Content-Type: application/json" \
  -d '{
    "text": "This Agreement is entered into on January 1, 2024 between Acme Corporation (\"Client\") and Beta Services Ltd (\"Provider\").\n\n1. Term\nThis agreement shall commence on January 1, 2024 and continue for 12 months.\n\n2. Payment\nClient agrees to pay Provider $50,000 annually, payable in quarterly installments of $12,500.\n\n3. Termination\nEither party may terminate with 30 days written notice.\n\n4. Governing Law\nThis Agreement shall be governed by the laws of England and Wales.",
    "title": "Service Agreement",
    "jurisdiction": "UK"
  }'
```

### 3. Retrieve extracted entities
```bash
# Get all entities
curl http://localhost:8000/contracts/1/entities

# Get only financial terms
curl http://localhost:8000/contracts/1/entities?entity_type=financial_term
```

## Entity Types

The system extracts five types of entities from contracts:

- **Parties**: Legal entities involved (companies, individuals, organizations)
  - Examples: "Acme Corporation", "John Smith", "ABC Ltd."

- **Dates**: Important dates (effective date, termination date, deadlines, milestones)
  - Examples: "January 1, 2024", "within 30 days", "12 months"

- **Financial Terms**: Monetary amounts, payment terms, pricing, fees, penalties
  - Examples: "$50,000", "quarterly installments", "5% annual interest"

- **Governing Law**: Applicable laws, jurisdictions, dispute resolution venues
  - Examples: "laws of England and Wales", "New York courts"

- **Obligations**: Key duties and responsibilities of each party
  - Examples: "provide monthly reports", "maintain confidentiality", "deliver services"

Each entity includes:
- **Confidence level** (high/medium/low) indicating extraction certainty
- **Context** - surrounding text showing where the entity appears in the contract

## Project Structure

```
ai-legal-anayst/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI application with endpoints
│   │                     # - POST /contracts/segment: Process contracts with AI
│   │                     # - GET /contracts/{id}/entities: Retrieve entities
│   │                     # - segment_contract() function for clause extraction
│   ├── schemas.py        # Pydantic models for API requests/responses
│   ├── config.py         # Configuration management with pydantic-settings
│   ├── database.py       # Database connection and session management
│   ├── models.py         # SQLAlchemy ORM models (6 tables)
│   ├── crud.py           # CRUD operations for database entities
│   ├── db_init.py        # Database initialization script
│   └── services/         # Business logic and external service integrations
│       ├── __init__.py
│       └── entity_extractor.py  # OpenAI-powered entity extraction service
├── .env                  # Environment variables (DO NOT COMMIT)
├── .env.example          # Environment template
├── requirements.txt      # Python dependencies
├── CLAUDE.md            # Development guidance
└── README.md            # This file
```

## Technology Stack

- **FastAPI**: Modern Python web framework for building APIs
- **PostgreSQL**: Relational database with advanced features
- **pgvector**: Vector similarity search for semantic analysis
- **SQLAlchemy**: SQL toolkit and ORM for database operations
- **OpenAI GPT-4o**: Large language model for AI-powered entity extraction and contract analysis
- **Pydantic**: Data validation and settings management
- **Structured JSON Output**: GPT-4o's JSON mode for reliable entity extraction

## Development Status

### ✅ Completed Features (Phase 1)
- **Contract Parsing & Segmentation**
  - Regex-based clause segmentation with numbered heading detection
  - Database persistence for contracts and clauses
  - REST API endpoint for contract processing

- **AI-Powered Entity Extraction**
  - OpenAI GPT-4o integration with structured JSON output
  - Five entity types: parties, dates, financial terms, governing laws, obligations
  - Confidence scoring (high/medium/low) for each entity
  - Contextual information extraction
  - Database persistence for extracted entities

- **Database Infrastructure**
  - PostgreSQL with pgvector extension
  - SQLAlchemy ORM models for 6 tables
  - CRUD operations for contracts, clauses, and entities
  - Automated database initialization script

- **API Endpoints**
  - `POST /contracts/segment` - Process contracts with AI entity extraction
  - `GET /contracts/{id}/entities` - Retrieve entities with type filtering
  - `GET /health` - Service health check

### 📋 Planned Features (Future Phases)
- **Phase 2**: Jurisdiction analysis and detection
- **Phase 3**: Risk assessment and obligation tracking
- **Phase 4**: Plain-language contract summaries
- **Phase 5**: Semantic search with vector embeddings
- **Phase 6**: Interactive Q&A system for contract queries
- Comparative analysis across multiple contracts
- Export and reporting functionality

## Troubleshooting

### Common Issues

**OpenAI API key not configured:**
- Check that `OPENAI_API_KEY` is set in your `.env` file
- Verify the API key starts with `sk-`
- Test your API key at https://platform.openai.com/api-keys

**Rate limit errors from OpenAI:**
- You've exceeded OpenAI API usage limits
- Check your usage at https://platform.openai.com/usage
- Consider upgrading your OpenAI plan for higher limits

**Empty entities list returned:**
- Check contract text quality - ensure it contains extractable information
- Review application logs for extraction errors
- Verify OpenAI API key has GPT-4o access
- Try with a longer, more detailed contract sample

**Database connection errors:**
- Verify PostgreSQL is running: `pg_isready`
- Check `DATABASE_URL` in `.env` matches your PostgreSQL configuration
- Test connection: `psql <your-database-url>`
- Ensure database was created: `createdb legal_analyst`

**Import errors or missing dependencies:**
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`
- Check Python version: `python --version` (should be 3.11+)

## Security Notes

- **Never commit the `.env` file** - it contains sensitive API keys
- **Keep your OpenAI API key confidential** - treat it like a password
- **Rotate your API keys immediately** if they are exposed or committed accidentally
- The `.env` file is already included in `.gitignore` to prevent accidental commits
- Review OpenAI's best practices for API key security: https://platform.openai.com/docs/guides/safety-best-practices

## License

[License information to be added]

## Contributing

[Contributing guidelines to be added]
