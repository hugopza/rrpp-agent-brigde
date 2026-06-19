from __future__ import annotations

import hashlib
import hmac
import html
import json
import secrets
import sqlite3
import time
from http import cookies
from urllib.parse import parse_qs
from wsgiref.util import setup_testing_defaults

from .config import Settings
from .db import connect, initialize
from .service import ingest_local


def _escape(value: object) -> str:
    return html.escape(str(value or ""))


class Application:
    def __init__(self, settings: Settings):
        self.settings = settings
        conn = connect(settings.database_path)
        initialize(conn)
        conn.close()

    def _sign(self, value: str) -> str:
        signature = hmac.new(self.settings.session_secret.encode(), value.encode(), hashlib.sha256).hexdigest()
        return f"{value}.{signature}"

    def _session(self, environ: dict) -> tuple[bool, str]:
        jar = cookies.SimpleCookie(environ.get("HTTP_COOKIE", ""))
        morsel = jar.get("rrpp_session")
        if not morsel:
            return False, ""
        try:
            user, expiry, csrf, signature = morsel.value.split(".", 3)
            raw = f"{user}.{expiry}.{csrf}"
            expected = self._sign(raw).rsplit(".", 1)[1]
            valid = hmac.compare_digest(signature, expected) and int(expiry) >= int(time.time())
            return valid and hmac.compare_digest(user, self.settings.dashboard_user), csrf
        except (ValueError, TypeError):
            return False, ""

    @staticmethod
    def _body(environ: dict, limit: int = 25_000) -> dict[str, str]:
        try:
            length = int(environ.get("CONTENT_LENGTH") or 0)
        except ValueError as exc:
            raise ValueError("Invalid content length") from exc
        if length > limit:
            raise ValueError("Request body is too large")
        raw = environ["wsgi.input"].read(length).decode("utf-8")
        return {key: values[0] for key, values in parse_qs(raw, keep_blank_values=True).items()}

    @staticmethod
    def _respond(start_response, status: str, body: str, headers=None):
        encoded = body.encode("utf-8")
        base = [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(encoded))),
                ("X-Content-Type-Options", "nosniff"), ("X-Frame-Options", "DENY"),
                ("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'")]
        start_response(status, base + (headers or []))
        return [encoded]

    def __call__(self, environ, start_response):
        setup_testing_defaults(environ)
        path, method = environ["PATH_INFO"], environ["REQUEST_METHOD"]
        authenticated, csrf = self._session(environ)
        if path == "/login":
            return self._login(environ, start_response, method)
        if not authenticated:
            return self._respond(start_response, "303 See Other", "", [("Location", "/login")])
        if path == "/logout" and method == "POST":
            form = self._body(environ)
            if not hmac.compare_digest(form.get("csrf", ""), csrf):
                return self._respond(start_response, "403 Forbidden", self._page("Forbidden", "Invalid CSRF token"))
            return self._respond(start_response, "303 See Other", "", [
                ("Location", "/login"),
                ("Set-Cookie", "rrpp_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"),
            ])
        if path == "/simulate" and method == "POST":
            form = self._body(environ)
            if not hmac.compare_digest(form.get("csrf", ""), csrf):
                return self._respond(start_response, "403 Forbidden", self._page("Forbidden", "Invalid CSRF token"))
            try:
                conn = connect(self.settings.database_path)
                event_id, created = ingest_local(conn, form)
                conn.close()
                location = f"/?notice={'accepted' if created else 'duplicate'}:{event_id}"
                return self._respond(start_response, "303 See Other", "", [("Location", location)])
            except ValueError as exc:
                return self._respond(start_response, "400 Bad Request", self._page("Invalid event", _escape(exc)))
        if path == "/" and method == "GET":
            return self._dashboard(start_response, csrf)
        return self._respond(start_response, "404 Not Found", self._page("Not found", "Unknown route"))

    def _login(self, environ, start_response, method: str):
        error = ""
        if method == "POST":
            try:
                form = self._body(environ, 4_096)
                user_ok = hmac.compare_digest(form.get("username", ""), self.settings.dashboard_user)
                pass_ok = hmac.compare_digest(form.get("password", ""), self.settings.dashboard_password)
                if user_ok and pass_ok:
                    csrf = secrets.token_urlsafe(24)
                    raw = f"{self.settings.dashboard_user}.{int(time.time()) + 28_800}.{csrf}"
                    return self._respond(start_response, "303 See Other", "", [
                        ("Location", "/"),
                        ("Set-Cookie", f"rrpp_session={self._sign(raw)}; Path=/; HttpOnly; SameSite=Strict"),
                    ])
                error = "Invalid credentials"
            except ValueError as exc:
                error = str(exc)
        form = f"""<form method=post><label>User <input name=username required autocomplete=username></label>
<label>Password <input name=password type=password required autocomplete=current-password></label>
<button type=submit>Sign in</button></form><p class=error>{_escape(error)}</p>"""
        return self._respond(start_response, "200 OK", self._page("Private dashboard", form))

    def _dashboard(self, start_response, csrf: str):
        conn = connect(self.settings.database_path)
        counts = {row["state"]: row["n"] for row in conn.execute("SELECT state, count(*) n FROM jobs GROUP BY state")}
        events = conn.execute("SELECT * FROM events ORDER BY ingested_at DESC LIMIT 20").fetchall()
        actions = conn.execute(
            "SELECT a.*,p.outcome,p.policy_id FROM actions a JOIN policy_decisions p ON p.action_id=a.id "
            "ORDER BY a.created_at DESC LIMIT 20"
        ).fetchall()
        audits = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 30").fetchall()
        failures = conn.execute(
            "SELECT * FROM jobs WHERE last_error_code IS NOT NULL ORDER BY updated_at DESC LIMIT 20"
        ).fetchall()
        conn.close()
        metrics = " ".join(f"<strong>{_escape(k)}</strong>: {_escape(counts.get(k, 0))}" for k in
                           ("queued", "processing", "completed", "dead_letter"))
        event_rows = "".join(
            f"<tr><td>{_escape(e['id'])}</td><td>{_escape(e['sender'])}</td><td>{_escape(e['subject'])}</td>"
            f"<td>{_escape(e['status'])}</td><td>{_escape(e['ingested_at'])}</td></tr>" for e in events
        ) or "<tr><td colspan=5>No events</td></tr>"
        action_rows = "".join(
            f"<tr><td>{_escape(a['id'])}</td><td>{_escape(a['type'])}</td><td>{_escape(a['outcome'])}</td>"
            f"<td>{_escape(a['state'])}</td><td>{_escape(a['policy_id'])}</td></tr>" for a in actions
        ) or "<tr><td colspan=5>No actions</td></tr>"
        failure_rows = "".join(
            f"<tr><td>{_escape(j['id'])}</td><td>{_escape(j['state'])}</td><td>{_escape(j['attempts'])}</td>"
            f"<td>{_escape(j['last_error_code'])}: {_escape(j['last_error_message'])}</td></tr>" for j in failures
        ) or "<tr><td colspan=4>No failures</td></tr>"
        audit_rows = "".join(
            f"<tr><td>{_escape(a['occurred_at'])}</td><td>{_escape(a['actor'])}</td>"
            f"<td>{_escape(a['operation'])}</td><td>{_escape(a['outcome'])}</td></tr>" for a in audits
        ) or "<tr><td colspan=4>No activity</td></tr>"
        content = f"""
<header><h1>RRPP Agent Bridge</h1><p>Mode: <strong>{_escape(self.settings.mode)}</strong> | {metrics}</p>
<form method=post action=/logout><input type=hidden name=csrf value="{_escape(csrf)}"><button>Sign out</button></form></header>
<section><h2>Local simulator</h2><form method=post action=/simulate>
<input type=hidden name=csrf value="{_escape(csrf)}"><label>External ID <input name=external_message_id required maxlength=200></label>
<label>Sender <input name=sender required maxlength=200></label><label>Recipient <input name=recipient required maxlength=200></label>
<label>Subject <input name=subject maxlength=500></label><label>Message <textarea name=body_text required maxlength=20000></textarea></label>
<button>Persist event</button></form></section>
<section><h2>Events</h2><table><tr><th>ID</th><th>Sender</th><th>Subject</th><th>Status</th><th>Ingested</th></tr>{event_rows}</table></section>
<section><h2>Actions and policy</h2><table><tr><th>ID</th><th>Type</th><th>Decision</th><th>State</th><th>Policy</th></tr>{action_rows}</table></section>
<section><h2>Failed jobs</h2><table><tr><th>ID</th><th>State</th><th>Attempts</th><th>Error</th></tr>{failure_rows}</table></section>
<section><h2>Recent activity</h2><table><tr><th>Time</th><th>Actor</th><th>Operation</th><th>Outcome</th></tr>{audit_rows}</table></section>"""
        return self._respond(start_response, "200 OK", self._page("RRPP Agent Bridge", content))

    @staticmethod
    def _page(title: str, content: str) -> str:
        return f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width">
<title>{_escape(title)}</title><style>body{{font:15px system-ui;max-width:1200px;margin:auto;padding:24px;background:#f5f6f8;color:#17202a}}
section,header{{background:white;padding:18px;margin:14px 0;border-radius:8px}}form{{display:grid;gap:10px;max-width:650px}}
label{{display:grid;gap:4px}}input,textarea,button{{font:inherit;padding:8px}}textarea{{min-height:90px}}table{{border-collapse:collapse;width:100%;display:block;overflow:auto}}
th,td{{padding:8px;border-bottom:1px solid #ddd;text-align:left;white-space:nowrap}}.error{{color:#a00}}</style><body>{content}</body></html>"""
