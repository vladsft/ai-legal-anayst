# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI Legal Analyst MVP - a FastAPI application that segments legal contract documents into individual clauses. The application parses contract text and extracts numbered clauses (e.g., "2.1 Termination") along with their content.

## Architecture

The application is a single-file FastAPI service (`app/main.py`) that:

1. **Accepts contract text** via POST endpoint at `/contracts/segment`
2. **Segments the document** using regex-based pattern matching to identify numbered headings
3. **Returns structured clauses** with unique IDs, numbers, titles, and body text

### Key Components

- **`segment_contract(text: str)`** (app/main.py:44-80): Core segmentation logic
  - Uses `HEADING_RX` regex to detect numbered headings like "2.1 Termination"
  - Normalizes bullet points to prevent incorrect splits
  - Returns list of `Clause` objects with UUID identifiers

- **Data Models**:
  - `Clause`: Represents a contract clause with `clause_id`, `number`, `title`, and `text`
  - `UploadRequest`: Simple input model containing raw contract text

- **API Endpoint**: POST `/contracts/segment` accepts JSON with contract text and returns segmented clauses

## Development Commands

### Running the Application

```bash
# The virtual environment uses Python 3.11 (symlinked from the original Windows path)
# Run the development server:
python3 -m uvicorn app.main:app --reload

# Or using the uvicorn script directly:
.venv/bin/uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

### Testing the API

```bash
# Example curl request:
curl -X POST http://localhost:8000/contracts/segment \
  -H "Content-Type: application/json" \
  -d '{"text": "1 Term\nThis agreement lasts 12 months.\n\n2 Termination\nEither party may terminate..."}'
```

## Dependencies

The project uses:
- FastAPI for the web framework
- Pydantic for data validation
- uvicorn as the ASGI server
- python-docx (installed but not yet used in current code)

Virtual environment is located at `.venv/` with Python 3.11.

## Important Implementation Details

### Regex Patterns

- **`HEADING_RX`** (app/main.py:38): Matches numbered headings at start of line with format `\d+(\.\d+)* Title`
  - Captures both the number (e.g., "2.1") and title (e.g., "Termination")
  - Expects title to start with capital letter and be max 100 characters

- **`BULLET_JOIN_RX`** (app/main.py:42): Prevents splitting bullet points (•, -, –) into separate clauses

### Edge Cases Handled

- Documents with no numbered headings are treated as a single clause
- Bullet points are normalized to stay within their parent clause
- Each clause gets a unique UUID identifier
