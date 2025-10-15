# Import FastAPI (web framework) and supporting classes
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import re
from uuid import uuid4

# Initialize the FastAPI application
# - title is optional, but will show up in the Swagger UI
app = FastAPI(title="AI Legal Analyst MVP (tiny)")

# --------------------------
# Data Models (using Pydantic)
# --------------------------

# This represents a single contract clause (one section in the document).
class Clause(BaseModel):
    clause_id: str          # unique identifier for this clause
    number: Optional[str]   # e.g. "2.1" if it's numbered, otherwise None
    title: Optional[str]    # heading/title of the clause, e.g. "Termination"
    text: str               # the full body text of the clause

# Input model for our endpoint:
# - right now, we just send raw text of the contract.
# - in the future, this could be replaced with file uploads.
class UploadRequest(BaseModel):
    text: str

# --------------------------
# Clause Segmentation Logic
# --------------------------

# Regex that detects numbered headings in contracts.
# Example it matches:
#   "2 Term"
#   "2.1 Termination for Convenience"
# Captures: the number ("2.1") and the title ("Termination for Convenience").
HEADING_RX = re.compile(r'(?m)^\s*(\d+(?:\.\d+)*)\s+([A-Z][^\n]{0,100})\s*$')

# Regex to join lines that are bullets (•, -, –) back together
# (to prevent splitting a single bullet point into multiple clauses).
BULLET_JOIN_RX = re.compile(r'\n(?=[•\-–]\s)')

def segment_contract(text: str) -> List[Clause]:
    """
    Splits the raw contract text into clauses based on numbered headings.
    Returns a list of Clause objects.
    """
    # First: normalize bullet lists so they stay inside the same clause
    text = BULLET_JOIN_RX.sub('\n', text)

    # Find all numbered headings using regex
    matches = list(HEADING_RX.finditer(text))

    # If no headings are found, treat the entire document as one big clause
    if not matches:
        return [Clause(clause_id=str(uuid4()), number=None, title=None, text=text.strip())]

    clauses: List[Clause] = []
    for i, m in enumerate(matches):
        # Start of clause is right after the heading we matched
        start = m.end()
        # End of clause is the start of the next heading, or end of document
        end = matches[i+1].start() if i+1 < len(matches) else len(text)

        # Clause number (e.g. "2.1")
        number = m.group(1).strip()
        # Clause title (e.g. "Termination for Convenience")
        title = m.group(2).strip()
        # The body text of the clause (between this heading and the next one)
        body = text[start:end].strip()

        # Create a Clause object and add it to the list
        clauses.append(Clause(
            clause_id=str(uuid4()),  # generate a random unique ID
            number=number,
            title=title,
            text=body
        ))
    return clauses

# --------------------------
# API Endpoint
# --------------------------

@app.get("/health")
def health_check():
    """
    Health check endpoint to verify the service is running.
    Returns status and service information.
    """
    return {
        "status": "healthy",
        "service": "AI Legal Analyst MVP",
        "version": "0.1.0"
    }

@app.post("/contracts/segment", response_model=List[Clause])
def upload_and_segment(req: UploadRequest):
    """
    API endpoint: POST /contracts/segment
    Input: JSON with { "text": "<raw contract>" }
    Output: list of clauses (with IDs, numbers, titles, and text).
    """
    return segment_contract(req.text)

