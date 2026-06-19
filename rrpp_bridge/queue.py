from __future__ import annotations

import json
import sqlite3
import uuid

from .audit import record, utc_now
from .db import transaction
from .models import NormalizedEvent


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class JobQueue:
    """SQLite/WAL durable queue with per-conversation serialization."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def enqueue(self, event: NormalizedEvent) -> tuple[str, bool]:
        event_id, job_id, timestamp = _id("evt"), _id("job"), utc_now()
        try:
            with transaction(self.conn, immediate=True):
                self.conn.execute(
                    "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (event_id, event.channel, event.external_message_id, event.sender,
                     event.recipient, event.subject, event.body_text, timestamp, timestamp,
                     json.dumps(event.metadata, separators=(",", ":")), event.work_key, "queued"),
                )
                self.conn.execute(
                    "INSERT INTO jobs(id,event_id,work_key,state,available_at,created_at,updated_at) "
                    "VALUES(?,?,?,'queued',?,?,?)",
                    (job_id, event_id, event.work_key, timestamp, timestamp, timestamp),
                )
                record(self.conn, f"adapter.{event.channel}", "event.accepted", "event",
                       event_id, "accepted", {"channel": event.channel, "job_id": job_id})
            return event_id, True
        except sqlite3.IntegrityError:
            row = self.conn.execute(
                "SELECT id FROM events WHERE channel=? AND external_message_id=?",
                (event.channel, event.external_message_id),
            ).fetchone()
            if row is None:
                raise
            record(self.conn, f"adapter.{event.channel}", "event.duplicate", "event",
                   row["id"], "ignored")
            return str(row["id"]), False

    def claim_next(self, worker_id: str) -> sqlite3.Row | None:
        timestamp = utc_now()
        with transaction(self.conn, immediate=True):
            job = self.conn.execute(
                "SELECT * FROM jobs j WHERE j.state='queued' AND j.available_at<=? "
                "AND NOT EXISTS (SELECT 1 FROM jobs r WHERE r.work_key=j.work_key "
                "AND r.state='processing') ORDER BY j.created_at LIMIT 1", (timestamp,),
            ).fetchone()
            if job is None:
                return None
            self.conn.execute(
                "UPDATE jobs SET state='processing',attempts=attempts+1,claimed_at=?,worker_id=?,updated_at=? "
                "WHERE id=?", (timestamp, worker_id, timestamp, job["id"]),
            )
            record(self.conn, worker_id, "job.claimed", "job", job["id"], "processing",
                   {"attempt": int(job["attempts"]) + 1, "work_key": job["work_key"]})
        return self.conn.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone()

    def fail(self, job: sqlite3.Row, exc: Exception, worker_id: str, max_attempts: int) -> None:
        terminal = int(job["attempts"]) >= max_attempts
        state, timestamp = ("dead_letter" if terminal else "queued"), utc_now()
        code, message = type(exc).__name__, str(exc)[:500]
        with transaction(self.conn, immediate=True):
            self.conn.execute(
                "UPDATE jobs SET state=?,last_error_code=?,last_error_message=?,updated_at=? WHERE id=?",
                (state, code, message, timestamp, job["id"]),
            )
            record(self.conn, worker_id, "job.failed", "job", job["id"], state,
                   {"error_code": code, "attempt": job["attempts"]})
