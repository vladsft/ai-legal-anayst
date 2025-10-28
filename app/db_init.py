"""
Database initialization script for AI Legal Analyst.

This script sets up the PostgreSQL database with the pgvector extension
and creates all required tables. It should be run once after configuring
the .env file with DATABASE_URL.

Prerequisites:
- PostgreSQL 14+ must be installed and running
- pgvector extension must be installed on PostgreSQL server
  - macOS: brew install pgvector
  - Ubuntu/Debian: https://github.com/pgvector/pgvector#installation
  - Docker: use ankane/pgvector image
- DATABASE_URL must be configured in .env file
- Database user must have CREATE EXTENSION privilege

Usage:
    python -m app.db_init

This script is safe to run multiple times (idempotent operation).
Future schema changes should use Alembic migrations.
"""

import re
from sqlalchemy import text
from app.database import engine, Base, enable_pgvector_extension
from app.config import get_settings

# Import all models to register them with Base.metadata
from app.models import (  # noqa: F401
    Contract,
    Clause,
    Entity,
    RiskAssessment,
    Summary,
    QAHistory
)


def create_tables() -> None:
    """
    Create all database tables defined in app/models.py.

    This uses SQLAlchemy's metadata to create tables based on ORM models.
    Tables created:
    - contracts: Store uploaded contract documents
    - clauses: Store segmented contract clauses with embeddings
    - entities: Store extracted entities (parties, dates, terms, etc.)
    - risk_assessments: Store risk analysis results
    - summaries: Store plain-language summaries
    - qa_history: Store question-answer interactions

    This operation is idempotent - safe to run multiple times.
    """
    try:
        print("\nCreating database tables...")
        Base.metadata.create_all(bind=engine)
        print("✓ Database tables created successfully")
        print("\nTables created:")
        print("  - contracts")
        print("  - clauses")
        print("  - entities")
        print("  - risk_assessments")
        print("  - summaries")
        print("  - qa_history")
    except Exception as e:
        print(f"\n❌ ERROR creating tables: {e}")
        raise


