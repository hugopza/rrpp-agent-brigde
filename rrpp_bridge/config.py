from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

VALID_MODES = frozenset({"shadow", "dry-run", "canary", "live"})


@dataclass(frozen=True)
class Settings:
    database_path: Path
    mode: str
    dashboard_user: str
    dashboard_password: str
    session_secret: str
    host: str = "127.0.0.1"
    port: int = 8080
    max_attempts: int = 3
    lease_seconds: int = 60
    canary_senders: frozenset[str] = frozenset()

    @classmethod
    def from_env(cls, *, require_auth: bool = True) -> "Settings":
        mode = os.getenv("RRPP_MODE", "shadow")
        if mode not in VALID_MODES:
            raise ValueError(f"RRPP_MODE must be one of: {', '.join(sorted(VALID_MODES))}")
        user = os.getenv("RRPP_DASHBOARD_USER", "")
        password = os.getenv("RRPP_DASHBOARD_PASSWORD", "")
        secret = os.getenv("RRPP_SESSION_SECRET", "")
        if require_auth and (not user or len(password) < 12 or len(secret) < 32):
            raise ValueError(
                "Dashboard credentials are required; password must be at least 12 "
                "characters and session secret at least 32 characters"
            )
        try:
            port = int(os.getenv("RRPP_PORT", "8080"))
            max_attempts = int(os.getenv("RRPP_MAX_ATTEMPTS", "3"))
            lease_seconds = int(os.getenv("RRPP_LEASE_SECONDS", "60"))
        except ValueError as exc:
            raise ValueError("Port, max attempts, and lease seconds must be integers") from exc
        if not 1 <= port <= 65535 or max_attempts < 1 or lease_seconds < 5:
            raise ValueError("Port must be 1-65535, max attempts >= 1, and lease seconds >= 5")
        canary_senders = frozenset(
            value.strip().casefold() for value in os.getenv("RRPP_CANARY_SENDERS", "").split(",")
            if value.strip()
        )
        return cls(
            database_path=Path(os.getenv("RRPP_DATABASE_PATH", "var/rrpp-bridge.db")),
            mode=mode,
            dashboard_user=user,
            dashboard_password=password,
            session_secret=secret,
            host=os.getenv("RRPP_HOST", "127.0.0.1"),
            port=port,
            max_attempts=max_attempts,
            lease_seconds=lease_seconds,
            canary_senders=canary_senders,
        )
