# AI Legal Contract Analyst

An AI-powered system for analyzing legal contracts with automated clause segmentation, entity extraction, UK jurisdiction analysis, and comprehensive risk assessment.

## Features

- **Contract Parsing**: Automated segmentation into numbered clauses with database persistence
- **Entity Extraction**: AI-powered extraction of parties, dates, financial terms, governing laws, and obligations
- **UK Jurisdiction Analysis**: Statute identification, enforceability assessment, and legal principle mapping
- **Risk Assessment**: Detection of 10 risk categories (termination rights, indemnities, penalties, liability caps, payment terms, IP, confidentiality, warranties, force majeure, dispute resolution) with severity scoring (low/medium/high) and actionable recommendations

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ with [pgvector extension](https://github.com/pgvector/pgvector)
- OpenAI API key ([get one here](https://platform.openai.com/api-keys))

### Installation

1. **Clone and setup**
```bash
git clone <repository-url>
cd ai-legal-anayst
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your settings:
# - OPENAI_API_KEY (required)
# - DATABASE_URL (required)
```

3. **Install PostgreSQL and pgvector**
```bash
# macOS
brew install postgresql pgvector

# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib
# See https://github.com/pgvector/pgvector#installation for pgvector

# Docker
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=mypassword \
  -p 5432:5432 \
  ankane/pgvector
```

4. **Initialize database**
```bash
createdb legal_analyst
python -m app.db_init
```

5. **Start the server**
```bash
uvicorn app.main:app --reload
```

API: http://localhost:8000
Interactive Docs: http://localhost:8000/docs

## Usage

### 1. Upload and Process Contract

```bash
curl -X POST http://localhost:8000/contracts/segment \
  -H "Content-Type: application/json" \
  -d '{
    "text": "1 Term\nThis agreement lasts 12 months.\n\n2 Payment\nClient pays £50,000 annually.",
    "title": "Service Agreement",
    "jurisdiction": "UK"
  }'
```

**Response:**
```json
{
  "contract_id": 1,
  "status": "completed",
  "clauses": [
    {"clause_id": "uuid", "number": "1", "title": "Term", "text": "This agreement lasts 12 months."}
  ],
  "entities": [
    {"entity_type": "date", "value": "12 months", "confidence": "high"}
  ],
  "message": "Contract processed successfully. Found 2 clauses and 3 entities."
}
```

**Status Values:**
- `completed` - All processing succeeded
- `completed_with_warnings` - Segmentation succeeded but entity extraction failed (clauses still available)
- `failed` - Processing failed entirely

### 2. Retrieve Entities

```bash
# All entities
curl http://localhost:8000/contracts/1/entities

# Filter by type
curl http://localhost:8000/contracts/1/entities?entity_type=financial_term
```

**Entity Types:**
- `party` - Companies, individuals, organizations
- `date` - Effective dates, deadlines, milestones
- `financial_term` - Monetary amounts, payment terms, fees
- `governing_law` - Jurisdictions, applicable laws
- `obligation` - Duties and responsibilities

### 3. Analyze Jurisdiction (UK Law)

```bash
curl -X POST http://localhost:8000/contracts/1/analyze-jurisdiction
```

**Response:**
```json
{
  "jurisdiction_confirmed": "England and Wales",
  "confidence": "high",
  "applicable_statutes": ["Consumer Rights Act 2015", "Unfair Contract Terms Act 1977"],
  "legal_principles": ["Freedom of contract", "Contra proferentem rule"],
  "enforceability_assessment": "The contract appears generally enforceable...",
  "key_considerations": ["Limitation clause may require reasonableness test"],
  "clause_interpretations": [
    {"clause": "Clause 5 - Liability", "interpretation": "Under UCTA 1977..."}
  ],
  "recommendations": ["Consider adding force majeure clause"],
  "analyzed_at": "2025-11-02T10:00:00Z"
}
```

**What it analyzes:**
- Jurisdiction detection with confidence level (high/medium/low)
- Applicable UK statutes (Consumer Rights Act, UCTA, etc.)
- Relevant legal principles (formation, interpretation, unfair terms)
- Overall enforceability under UK law
- Clause-specific interpretations
- Recommendations for UK law compliance

### 4. Analyze Risks

```bash
curl -X POST http://localhost:8000/contracts/1/analyze-risks
```

**Response:**
```json
{
  "contract_id": 1,
  "risks": [
    {
      "risk_type": "liability_cap",
      "risk_level": "high",
      "description": "Liability cap of £1,000 is only 2% of £50,000 contract value",
      "justification": "This creates significant financial exposure as cap is drastically below contract value...",
      "recommendation": "Negotiate to increase cap to at least 50% of contract value",
      "clause_id": 5
    }
  ],
  "total_risks": 8,
  "risk_summary": {"high": 2, "medium": 4, "low": 2},
  "analyzed_at": "2025-11-02T10:00:00Z"
}
```

**Risk Categories:**
- `termination_rights` - Unfavorable termination clauses, unilateral termination, inadequate notice
- `indemnity` - Broad indemnification, uncapped indemnities, one-sided clauses
- `penalty` - Excessive penalties, liquidated damages, punitive terms
- `liability_cap` - Low caps, exclusions of consequential damages
- `payment_terms` - Unfavorable payment schedules, late payment penalties
- `intellectual_property` - IP ownership disputes, broad assignment
- `confidentiality` - Overly broad obligations, indefinite periods
- `warranty` - Excessive warranties, warranty disclaimers
- `force_majeure` - Absence of clause, narrow definition
- `dispute_resolution` - Unfavorable jurisdiction, mandatory arbitration

**Risk Levels:**
- `high` - Significant financial exposure (>50% contract value), business disruption, legal non-compliance
- `medium` - Moderate financial impact (10-50%), operational inconvenience, ambiguous terms
- `low` - Minor concerns (<10%), standard industry practice with slight unfavorability

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| POST | `/contracts/segment` | Upload and process contract (segmentation + entity extraction) |
| GET | `/contracts/{id}/entities` | Retrieve extracted entities (optional `?entity_type=` filter) |
| POST | `/contracts/{id}/analyze-jurisdiction` | Analyze contract through UK contract law lens |
| POST | `/contracts/{id}/analyze-risks` | Comprehensive risk assessment across 10 categories |

**Note:** Jurisdiction and risk analyses are cached - subsequent requests return cached results without calling OpenAI API again.

## Configuration

Environment variables in `.env`:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4o | `sk-...` |
| `DATABASE_URL` | Yes | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/legal_analyst` |
| `ENVIRONMENT` | No | Application environment | `development` (default) |
| `LOG_LEVEL` | No | Logging level | `INFO` (default) |

## Technology Stack

- **FastAPI** - Modern Python web framework
- **PostgreSQL + pgvector** - Database with vector similarity search
- **OpenAI GPT-4o** - AI model for entity extraction, jurisdiction analysis, and risk assessment
- **SQLAlchemy 2.0** - ORM with type safety
- **Pydantic v2** - Data validation

## Development Status

### ✅ Phase 1: Contract Parsing & Entity Extraction
- Regex-based clause segmentation
- AI-powered entity extraction (5 entity types)
- Database persistence
- REST API endpoints

### ✅ Phase 2: Jurisdiction Analysis
- UK contract law analysis
- Statute identification (Consumer Rights Act, UCTA, etc.)
- Enforceability assessment
- Clause-specific interpretations
- Analysis result caching

### ✅ Phase 3: Risk Assessment
- 10 risk categories detection
- Risk severity scoring (low/medium/high)
- Clause-specific risk linking
- Actionable recommendations
- Risk analysis caching

### 📋 Planned: Future Phases
- **Phase 4:** Plain-language summaries
- **Phase 5:** Semantic search with embeddings
- **Phase 6:** Interactive Q&A system

## Troubleshooting

**OpenAI API key not configured:**
- Ensure `OPENAI_API_KEY` is set in `.env` file
- Verify key starts with `sk-`
- Check API credits at https://platform.openai.com/usage

**Database connection errors:**
- Verify PostgreSQL is running: `pg_isready`
- Check `DATABASE_URL` in `.env` matches your setup
- Ensure database exists: `createdb legal_analyst`
- Test connection: `psql <your-database-url>`

**pgvector extension errors:**
- Install pgvector: `brew install pgvector` (macOS) or see https://github.com/pgvector/pgvector
- Enable extension manually: `psql -U postgres -d legal_analyst -c 'CREATE EXTENSION vector;'`
- Verify: `psql -d legal_analyst -c "SELECT * FROM pg_extension WHERE extname='vector';"`

**Empty entity results:**
- Check contract text quality (needs substantive content)
- Verify OpenAI API key has GPT-4o access
- Review application logs for extraction errors
- Ensure contract is longer than 50 characters

**Risk analysis returns no risks:**
- This may be legitimate for well-balanced contracts
- Check logs to verify analysis completed successfully
- Ensure contract has substantive clauses (>100 characters)

## Security Notes

- **Never commit `.env`** - contains sensitive API keys (already in `.gitignore`)
- **Keep OpenAI API key confidential** - treat it like a password
- **Rotate keys immediately** if exposed or committed accidentally
- Review [OpenAI security best practices](https://platform.openai.com/docs/guides/safety-best-practices)

## Legal Disclaimer

**IMPORTANT: This software is for informational purposes only.**

- **Does NOT constitute legal advice** - All analysis is AI-generated and informational
- **Not a substitute for professional legal counsel** - Always consult qualified solicitors
- **May not identify all risks** - AI analysis may miss issues or flag standard practices incorrectly
- **Requires human review** - All insights must be validated by legal professionals
- **No warranty** - Provided "as is" without guarantees of accuracy or completeness

### Data Privacy

- **Contract data is processed by OpenAI** - By using this tool, you acknowledge contract text is sent to OpenAI's API
- **Do not upload confidential contracts** without proper authorization
- **Review OpenAI's data usage policies** before processing sensitive contracts
- **Consider data residency requirements** if handling GDPR-regulated contracts

**Always consult qualified legal professionals for actual legal guidance on contract matters.**

## Developer Documentation

For architecture details, module documentation, and development guidelines, see [CLAUDE.md](CLAUDE.md).
