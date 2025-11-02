"""
Jurisdiction-Specific Configuration Package

This package contains jurisdiction-specific configurations for legal contract analysis.
Each jurisdiction has its own configuration module that provides:

- Legal principles and frameworks specific to that jurisdiction
- Prompt templates for AI-powered legal analysis
- Reference information about applicable statutes and regulations
- Common contract clauses and their treatment under local law

Current Jurisdictions:
- uk_config.py: United Kingdom (England and Wales) contract law

Future jurisdictions can be added as separate modules following the same pattern:
- us_config.py: United States contract law
- eu_config.py: European Union contract law
- etc.

Usage:
    from app.jurisdictions.uk_config import UK_CONFIG, get_system_prompt

    system_prompt = get_system_prompt()
    legal_principles = get_legal_principles()
"""
