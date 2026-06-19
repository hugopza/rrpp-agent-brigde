from __future__ import annotations

import argparse
import socket
import time
from wsgiref.simple_server import make_server

from .config import Settings
from .db import connect, initialize
from .service import process_one
from .web import Application


def main() -> None:
    parser = argparse.ArgumentParser(prog="rrpp-bridge")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db")
    sub.add_parser("web")
    worker = sub.add_parser("worker")
    worker.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings.from_env(require_auth=args.command == "web")
    conn = connect(settings.database_path)
    initialize(conn)
    if args.command == "init-db":
        print(f"Initialized {settings.database_path}")
        return
    if args.command == "web":
        conn.close()
        app = Application(settings)
        print(f"Dashboard listening on http://{settings.host}:{settings.port} ({settings.mode})")
        with make_server(settings.host, settings.port, app) as server:
            server.serve_forever()
        return
    worker_id = f"worker.{socket.gethostname()}"
    while True:
        processed = process_one(conn, settings.mode, worker_id, settings.max_attempts)
        if args.once:
            break
        if not processed:
            time.sleep(1)


if __name__ == "__main__":
    main()
