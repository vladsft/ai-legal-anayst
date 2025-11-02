-- Migration: Normalize entity_type to lowercase
-- Date: 2025-11-01
-- Description: Updates all existing entity_type values to lowercase to match new normalization logic
--
-- Background:
-- - Previous code allowed mixed-case entity_type values (Party, PARTY, party)
-- - New code normalizes to lowercase on write (crud.py line 377)
-- - This migration ensures existing data matches the new convention
--
-- Rollback: Not provided - this is a data normalization change
-- If needed: UPDATE entities SET entity_type = INITCAP(entity_type);

BEGIN;

-- Update all entity_type values to lowercase
UPDATE entities
SET entity_type = LOWER(entity_type)
WHERE entity_type != LOWER(entity_type);

-- Log the migration
-- Note: Adjust this if you have a migrations tracking table
-- Example: INSERT INTO schema_migrations (version, applied_at) VALUES ('001', NOW());

COMMIT;

-- Verification query (run after migration):
-- SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type ORDER BY entity_type;
-- Expected: All values should be lowercase (party, date, financial_term, etc.)
