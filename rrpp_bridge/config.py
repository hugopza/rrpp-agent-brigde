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
        return cls(
            database_path=Path(os.getenv("RRPP_DATABASE_PATH", "var/rrpp-bridge.db")),
            mode=mode,
            dashboard_user=user,
            dashboard_password=password,
            session_secret=secret,
            host=os.getenv("RRPP_HOST", "127.0.0.1"),
            port=int(os.getenv("RRPP_PORT", "8080")),
            max_attempts=max(1, int(os.getenv("RRPP_MAX_ATTEMPTS", "3"))),
        )
