"""
Configuration management for AI Legal Contract Analyst.

This module uses pydantic-settings to manage environment variables with type validation.

Usage:
    from app.config import get_settings

    # Access configuration values
    settings = get_settings()
    api_key = settings.openai_api_key
    db_url = settings.database_url
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the project root directory (parent of app/)
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI Configuration
    openai_api_key: str = Field(
        ...,
        description="OpenAI API key for GPT-4o access"
    )

    # Database Configuration
    database_url: str = Field(
        ...,
        description="PostgreSQL connection string with pgvector support"
    )

    # Application Configuration
    environment: str = Field(
        default="development",
        description="Application environment (development/staging/production)"
    )

    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL)"
    )

    app_name: str = Field(
        default="AI Legal Contract Analyst",
        description="Application name for FastAPI"
    )

    app_version: str = Field(
        default="0.1.0",
        description="Application version"
    )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields in .env
    )


@lru_cache
def get_settings() -> Settings:
    """
    Get cached Settings instance.

    Uses lru_cache to ensure Settings is instantiated only once,
    preventing import-time failures and improving performance.

    Returns:
        Settings: Cached application settings instance
    """
    return Settings()
