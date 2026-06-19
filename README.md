# RRPP Agent Bridge

Dependency-free V1 bridge foundation for safe, observable processing of future customer communication channels.

## Local setup

Requires Python 3.12 or newer. Set the environment variables shown in `.env.example`; do not commit a real `.env` file.

PowerShell example:

```powershell
$env:RRPP_DASHBOARD_USER = "admin"
$env:RRPP_DASHBOARD_PASSWORD = "use-a-long-random-password"
$env:RRPP_SESSION_SECRET = "use-at-least-32-random-characters-here"
$env:RRPP_MODE = "shadow"
python -m rrpp_bridge init-db
python -m rrpp_bridge web
```

In a second terminal, run the independent worker:

```powershell
python -m rrpp_bridge worker
```

Open `http://127.0.0.1:8080`, authenticate, and submit a local simulator event. The event is durably persisted before the worker handles it. V1 produces drafts or owner escalations but has no external sender.

## Tests

```powershell
python -m unittest discover -s tests -v
```

See [`docs/agent-guide/`](docs/agent-guide/README.md) for requirements, architecture, security rules, and delivery milestones.
