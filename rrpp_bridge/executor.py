from __future__ import annotations

import json
import sqlite3
import uuid

from .agent import generate_action
from .audit import record, utc_now
from .db import transaction
from .policy import Policy
from .queue import JobQueue


class Executor:
    def __init__(self, conn: sqlite3.Connection, mode: str, max_attempts: int = 3):
        self.conn, self.mode, self.max_attempts = conn, mode, max_attempts
        self.queue, self.policy = JobQueue(conn), Policy()

    def run_once(self, worker_id: str = "worker.local") -> bool:
        job = self.queue.claim_next(worker_id)
        if job is None:
            return False
        try:
            event = self.conn.execute("SELECT * FROM events WHERE id=?", (job["event_id"],)).fetchone()
            if event is None:
                raise RuntimeError("event_not_found")
            action = generate_action(event["body_text"])
            decision = self.policy.decide(action)
            action_id, decision_id, timestamp = (
                f"act_{uuid.uuid4().hex}", f"dec_{uuid.uuid4().hex}", utc_now()
            )
            # Deliberate V1 boundary: there is no external dispatch implementation.
            state = "pending_review" if decision.outcome in {"allowed", "escalated"} else decision.outcome
            with transaction(self.conn, immediate=True):
                self.conn.execute(
                    "INSERT INTO actions VALUES(?,?,?,?,?,?,?,?,?)",
                    (action_id, event["id"], job["id"], action.type,
                     json.dumps(action.payload, separators=(",", ":")), state, self.mode,
                     timestamp, timestamp),
                )
                self.conn.execute("INSERT INTO policy_decisions VALUES(?,?,?,?,?,?)", (
                    decision_id, action_id, decision.outcome, decision.policy_id,
                    decision.reason, timestamp,
                ))
                record(self.conn, worker_id, "action.generated", "action", action_id, state,
                       {"type": action.type, "mode": self.mode})
                record(self.conn, "policy", "action.decided", "action", action_id,
                       decision.outcome, {"policy_id": decision.policy_id, "mode": self.mode})
                self.conn.execute("UPDATE jobs SET state='completed',updated_at=? WHERE id=?",
                                  (timestamp, job["id"]))
                self.conn.execute("UPDATE events SET status='processed' WHERE id=?", (event["id"],))
                record(self.conn, worker_id, "job.completed", "job", job["id"], "completed")
            return True
        except Exception as exc:
            self.queue.fail(job, exc, worker_id, self.max_attempts)
            return True
