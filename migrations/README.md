# Database Migrations

This directory contains SQL migration scripts for database schema and data changes.

## Running Migrations

Migrations should be run manually in order against your PostgreSQL database:

```bash
# Connect to your database
psql -U your_user -d your_database

# Run a migration
\i migrations/001_normalize_entity_type.sql
```

Or using psql command line:

```bash
psql -U your_user -d your_database -f migrations/001_normalize_entity_type.sql
```

## Migration List

| Version | File | Description | Date |
|---------|------|-------------|------|
| 001 | `001_normalize_entity_type.sql` | Normalize all entity_type values to lowercase | 2025-11-01 |

## Future: Alembic Integration

For production use, consider migrating to [Alembic](https://alembic.sqlalchemy.org/) for automatic migration management:

```bash
pip install alembic
alembic init alembic
# Configure alembic.ini with your database URL
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

## Migration Best Practices

1. **Test on staging first** - Always test migrations on a non-production database
2. **Backup before migrating** - Create a database backup before running migrations
3. **Run in transaction** - All migrations use BEGIN/COMMIT for atomicity
4. **Document rollback** - Include rollback instructions when possible
5. **Version control** - All migrations are tracked in git
