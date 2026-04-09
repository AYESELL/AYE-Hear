-- AYE Hear V1 Schema - Migration 003
-- HEAR-020: Participant naming_template constraint (ADR-0003, ADR-0007)
--
-- The naming_template field controls how participant identity is displayed and
-- matched during live intro detection (ADR-0003 Stage 0). Only the two V1
-- templates are valid. NULL indicates unset (pre-enrollment participants).
--
-- The constraint is named so repeated application is idempotent.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM   pg_constraint
        WHERE  conname    = 'chk_participants_naming_template'
          AND  conrelid   = 'participants'::regclass
    ) THEN
        ALTER TABLE participants
            ADD CONSTRAINT chk_participants_naming_template
            CHECK (
                naming_template IS NULL
                OR naming_template IN ('salutation_last_name_company', 'full_name_company')
            );
    END IF;
END;
$$;
