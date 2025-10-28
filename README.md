# AI Legal Contract Analyst

An AI-powered system for reading, interpreting, and contextualizing legal contracts with jurisdiction-aware analysis, focused on UK contract law.

## Features

- **Contract Parsing**: Automated segmentation of contracts into individual clauses
- **Entity Recognition**: Identification of parties, dates, obligations, and key terms
- **Risk Analysis**: AI-powered assessment of contractual risks and obligations
- **Plain-Language Summaries**: Convert complex legal language into accessible explanations
- **Interactive Q&A**: Ask questions about contract terms and receive contextualized answers

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

   - **`OPENAI_API_KEY`**: Paste your OpenAI API key here (obtained from step above)
   - **`DATABASE_URL`**: Configure your PostgreSQL connection string
     - Format: `postgresql://username:password@localhost:5432/database_name`
     - Example: `postgresql://postgres:mypassword@localhost:5432/legal_analyst`
   - **`ENVIRONMENT`**: Set to `development`, `staging`, or `production` (default: `development`)
   - **`LOG_LEVEL`**: Set logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` (default: `INFO`)

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
- **Interactive Documentation**: http://localhost:8000/docs

### Example API Call

Test the existing clause segmentation endpoint:

```bash
curl -X POST http://localhost:8000/contracts/segment \
  -H "Content-Type: application/json" \
  -d '{
    "text": "1. Term\nThis agreement lasts 12 months.\n\n2. Termination\nEither party may terminate with 30 days notice.\n\n3. Payment\nPayment is due within 14 days."
  }'
```

## Project Structure

```
ai-legal-anayst/
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI application and endpoints
│   │                     # - segment_contract() function (line 44-80)
│   │                     # - POST /contracts/segment endpoint
│   ├── config.py         # Configuration management with pydantic-settings
│   ├── database.py       # Database connection and session management
│   ├── models.py         # SQLAlchemy ORM models (6 tables)
│   ├── crud.py           # CRUD operations for database entities
│   ├── db_init.py        # Database initialization script
│   └── services/         # Business logic services (coming in next phase)
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
- **OpenAI GPT-4o**: Large language model for AI-powered contract analysis
- **Pydantic**: Data validation and settings management

## Development Status

### ✅ Completed Features
- Basic clause segmentation using regex pattern matching
- REST API endpoint for contract text processing
- FastAPI application structure with configuration management
- **Database infrastructure with PostgreSQL and pgvector**
  - SQLAlchemy ORM models for 6 tables (contracts, clauses, entities, risk_assessments, summaries, qa_history)
  - Database connection and session management
  - CRUD operations for contracts and clauses
  - Automated database initialization script

### 🚧 In Progress
- AI-powered clause analysis using OpenAI GPT-4o
- Entity extraction and relationship mapping
- Integration of database persistence into existing endpoints

### 📋 Planned Features
- Risk assessment and obligation tracking
- Interactive Q&A system for contract queries
- Jurisdiction-aware legal reasoning (UK contract law focus)
- Comparative analysis across multiple contracts
- Export and reporting functionality

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
