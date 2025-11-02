"""
UK Contract Law Configuration Module

This module contains UK-specific legal configuration for contract analysis,
including legal principles, statutes, prompt templates, and reference information.

The legal information provided is based on English and Welsh law. Please note:
- Scotland and Northern Ireland have different legal systems and may differ
- This information is for analysis purposes and does NOT constitute legal advice
- Always consult qualified legal professionals for actual legal guidance

Key Components:
- UK_LEGAL_PRINCIPLES: Core principles of UK contract law
- UK_KEY_STATUTES: Relevant UK statutes with descriptions
- UK_COMMON_CLAUSES: Common clauses and their UK law treatment
- Prompt templates for OpenAI GPT-4o legal analysis
- Helper functions for accessing configuration data
"""

from typing import Dict, List, Any


# ============================================================================
# UK Legal Principles
# ============================================================================

UK_LEGAL_PRINCIPLES: Dict[str, str] = {
    "formation": (
        "A valid contract under UK law requires: (1) offer - a clear proposal with definite terms, "
        "(2) acceptance - unequivocal agreement to those terms, (3) consideration - something of value "
        "exchanged by both parties, and (4) intention to create legal relations - parties must intend "
        "the agreement to be legally binding. Commercial agreements are presumed to have this intention."
    ),
    "interpretation": (
        "UK courts interpret contracts using the literal rule (giving words their ordinary meaning), "
        "the contra proferentem rule (ambiguous terms construed against the party who drafted them), "
        "and the business efficacy test (implying terms necessary to give business sense to the contract). "
        "Courts aim to ascertain the parties' objective intentions from the language used."
    ),
    "unfair_terms": (
        "The Consumer Rights Act 2015 protects consumers from unfair contract terms by requiring terms "
        "to be fair and transparent. The Unfair Contract Terms Act 1977 (UCTA) restricts exemption clauses, "
        "particularly those excluding liability for negligence, and subjects limitation clauses to a "
        "reasonableness test in business-to-business contracts."
    ),
    "termination": (
        "Contracts may be terminated by: performance, agreement, breach (material breach allows innocent "
        "party to terminate), or frustration (unforeseen event makes performance impossible or radically "
        "different). Notice periods must be reasonable unless specified. Termination clauses must be clear "
        "about triggers, notice requirements, and consequences."
    ),
    "remedies": (
        "Primary remedy for breach is damages (compensatory, aimed at putting innocent party in position "
        "as if contract performed). Specific performance (court order to perform) is discretionary and "
        "rare, typically for unique goods or land. Injunctions may prevent breach. Liquidated damages "
        "clauses are enforceable if genuine pre-estimate; penalty clauses are void."
    ),
    "governing_law": (
        "Parties may choose governing law (freedom of choice principle). For EU-related contracts, "
        "Rome I Regulation governs choice of law. In absence of choice, contract is governed by law "
        "of country most closely connected. Jurisdiction clauses specifying UK courts are generally "
        "enforceable if exclusive or non-exclusive jurisdiction is clearly stated."
    ),
}


# ============================================================================
# UK Key Statutes
# ============================================================================

UK_KEY_STATUTES: List[Dict[str, Any]] = [
    {
        "name": "Consumer Rights Act",
        "year": 2015,
        "key_provisions": (
            "Protects consumers in contracts with traders. Goods must be of satisfactory quality, "
            "fit for purpose, and as described. Unfair terms are not binding. Consumers have rights "
            "to repair, replacement, price reduction, or refund for faulty goods. Transparency "
            "requirements for contract terms."
        )
    },
    {
        "name": "Unfair Contract Terms Act",
        "year": 1977,
        "key_provisions": (
            "Restricts exemption clauses. Cannot exclude liability for death/personal injury from "
            "negligence. Other exemption/limitation clauses must satisfy reasonableness test. "
            "Applies to business-to-business and business-to-consumer contracts. Protects against "
            "unfair standard terms."
        )
    },
    {
        "name": "Sale of Goods Act",
        "year": 1979,
        "key_provisions": (
            "Implies terms into sale of goods contracts: goods must match description, be of "
            "satisfactory quality, and be fit for particular purpose. Governs transfer of ownership "
            "and risk. Defines seller's and buyer's remedies for breach."
        )
    },
    {
        "name": "Supply of Goods and Services Act",
        "year": 1982,
        "key_provisions": (
            "Extends Sale of Goods Act protections to hire, exchange, and service contracts. "
            "Services must be carried out with reasonable care and skill, within reasonable time, "
            "and at reasonable price (if not agreed). Goods supplied must be of satisfactory quality."
        )
    },
    {
        "name": "Contracts (Rights of Third Parties) Act",
        "year": 1999,
        "key_provisions": (
            "Allows third parties to enforce contract terms if contract expressly provides or term "
            "purports to confer benefit on them (unless parties intended otherwise). Third party "
            "must be identified by name, class, or description. Parties can exclude third-party rights."
        )
    },
    {
        "name": "Late Payment of Commercial Debts (Interest) Act",
        "year": 1998,
        "key_provisions": (
            "Gives businesses statutory right to claim interest on late payments in commercial "
            "transactions. Interest accrues automatically at 8% above Bank of England base rate. "
            "Also allows recovery of debt recovery costs. Contracting out is possible but replacement "
            "terms must provide substantial remedy."
        )
    },
]


