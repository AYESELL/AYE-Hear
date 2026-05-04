-- AYE Hear V1 Schema - Migration 005
-- HEAR-164: Restore transcript/protocol persistence on older runtime schemas.
--
-- ORM and repository code persist separate ASR and speaker-attribution
-- confidence values. Older installed runtimes predate these nullable columns,
-- which causes transcript segment inserts and downstream protocol rebuilds to
-- fail with UndefinedColumn. Add both columns forward-compatibly.

ALTER TABLE transcript_segments
    ADD COLUMN IF NOT EXISTS asr_confidence FLOAT;

ALTER TABLE transcript_segments
    ADD COLUMN IF NOT EXISTS speaker_confidence FLOAT;