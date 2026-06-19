ALTER TABLE jobs ADD COLUMN lease_expires_at TEXT;
ALTER TABLE jobs ADD COLUMN dismissed_at TEXT;

CREATE TABLE runtime_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL
);

CREATE TABLE action_executions (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES actions(id),
    idempotency_key TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    simulated INTEGER NOT NULL CHECK(simulated = 1),
    created_at TEXT NOT NULL
);
CREATE INDEX idx_action_executions_action ON action_executions(action_id, created_at);
