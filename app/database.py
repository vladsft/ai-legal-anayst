"""
Database connection and session management for AI Legal Analyst.

This module provides SQLAlchemy engine configuration, session factory, and
the declarative base for ORM models. It implements connection pooling and
provides a dependency function for FastAPI endpoints to access the database.

Architecture:
- Engine: Manages database connections with pooling
- SessionLocal: Factory for creating database sessions
- Base: Declarative base for all ORM models
- get_db(): FastAPI dependency that provides sessions with automatic cleanup
"""

from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from app.config import get_settings


# Database engine configuration
settings = get_settings()
engine: Engine = create_engine(
    settings.database_url,
    echo=settings.environment == "development",  # SQL query logging in development
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=5,  # Base connection pool size
    max_overflow=10,  # Additional connections under load
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,  # Require explicit commits
    autoflush=False,  # Control when changes are flushed
    bind=engine,
)


# Declarative base for ORM models using SQLAlchemy 2.0 style
class Base(DeclarativeBase):
    """Base class for all ORM models using SQLAlchemy 2.0 declarative style."""
    pass


def get_db():
    """
    FastAPI dependency that provides a database session.

    Yields a database session and ensures it is closed after use.
    Use this as a dependency in FastAPI endpoints:

    Example:
        @app.get("/endpoint")
        def endpoint(db: Session = Depends(get_db)):
            # Use db session here
            pass

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def enable_pgvector_extension() -> None:
    """
    Enable the pgvector extension in PostgreSQL.

    The pgvector extension provides vector similarity search capabilities
    required for semantic search of clause embeddings.

    Raises:
        Exception: If pgvector is not installed on PostgreSQL server
        Exception: If database user lacks CREATE EXTENSION privilege
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            connection.commit()
    except Exception as e:
        error_msg = str(e).lower()
        if "could not open extension control file" in error_msg or "does not exist" in error_msg:
            raise Exception(
                "pgvector extension is not installed on PostgreSQL server.\n"
                "Installation instructions:\n"
                "  macOS:          brew install pgvector\n"
                "  Ubuntu/Debian:  https://github.com/pgvector/pgvector#installation\n"
                "  Docker:         use ankane/pgvector PostgreSQL image\n"
                "  Documentation:  https://github.com/pgvector/pgvector"
            ) from e
        elif "permission denied" in error_msg or "must be owner" in error_msg:
            raise Exception(
                "Database user lacks CREATE EXTENSION privilege.\n"
                "To fix, run as PostgreSQL superuser:\n"
                "  psql -U postgres -d <database_name> -c 'CREATE EXTENSION vector;'"
            ) from e
        else:
            raise Exception(f"Error enabling pgvector extension: {e}") from e


def init_db():
    """
    Initialize the database by creating all tables.

    DEPRECATED: This function is maintained for backwards compatibility only.
    Use app/db_init.py instead for proper database initialization with
    comprehensive error handling and user feedback.

    This function now delegates to app.db_init.init_database() to avoid
    duplication of initialization logic.

    Recommended usage:
        python -m app.db_init  # Preferred method with better error handling

    Direct usage (backwards compatibility):
        from app.database import init_db
        init_db()  # Delegates to app.db_init.init_database()

    Raises:
        Exception: If pgvector extension cannot be enabled
        Exception: If table creation fails
    """
    # Delegate to the canonical initialization function in app.db_init
    from app.db_init import init_database
    init_database()