# ============================================================================
# UK Common Clauses
# ============================================================================

UK_COMMON_CLAUSES: Dict[str, str] = {
    "limitation_of_liability": (
        "Limitation clauses are enforceable if reasonable under UCTA 1977 (business-to-business) "
        "or fair under Consumer Rights Act 2015 (business-to-consumer). Cannot exclude liability "
        "for death/personal injury from negligence. Courts consider: equality of bargaining power, "
        "whether party received inducement to accept term, whether party knew/ought to know of term, "
        "and whether it was reasonable to expect compliance."
    ),
    "termination_clauses": (
        "Must clearly specify: termination triggers (e.g., material breach, convenience), notice "
        "period requirements, and consequences (e.g., payment obligations, return of property). "
        "Automatic termination clauses are enforceable if clearly drafted. Reasonable notice must "
        "be given unless contract specifies otherwise. Consider whether termination is with or without cause."
    ),
    "force_majeure": (
        "Force majeure is NOT implied in English law - must be expressly included. Clause should: "
        "define triggering events (e.g., acts of God, war, pandemic, government action), specify "
        "notice requirements, state consequences (suspension vs termination), and address mitigation "
        "obligations. COVID-19 litigation highlighted importance of specific drafting."
    ),
    "entire_agreement": (
        "Entire agreement clauses confirm contract contains whole agreement and supersedes prior "
        "negotiations. Generally enforceable but cannot exclude liability for fraudulent misrepresentation. "
        "Courts strictly construe such clauses. Often combined with 'non-reliance' clause confirming "
        "no reliance on pre-contract statements."
    ),
    "jurisdiction_clauses": (
        "Clauses selecting UK courts are generally enforceable. Must specify whether jurisdiction "
        "is 'exclusive' (only UK courts) or 'non-exclusive' (UK courts plus others). For EU-related "
        "disputes, Brussels Regulation/Lugano Convention may apply. Consider whether English law "
        "is also chosen as governing law."
    ),
    "indemnity_clauses": (
        "Indemnity clauses require one party to compensate other for specified losses. Broader than "
        "damages (can cover losses not directly caused by breach). Must be clearly drafted. Subject "
        "to UCTA 1977 reasonableness test in business-to-business contracts. Cannot exclude liability "
        "for own fraud or deliberate breach."
    ),
}


# ============================================================================
# OpenAI Prompt Templates
# ============================================================================

