-- AYE Hear V1 Schema - Migration 004
-- HEAR-022: Transcript correction audit log (ADR-0003, ADR-0007)
--
-- Immutable, append-only audit record for every manual speaker-name or
-- participant-identity correction applied to a transcript segment.
--
-- Every call to TranscriptSegmentRepository.apply_correction() writes one row
-- here before mutating the source segment. The transcript segment itself is
-- updated in-place (speaker_name, participant_id, manual_correction=true);
-- this table preserves the before-state for auditability.
--
-- Rows are never updated or deleted (only CASCADE-deleted when the parent
-- segment is deleted, typically when the meeting is purged).

CREATE TABLE IF NOT EXISTS transcript_correction_log (
    id                       VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    transcript_segment_id    VARCHAR(36)  NOT NULL
        REFERENCES transcript_segments(id) ON DELETE CASCADE,
    previous_speaker_name    VARCHAR(256) NOT NULL,
    corrected_speaker_name   VARCHAR(256) NOT NULL,
    previous_participant_id  VARCHAR(36)
        REFERENCES participants(id) ON DELETE SET NULL,
    corrected_participant_id VARCHAR(36)
        REFERENCES participants(id) ON DELETE SET NULL,
    corrected_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_correction_log_segment_id
    ON transcript_correction_log(transcript_segment_id);
