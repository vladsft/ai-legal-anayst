# AI Legal Contract Analyst

An AI-powered system for analyzing legal contracts with automated clause segmentation, entity extraction, UK jurisdiction analysis, comprehensive risk assessment, and plain-language summarization.

## Features

- **Contract Parsing**: Automated segmentation into numbered clauses with database persistence
- **Entity Extraction**: AI-powered extraction of parties, dates, financial terms, governing laws, and obligations
- **UK Jurisdiction Analysis**: Statute identification, enforceability assessment, and legal principle mapping
- **Risk Assessment**: Detection of 10 risk categories (termination rights, indemnities, penalties, liability caps, payment terms, IP, confidentiality, warranties, force majeure, dispute resolution) with severity scoring (low/medium/high) and actionable recommendations
- **Plain-Language Summaries**: AI-powered translation of legal jargon into clear, accessible language using OpenAI GPT-4o-mini. Supports role-specific perspectives (supplier, client, neutral) to highlight relevant information for different stakeholders. Includes key points, parties, dates, financial terms, obligations, rights, termination conditions, and risk overview

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
      "id": 42,
      "contract_id": 1,
      "clause_id": 5,
      "risk_type": "liability_cap",
      "risk_level": "high",
      "description": "The limitation of liability clause caps damages at £1,000, which is significantly below the contract value of £50,000.",
      "justification": "This represents a high risk because the liability cap is only 2% of the contract value, leaving the client severely underprotected in case of breach. Industry standard is typically 100% of contract value or at least 50%. The cap applies to all damages including direct losses, which is unusually restrictive and could leave the client with substantial unrecoverable losses.",
      "recommendation": "Negotiate to increase the liability cap to at least £25,000 (50% of contract value) or remove the cap for direct damages. Consider adding carve-outs for fraud, willful misconduct, and IP infringement which should remain uncapped.",
      "assessed_at": "2025-11-02T10:15:30Z"
    },
    {
      "id": 43,
      "contract_id": 1,
      "clause_id": 8,
      "risk_type": "termination_rights",
      "risk_level": "medium",
      "description": "The supplier can terminate the contract with only 7 days notice for convenience, while the client requires 30 days notice.",
      "justification": "This asymmetry creates moderate risk as the supplier can exit quickly, potentially disrupting the client's operations. However, 7 days may be sufficient for transition in some contexts. The lack of reciprocal termination rights is concerning and gives the supplier undue leverage.",
      "recommendation": "Negotiate for equal termination notice periods (e.g., 30 days for both parties) or add provisions requiring the supplier to assist with transition during the notice period at no additional cost.",
      "assessed_at": "2025-11-02T10:15:30Z"
    }
  ],
  "total_risks": 8,
  "risk_summary": {"high": 2, "medium": 4, "low": 2},
  "analyzed_at": "2025-11-02T10:15:30Z"
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

### 5. Generate Contract Summary

```bash
# Neutral summary
curl -X POST http://localhost:8000/contracts/1/summarize

# Client perspective
curl -X POST "http://localhost:8000/contracts/1/summarize?role=client"

# Supplier perspective
curl -X POST "http://localhost:8000/contracts/1/summarize?role=supplier"
```

**Response:**
```json
{
  "contract_id": 1,
  "summary_type": "role_specific",
  "role": "client",
  "summary": "This is a service agreement between ABC Corp (client) and XYZ Services (supplier) for software development services. The contract runs for 12 months starting January 1, 2024, with automatic renewal unless either party provides 30 days notice. The client will pay £50,000 in monthly installments of £4,167. The agreement includes standard confidentiality provisions and a 90-day termination clause. Key protections for the client include a liability cap at contract value, IP ownership of deliverables, and the right to terminate for cause with 30 days notice.",
  "key_points": [
    "12-month contract with automatic renewal",
    "£50,000 total value paid monthly",
    "Client owns all IP in deliverables",
    "90-day termination notice required",
    "Liability capped at contract value",
    "Confidentiality obligations for both parties",
    "Supplier warrants professional workmanship"
  ],
  "parties": "ABC Corp (client) and XYZ Services (supplier)",
  "key_dates": [
    "Start date: January 1, 2024",
    "End date: December 31, 2024 (with auto-renewal)",
    "Payment due: 1st of each month"
  ],
  "financial_terms": "Total contract value of £50,000 paid in 12 monthly installments of £4,167. Late payments incur 5% interest per month.",
  "obligations": {
    "supplier": [
      "Deliver software development services",
      "Maintain confidentiality of client information",
      "Provide monthly progress reports"
    ],
    "client": [
      "Pay monthly fees on time",
      "Provide necessary access and information",
      "Review and approve deliverables within 14 days"
    ]
  },
  "rights": {
    "supplier": [
      "Terminate for non-payment after 30 days",
      "Retain IP in pre-existing materials"
    ],
    "client": [
      "Own all IP in deliverables",
      "Terminate for cause with 30 days notice",
      "Receive warranty support for 90 days"
    ]
  },
  "termination": "Either party can terminate with 90 days written notice. Client can terminate for cause (breach, insolvency) with 30 days notice. Supplier can terminate for non-payment after 30 days.",
  "risks": [
    "Automatic renewal may lock client into unwanted extension",
    "Late payment interest rate (5% per month) is relatively high",
    "Limited warranty period (90 days) may be insufficient for complex software"
  ],
  "created_at": "2025-10-28T10:00:00Z"
}
```

