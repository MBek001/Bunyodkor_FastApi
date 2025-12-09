-- Manual migrations for archive system
-- Run this SQL in your PostgreSQL database

-- Migration 003: Add archive_year to tables
-- ============================================

-- Add archive_year to groups if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'groups' AND column_name = 'archive_year'
    ) THEN
        ALTER TABLE groups ADD COLUMN archive_year INTEGER NOT NULL DEFAULT 2025;
        CREATE INDEX ix_groups_archive_year ON groups(archive_year);
    END IF;
END $$;

-- Add archive_year to students if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'students' AND column_name = 'archive_year'
    ) THEN
        ALTER TABLE students ADD COLUMN archive_year INTEGER NOT NULL DEFAULT 2025;
        CREATE INDEX ix_students_archive_year ON students(archive_year);
    END IF;
END $$;

-- Add archive_year to contracts if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contracts' AND column_name = 'archive_year'
    ) THEN
        ALTER TABLE contracts ADD COLUMN archive_year INTEGER NOT NULL DEFAULT 2025;
        CREATE INDEX ix_contracts_archive_year ON contracts(archive_year);
    END IF;
END $$;


-- Migration 004: Add status to groups and ARCHIVED enum values
-- ============================================

-- Add status to groups if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'groups' AND column_name = 'status'
    ) THEN
        ALTER TABLE groups ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';
        CREATE INDEX ix_groups_status ON groups(status);
    END IF;
END $$;

-- Note: Students and contracts already have status columns
-- The new enum values (archived) are handled in Python code

-- Verify changes
SELECT 'Migration complete!' AS status;
SELECT
    'groups' AS table_name,
    COUNT(*) FILTER (WHERE archive_year IS NOT NULL) AS with_archive_year,
    COUNT(*) FILTER (WHERE status IS NOT NULL) AS with_status,
    COUNT(*) AS total
FROM groups
UNION ALL
SELECT
    'students',
    COUNT(*) FILTER (WHERE archive_year IS NOT NULL),
    NULL,
    COUNT(*)
FROM students
UNION ALL
SELECT
    'contracts',
    COUNT(*) FILTER (WHERE archive_year IS NOT NULL),
    NULL,
    COUNT(*)
FROM contracts;
