-- AYE Hear V1 Schema - Migration 002
-- ADR-0007: Persistence Contract and Lifecycle (schema alignment)
-- HEAR-026: Remove redundant segment_text column from transcript_segments.
--
-- The canonical text field is 'text'. The 'segment_text' column was a legacy
-- alias that duplicated data and conflicted with the ADR-0007 spec (which uses
-- 'text' as the primary transcript field). App code, protocol engine and
-- transcription service all read/write 'text' exclusively.
--
-- Safe on fresh installs (column may not exist if 001 is re-applied after this
-- migration is available) and idempotent on existing installs.

ALTER TABLE transcript_segments
    DROP COLUMN IF EXISTS segment_text;
