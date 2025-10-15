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

Create the PostgreSQL database:

```bash
createdb legal_analyst
```

> **Note**: Database schema initialization and migrations will be covered in subsequent development phases.

## Running the Application

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
│   ├── config.py         # Configuration management
│   ├── models.py         # Database models (coming in next phase)
│   ├── database.py       # Database connection setup (coming in next phase)
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

### ✅ Current Features
- Basic clause segmentation using regex pattern matching
- REST API endpoint for contract text processing
- FastAPI application structure

### 🚧 In Progress
- Database integration with PostgreSQL and pgvector
- AI-powered clause analysis using OpenAI GPT-4o
- Entity extraction and relationship mapping

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
