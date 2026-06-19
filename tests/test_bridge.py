from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from rrpp_bridge.config import Settings
from rrpp_bridge.db import connect, initialize
from rrpp_bridge.queue import JobQueue
from rrpp_bridge.service import ingest_local, process_one
from rrpp_bridge.web import Application


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = connect(Path(self.tmp.name) / "bridge.db")
        initialize(self.conn)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    @staticmethod
    def payload(message_id="m-1", body="When is the event?"):
        return {"external_message_id": message_id, "sender": "test-user",
                "recipient": "promoter", "subject": "Question", "body_text": body}

    def test_ingestion_is_durable_and_idempotent(self):
        first, created = ingest_local(self.conn, self.payload())
        second, duplicate_created = ingest_local(self.conn, self.payload())
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(first, second)
        self.assertEqual(1, self.conn.execute("SELECT count(*) FROM events").fetchone()[0])
        self.assertEqual("queued", self.conn.execute("SELECT state FROM jobs").fetchone()[0])

    def test_worker_generates_audited_draft_without_dispatch(self):
        ingest_local(self.conn, self.payload())
        self.assertTrue(process_one(self.conn, "shadow"))
        action = self.conn.execute("SELECT * FROM actions").fetchone()
        decision = self.conn.execute("SELECT * FROM policy_decisions").fetchone()
        self.assertEqual(("draft_reply", "pending_review", "shadow"),
                         (action["type"], action["state"], action["mode"]))
        self.assertEqual("allowed", decision["outcome"])
        self.assertEqual(1, self.conn.execute(
            "SELECT count(*) FROM audit_log WHERE operation='action.decided'"
        ).fetchone()[0])

    def test_sensitive_request_escalates(self):
        ingest_local(self.conn, self.payload(body="Confirma una reserva VIP i el pagament"))
        process_one(self.conn, "dry-run")
        self.assertEqual("escalate_to_owner", self.conn.execute("SELECT type FROM actions").fetchone()[0])
        self.assertEqual("escalated", self.conn.execute("SELECT outcome FROM policy_decisions").fetchone()[0])

    def test_failure_reaches_dead_letter(self):
        ingest_local(self.conn, self.payload())
        queue = JobQueue(self.conn)
        job = queue.claim_next("test-worker")
        queue.fail(job, RuntimeError("controlled failure"), "test-worker", 1)
        failed = self.conn.execute("SELECT * FROM jobs").fetchone()
        self.assertEqual(("dead_letter", "RuntimeError"),
                         (failed["state"], failed["last_error_code"]))

    def test_oversized_payload_is_not_persisted(self):
        with self.assertRaises(ValueError):
            ingest_local(self.conn, self.payload(body="x" * 20_001))
        self.assertEqual(0, self.conn.execute("SELECT count(*) FROM events").fetchone()[0])


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        settings = Settings(Path(self.tmp.name) / "web.db", "shadow", "admin",
                            "long-test-password", "s" * 32)
        self.app = Application(settings)

    def tearDown(self):
        self.tmp.cleanup()

    def request(self, path="/", method="GET", body="", cookie=""):
        captured = {}
        def start_response(status, headers):
            captured.update(status=status, headers=dict(headers))
        raw = body.encode()
        environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "SERVER_NAME": "test",
                   "SERVER_PORT": "80", "SERVER_PROTOCOL": "HTTP/1.1",
                   "wsgi.url_scheme": "http", "wsgi.input": io.BytesIO(raw),
                   "CONTENT_LENGTH": str(len(raw)), "HTTP_COOKIE": cookie}
        response = b"".join(self.app(environ, start_response)).decode()
        return captured, response

    def test_dashboard_is_private(self):
        result, _ = self.request()
        self.assertEqual("303 See Other", result["status"])
        self.assertEqual("/login", result["headers"]["Location"])

    def test_login_is_signed_and_rejects_invalid_credentials(self):
        bad, page = self.request("/login", "POST", "username=admin&password=wrong")
        self.assertEqual("200 OK", bad["status"])
        self.assertIn("Invalid credentials", page)
        good, _ = self.request("/login", "POST",
                               "username=admin&password=long-test-password")
        self.assertEqual("303 See Other", good["status"])
        self.assertIn("HttpOnly", good["headers"]["Set-Cookie"])
        self.assertIn("SameSite=Strict", good["headers"]["Set-Cookie"])


if __name__ == "__main__":
    unittest.main()