SYSTEM_PROMPT_TEMPLATE: str = """You are an expert UK contract law analyst with deep knowledge of English and Welsh contract law, statutes, and case law. Your task is to analyze contracts through a UK legal lens and provide comprehensive jurisdiction analysis.

**Your Analysis Should:**

1. **Jurisdiction Detection**: Identify whether the contract is governed by UK law (England and Wales). Look for:
   - Explicit governing law clauses
   - References to UK statutes or legal concepts
   - Jurisdiction clauses selecting UK courts
   - Language and terminology suggesting UK drafting
   - Confidence level: high (explicit), medium (strong indicators), low (uncertain)

2. **Statute Identification**: Identify which UK statutes apply, including:
   - Consumer Rights Act 2015 (consumer contracts)
   - Unfair Contract Terms Act 1977 (exemption clauses, reasonableness)
   - Sale of Goods Act 1979 (sale of goods)
   - Supply of Goods and Services Act 1982 (services, hire)
   - Contracts (Rights of Third Parties) Act 1999 (third-party rights)
   - Late Payment of Commercial Debts (Interest) Act 1998 (late payment)
   - Other relevant statutes

3. **Legal Principles**: Map relevant UK legal principles, including:
   - Contract formation (offer, acceptance, consideration, intention)
   - Interpretation rules (literal rule, contra proferentem, business efficacy)
   - Unfair terms protections (UCTA, CRA)
   - Termination and breach rules
   - Available remedies (damages, specific performance, injunctions)
   - Governing law and jurisdiction principles

4. **Enforceability Assessment**: Provide overall assessment of enforceability under UK law:
   - Identify potentially problematic clauses (e.g., unfair exclusions, penalties)
   - Note compliance with statutory requirements
   - Highlight areas requiring legal review
   - Assess reasonableness of key terms

5. **Clause-Specific Interpretations**: For important clauses, provide UK law analysis:
   - How clause would likely be interpreted by UK courts
   - Relevant statutes or case law principles
   - Potential enforceability issues
   - Reference specific clause numbers/headings

6. **Recommendations**: Suggest improvements for UK law compliance:
   - Missing clauses that should be added (e.g., force majeure)
   - Ambiguous terms that should be clarified
   - Potentially unenforceable provisions that should be revised
   - Best practices under UK law

**Output Format:**

Respond with a JSON object containing:
- `jurisdiction_confirmed` (string): Detected jurisdiction (e.g., "England and Wales", "UK", "Scotland", "Northern Ireland", or "Unknown")
- `confidence` (string): Detection confidence - "high", "medium", or "low"
- `applicable_statutes` (array of strings): List of relevant UK statutes
- `legal_principles` (array of strings): Key UK legal principles that apply
- `enforceability_assessment` (string): Comprehensive enforceability assessment (2-4 paragraphs)
- `key_considerations` (array of strings): Important UK-specific legal points
- `clause_interpretations` (array of objects): Clause-specific analysis with fields:
  - `clause` (string): Clause reference (e.g., "Clause 5 - Limitation of Liability")
  - `interpretation` (string): UK law interpretation and analysis
- `recommendations` (array of strings): Suggestions for UK law compliance

**Important Guidelines:**
- Cite specific UK legal authorities where applicable (statutes, well-known principles)
- Be precise about confidence levels - only use "high" for explicit UK law selection
- Consider both statute law and common law principles
- Note differences between B2B and B2C contracts where relevant
- Distinguish England/Wales from Scotland/Northern Ireland where jurisdiction differs
- If contract is clearly NOT governed by UK law, state this clearly with low confidence

**Legal Principles Reference:**

Formation: """ + UK_LEGAL_PRINCIPLES["formation"] + """

Interpretation: """ + UK_LEGAL_PRINCIPLES["interpretation"] + """

Unfair Terms: """ + UK_LEGAL_PRINCIPLES["unfair_terms"] + """

Termination: """ + UK_LEGAL_PRINCIPLES["termination"] + """

Remedies: """ + UK_LEGAL_PRINCIPLES["remedies"] + """

Governing Law: """ + UK_LEGAL_PRINCIPLES["governing_law"] + """

Provide accurate, practical analysis grounded in UK contract law. Your analysis is for informational purposes only and does not constitute legal advice."""


USER_PROMPT_TEMPLATE: str = """Analyze the following contract under UK contract law:

{contract_text}

Provide a comprehensive jurisdiction analysis following the specified JSON format."""


# ============================================================================
# Helper Functions
# ============================================================================

def get_system_prompt() -> str:
    """
    Returns the system prompt template for OpenAI GPT-4o.

    This prompt instructs the AI to act as a UK contract law expert and
    provides detailed guidance on the analysis structure and output format.

    Returns:
        str: Complete system prompt for jurisdiction analysis
    """
    return SYSTEM_PROMPT_TEMPLATE


def get_user_prompt(contract_text: str) -> str:
    """
    Returns formatted user prompt with contract text.

    Args:
        contract_text: The contract text to analyze

    Returns:
        str: Formatted user prompt ready for OpenAI API
    """
    return USER_PROMPT_TEMPLATE.format(contract_text=contract_text)


def get_legal_principles() -> Dict[str, str]:
    """
    Returns UK legal principles dictionary.

    Returns:
        dict: UK legal principles organized by category
    """
    return UK_LEGAL_PRINCIPLES


def get_key_statutes() -> List[Dict[str, Any]]:
    """
    Returns list of key UK statutes with descriptions.

    Returns:
        list: UK statutes with name, year, and key provisions
    """
    return UK_KEY_STATUTES


def get_common_clauses() -> Dict[str, str]:
    """
    Returns common contract clauses and their UK law treatment.

    Returns:
        dict: Common clauses with UK-specific legal considerations
    """
    return UK_COMMON_CLAUSES
