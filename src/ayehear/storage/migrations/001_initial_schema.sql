-- AYE Hear V1 Schema - Initial Migration
-- ADR-0007: Persistence Contract and Lifecycle
-- ADR-0006: PostgreSQL Local Deployment Model on Windows
-- PostgreSQL 16+

-- meetings: primary lifecycle container
CREATE TABLE IF NOT EXISTS meetings (
    id           VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    title        VARCHAR(512) NOT NULL,
    mode         VARCHAR(64)  NOT NULL DEFAULT 'internal',
    meeting_type VARCHAR(64)  NOT NULL DEFAULT 'internal',
    status       VARCHAR(32)  NOT NULL DEFAULT 'pending',
    started_at   TIMESTAMPTZ,
    ended_at     TIMESTAMPTZ,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- speaker_profiles: reusable enrolled speaker identity records
CREATE TABLE IF NOT EXISTS speaker_profiles (
    id                VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    display_name      VARCHAR(256) NOT NULL,
    embedding_vector  JSONB,
    embedding_version VARCHAR(64),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- participants: meeting-scoped participant registration (ADR-0007)
CREATE TABLE IF NOT EXISTS participants (
    id                 VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    meeting_id         VARCHAR(36)  NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    speaker_profile_id VARCHAR(36)  REFERENCES speaker_profiles(id) ON DELETE SET NULL,
    display_name       VARCHAR(256) NOT NULL,
    first_name         VARCHAR(128),
    last_name          VARCHAR(128),
    salutation         VARCHAR(64),
    organization       VARCHAR(256),
    naming_template    VARCHAR(128),
    enrollment_status  VARCHAR(32)  NOT NULL DEFAULT 'pending',
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_participants_meeting_id ON participants(meeting_id);

-- transcript_segments: timestamped transcript units with speaker attribution
CREATE TABLE IF NOT EXISTS transcript_segments (
    id                VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    meeting_id        VARCHAR(36) NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    participant_id    VARCHAR(36) REFERENCES participants(id) ON DELETE SET NULL,
    start_ms          INTEGER     NOT NULL,
    end_ms            INTEGER     NOT NULL,
    speaker_name      VARCHAR(256) NOT NULL DEFAULT 'Unknown Speaker',
    text              TEXT        NOT NULL DEFAULT '',
    segment_text      TEXT        NOT NULL DEFAULT '',
    confidence_score  FLOAT       NOT NULL DEFAULT 0.0,
    is_silence        BOOLEAN     NOT NULL DEFAULT FALSE,
    manual_correction BOOLEAN    NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transcript_meeting_id   ON transcript_segments(meeting_id);
CREATE INDEX IF NOT EXISTS idx_transcript_participant_id ON transcript_segments(participant_id);
CREATE INDEX IF NOT EXISTS idx_transcript_confidence   ON transcript_segments(confidence_score);

-- protocol_snapshots: immutable append-only protocol revisions
CREATE TABLE IF NOT EXISTS protocol_snapshots (
    id               VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    meeting_id       VARCHAR(36) NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    snapshot_version INTEGER     NOT NULL,
    snapshot_content JSONB       NOT NULL,
    engine_version   VARCHAR(64) NOT NULL DEFAULT 'v1.0',
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (meeting_id, snapshot_version)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_meeting_id ON protocol_snapshots(meeting_id);

-- protocol_action_items: normalized action items extracted from snapshots
CREATE TABLE IF NOT EXISTS protocol_action_items (
    id                      VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    protocol_snapshot_id    VARCHAR(36) NOT NULL REFERENCES protocol_snapshots(id) ON DELETE CASCADE,
    assignee_participant_id VARCHAR(36) REFERENCES participants(id) ON DELETE SET NULL,
    title                   VARCHAR(512) NOT NULL,
    description             TEXT,
    status                  VARCHAR(32) NOT NULL DEFAULT 'open',
    due_date                TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_action_items_snapshot_id ON protocol_action_items(protocol_snapshot_id);

-- Updated-at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at on all mutable tables
DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['meetings','participants','speaker_profiles','transcript_segments','protocol_action_items']
    LOOP
        EXECUTE format(
            'DROP TRIGGER IF EXISTS trg_updated_at_%1$s ON %1$s;
             CREATE TRIGGER trg_updated_at_%1$s
             BEFORE UPDATE ON %1$s
             FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();',
            t
        );
    END LOOP;
END;
$$;