**What this endpoint does:**
- Generates plain-language summary using OpenAI GPT-4o-mini
- Translates legal jargon into clear, accessible language
- Provides role-specific perspectives when requested
- Extracts key information: parties, dates, financial terms, obligations, rights
- Highlights termination conditions and potential risks
- Stores summaries in database for future reference
- Returns cached summaries for faster subsequent requests

**Use Cases:**
- **Executives**: Get quick overview without reading full contract
- **Procurement**: Understand supplier obligations and client protections
- **Legal review**: Identify key terms before detailed analysis
- **Contract comparison**: Compare multiple contracts at high level
- **Stakeholder communication**: Share accessible summaries with non-lawyers

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |
| POST | `/contracts/segment` | Upload and process contract (segmentation + entity extraction) |
| GET | `/contracts/{id}/entities` | Retrieve extracted entities (optional `?entity_type=` filter) |
| POST | `/contracts/{id}/analyze-jurisdiction` | Analyze contract through UK contract law lens |
| POST | `/contracts/{id}/analyze-risks` | Comprehensive risk assessment across 10 categories |
| POST | `/contracts/{id}/summarize?role={role}` | Plain-language summary generation with optional role perspective (supplier/client/neutral) |

**Note:** Jurisdiction analysis, risk assessments, and summaries are cached - subsequent requests return cached results without calling OpenAI API again.

## Configuration

Environment variables in `.env`:

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `OPENAI_API_KEY` | Yes | OpenAI API key for GPT-4o-mini | `sk-...` |
| `DATABASE_URL` | Yes | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/legal_analyst` |
| `ENVIRONMENT` | No | Application environment | `development` (default) |
| `LOG_LEVEL` | No | Logging level | `INFO` (default) |

## Technology Stack

- **FastAPI** - Modern Python web framework
- **PostgreSQL + pgvector** - Database with vector similarity search
- **OpenAI GPT-4o-mini** - AI model for entity extraction, jurisdiction analysis, risk assessment, and plain-language summarization
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

### ✅ Phase 4: Plain-Language Summaries
- OpenAI GPT-4o-mini powered summarization (cost-optimized)
- Contract-level summary generation
- Role-specific perspectives: supplier, client, neutral
- Key information extraction: parties, dates, financial terms, obligations, rights
- Termination conditions and risk overview
- Database persistence of summaries
- Caching to prevent redundant API calls
- Accessible language for non-lawyers

### 📋 Planned: Future Phases
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
- Verify OpenAI API key has GPT-4o-mini access
- Review application logs for extraction errors
- Ensure contract is longer than 50 characters

**Risk analysis returns no risks:**
- This may be legitimate for well-balanced contracts
- Check logs to verify analysis completed successfully
- Ensure contract has substantive clauses (>100 characters)

**Summarization fails or returns errors:**
- Verify OpenAI API key has GPT-4o-mini access
- Check application logs for detailed error messages
- Ensure contract text is substantial enough for summarization (> 100 characters)
- Verify role parameter is valid (supplier/client/neutral) if provided
- Check OpenAI API usage limits and quotas

**Invalid role parameter error:**
- Ensure role is one of: supplier, client, neutral (case-insensitive)
- Omit role parameter for neutral/balanced summary
- Check for typos in role parameter

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

### Plain-Language Summarization Disclaimer

The plain-language summarization feature:
- **Simplifies complex legal language** but may not capture all nuances
- **Highlights key information** but is not a substitute for reading the full contract
- **Provides role-specific perspectives** but should not be the sole basis for decisions
- **Uses AI analysis** which may miss important details or context
- **Should be validated** by qualified legal professionals before relying on summaries

Summaries are generated by AI and should be used as a starting point for understanding contracts, not as definitive legal interpretations.

### Data Privacy

- **Contract data is processed by OpenAI** - By using this tool, you acknowledge contract text is sent to OpenAI's API
- **Do not upload confidential contracts** without proper authorization
- **Review OpenAI's data usage policies** before processing sensitive contracts
- **Consider data residency requirements** if handling GDPR-regulated contracts

**Always consult qualified legal professionals for actual legal guidance on contract matters.**

## Developer Documentation

For architecture details, module documentation, and development guidelines, see [CLAUDE.md](CLAUDE.md).
