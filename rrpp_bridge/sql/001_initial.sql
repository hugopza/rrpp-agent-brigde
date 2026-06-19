CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY, channel TEXT NOT NULL, external_message_id TEXT NOT NULL,
    sender TEXT NOT NULL, recipient TEXT NOT NULL, subject TEXT NOT NULL,
    body_text TEXT NOT NULL, received_at TEXT NOT NULL, ingested_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL, work_key TEXT NOT NULL, status TEXT NOT NULL,
    UNIQUE(channel, external_message_id)
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, event_id TEXT NOT NULL UNIQUE REFERENCES events(id),
    work_key TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
    available_at TEXT NOT NULL, claimed_at TEXT, worker_id TEXT,
    last_error_code TEXT, last_error_message TEXT, created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id),
    job_id TEXT NOT NULL REFERENCES jobs(id), type TEXT NOT NULL,
    payload_json TEXT NOT NULL, state TEXT NOT NULL, mode TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS policy_decisions (
    id TEXT PRIMARY KEY, action_id TEXT NOT NULL UNIQUE REFERENCES actions(id),
    outcome TEXT NOT NULL, policy_id TEXT NOT NULL, reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, occurred_at TEXT NOT NULL,
    actor TEXT NOT NULL, operation TEXT NOT NULL, entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL, outcome TEXT NOT NULL, details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_claim ON jobs(state, available_at, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_work_state ON jobs(work_key, state);
CREATE INDEX IF NOT EXISTS idx_audit_recent ON audit_log(occurred_at DESC);