def create_vector_index() -> None:
    """
    Create optional pgvector index on clauses.embedding for similarity search.

    This creates an IVFFlat index using L2 distance (Euclidean distance) for
    accelerating vector similarity searches. The index is optional and its
    failure will not prevent database initialization.

    Index configuration:
    - Index type: IVFFlat (Inverted File with Flat compression)
    - Distance operator: vector_l2_ops (L2/Euclidean distance)
    - Lists parameter: 100 (number of inverted lists for clustering)

    The lists parameter of 100 is suitable for small to medium datasets.
    For larger datasets (>1M rows), consider increasing this value.
    Rule of thumb: lists = rows / 1000 (capped at a reasonable maximum).

    This operation is idempotent - safe to run multiple times.
    Index creation is skipped if it already exists.

    Note:
        This function will not raise exceptions on failure, only print
        warnings to allow database initialization to proceed.
    """
    try:
        print("\nCreating pgvector index on clauses.embedding...")
        with engine.connect() as connection:
            # Create IVFFlat index with L2 distance operator
            # Using 100 lists as a reasonable default for small-medium datasets
            connection.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_clauses_embedding_ivfflat
                ON clauses
                USING ivfflat (embedding vector_l2_ops)
                WITH (lists = 100)
            """))
            connection.commit()
        print("✓ pgvector index created successfully on clauses.embedding")
        print("  Index: ix_clauses_embedding_ivfflat (IVFFlat, L2 distance, 100 lists)")
    except Exception as e:
        # Non-fatal error - print warning but don't raise
        print(f"\n⚠ WARNING: Could not create pgvector index: {e}")
        print("  Similarity search will still work but may be slower for large datasets.")
        print("  You can manually create the index later with:")
        print("    CREATE INDEX ix_clauses_embedding_ivfflat ON clauses")
        print("    USING ivfflat (embedding vector_l2_ops) WITH (lists = 100);")


def mask_password(database_url: str) -> str:
    """
    Mask password in database URL for safe display.

    Args:
        database_url: Full database URL with credentials

    Returns:
        Database URL with password replaced by asterisks
    """
    return re.sub(r'://([^:]+):([^@]+)@', r'://\1:****@', database_url)


def init_database() -> None:
    """
    Main initialization function that sets up the complete database.

    This orchestrates the full database setup process:
    1. Enables pgvector extension for vector similarity search
    2. Creates all required tables with proper schemas and relationships

    Raises:
        Exception: If database connection fails or setup errors occur
    """
    try:
        settings = get_settings()
        print("=" * 60)
        print("AI Legal Analyst - Database Initialization")
        print("=" * 60)
        print(f"\nDatabase: {mask_password(settings.database_url)}")
        print("\nStarting database initialization...\n")

        # Step 1: Enable pgvector extension
        print("Enabling pgvector extension...")
        try:
            enable_pgvector_extension()
            print("✓ pgvector extension enabled successfully")
        except Exception as e:
            error_msg = str(e)
            if "pgvector extension is not installed" in error_msg:
                print("\n❌ ERROR: pgvector extension is not installed on PostgreSQL server")
                print("\nInstallation instructions:")
                print("  macOS:          brew install pgvector")
                print("  Ubuntu/Debian:  https://github.com/pgvector/pgvector#installation")
                print("  Docker:         use ankane/pgvector PostgreSQL image")
                print("  Documentation:  https://github.com/pgvector/pgvector")
            elif "CREATE EXTENSION privilege" in error_msg:
                print("\n❌ ERROR: Database user lacks CREATE EXTENSION privilege")
                print("\nTo fix, run as PostgreSQL superuser:")
                print("  psql -U postgres -d <database_name> -c 'CREATE EXTENSION vector;'")
            else:
                print(f"\n❌ ERROR enabling pgvector extension: {e}")
            raise

        # Step 2: Create all tables
        create_tables()

        # Step 3: Create optional pgvector index for similarity search
        create_vector_index()

        print("\n" + "=" * 60)
        print("✓ Database initialization completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Verify tables: psql -d <database> -c '\\dt'")
        print("  2. Verify pgvector: psql -d <database> -c \"SELECT * FROM pg_extension WHERE extname='vector';\"")
        print("  3. Verify index: psql -d <database> -c '\\di ix_clauses_embedding_ivfflat'")
        print("  4. Start the API: python3 -m uvicorn app.main:app --reload")
        print("\n")

    except Exception as e:
        # Check for common connection errors
        error_msg = str(e).lower()
        if "could not connect" in error_msg or "connection refused" in error_msg:
            print("\n❌ ERROR: Cannot connect to PostgreSQL database")
            print("\nTroubleshooting:")
            print("  1. Ensure PostgreSQL is running")
            print("  2. Verify DATABASE_URL in .env file")
            print("  3. Check database exists: createdb <database_name>")
            print("  4. Test connection: psql <database_url>")
        elif "does not exist" in error_msg and "database" in error_msg:
            print("\n❌ ERROR: Database does not exist")
            print("\nCreate the database first:")
            print("  createdb legal_analyst")
            print("  OR: psql -U postgres -c 'CREATE DATABASE legal_analyst;'")
        elif "authentication failed" in error_msg or "password" in error_msg:
            print("\n❌ ERROR: Authentication failed")
            print("\nCheck DATABASE_URL credentials in .env file")
        else:
            print(f"\n❌ Unexpected error during initialization: {e}")

        print("\n")
        raise


if __name__ == "__main__":
    """
    Script entry point for database initialization.

    Run this script after setting up your .env file:
        python -m app.db_init

    The script will:
    - Connect to PostgreSQL using DATABASE_URL from .env
    - Enable pgvector extension for semantic search
    - Create all required tables

    Safe to run multiple times (idempotent).
    """
    try:
        init_database()
    except Exception:
        # Error details already printed by init_database()
        exit(1)
