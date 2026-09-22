from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    server_version = "WDOSFoundation/0.1"

    def _send_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/app"):
            self._send_json(HTTPStatus.OK, {
                "service": "wdos",
                "stage": "foundation",
                "environment": os.getenv("WDOS_ENVIRONMENT", "local"),
                "message": "WDOS Stage 1 foundation shell",
            })
            return
        if self.path in ("/health", "/api/health"):
            self._send_json(HTTPStatus.OK, {
                "status": "ok",
                "service": "wdos",
                "environment": os.getenv("WDOS_ENVIRONMENT", "local"),
            })
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"wdos.http {self.address_string()} {fmt % args}")


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"WDOS foundation listening on {port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
