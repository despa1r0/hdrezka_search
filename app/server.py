from __future__ import annotations

import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from app.config import HOST, PORT, STATIC_DIR, TEMPLATES_DIR
from app.repositories.user_repository import ensure_test_users, get_all_users
from app.services.search_service import SearchService
from app.services.user_state_service import apply_movie_state


class AppHandler(BaseHTTPRequestHandler):
    search_service = SearchService()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path in {"/", "/index.html"}:
            self._send_file(TEMPLATES_DIR / "index.html", "text/html; charset=utf-8")
            return

        if parsed.path.startswith("/static/"):
            self._send_static_file(parsed.path)
            return

        if parsed.path == "/api/users":
            self._handle_users()
            return

        if parsed.path == "/api/search":
            self._handle_search(parsed.query)
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/api/movie-state":
            self._handle_movie_state()
            return

        if parsed.path == "/api/shutdown":
            self._send_json(HTTPStatus.OK, {"status": "stopping"})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def _handle_users(self) -> None:
        try:
            ensure_test_users()
            users = get_all_users()
        except Exception as exc:
            self._send_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "error": (
                        "PostgreSQL недоступен или схема не применена. "
                        f"Детали: {exc}"
                    )
                },
            )
            return

        self._send_json(HTTPStatus.OK, {"users": users})

    def _handle_search(self, query: str) -> None:
        params = {
            key: values[-1]
            for key, values in parse_qs(query, keep_blank_values=True).items()
        }
        status, payload = self.search_service.search(params)
        self._send_json(status, payload)

    def _handle_movie_state(self) -> None:
        try:
            payload = self._read_request_payload()
            user_id = int(payload.get("user_id", ""))
            movie_id = int(payload.get("movie_id", payload.get("movieId", "")))
            state = str(payload.get("state", "")).strip()
            action = str(payload.get("action", "set")).strip() or "set"
            apply_movie_state(user_id, movie_id, state, action)
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "user_id": user_id,
                "movie_id": movie_id,
                "state": state,
                "action": action,
            },
        )

    def _read_request_payload(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        content_type = self.headers.get("Content-Type", "")

        if "application/json" in content_type:
            data = json.loads(raw or "{}")
            if not isinstance(data, dict):
                raise ValueError("JSON body must be an object")
            return data

        parsed = parse_qs(raw, keep_blank_values=True)
        return {key: values[-1] for key, values in parsed.items()}

    def _send_static_file(self, request_path: str) -> None:
        relative_path = request_path.removeprefix("/static/").replace("/", "\\")
        path = (STATIC_DIR / relative_path).resolve()

        if not path.is_file() or STATIC_DIR.resolve() not in path.parents:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type == "application/javascript":
            content_type += "; charset=utf-8"

        self._send_file(path, content_type)

    def _send_file(self, path: Path, content_type: str) -> None:
        payload = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")


def run(host: str = HOST, port: int = PORT) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Open http://{host}:{port}")
    server.serve_forever()
