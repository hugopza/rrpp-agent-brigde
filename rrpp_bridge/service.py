"""Compatibility facade for the core bridge application services."""

from __future__ import annotations

import sqlite3
from typing import Any

from .adapters.local import normalize
from .executor import Executor
from .queue import JobQueue


def ingest_local(conn: sqlite3.Connection, payload: dict[str, Any]) -> tuple[str, bool]:
    return JobQueue(conn).enqueue(normalize(payload))


def process_one(conn: sqlite3.Connection, mode: str, worker_id: str = "worker.local",
                max_attempts: int = 3) -> bool:
    return Executor(conn, mode, max_attempts).run_once(worker_id)
