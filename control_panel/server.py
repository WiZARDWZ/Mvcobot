from __future__ import annotations

import json
import logging
import mimetypes
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Any, Callable, Dict, Optional, Tuple
from urllib.parse import urlparse
from pathlib import Path
from http.server import ThreadingHTTPServer as _ThreadingHTTPServer

from . import logic

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_ROOT = REPO_ROOT / "webControl"


class ControlPanelRequestHandler(BaseHTTPRequestHandler):
    server_version = "MvcobotControl/1.0"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - keep signature
        LOGGER.info("ControlPanel: %s - %s", self.address_string(), format % args)

    # region helpers
    def _send_json(self, status: int, data: Dict[str, Any]) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, text: str, content_type: str = "text/plain; charset=utf-8") -> None:
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            raise logic.ControlPanelError("ساختار JSON نامعتبر است.")

    def _handle_api(self, func: Callable[[], Tuple[int, Dict[str, Any]]]) -> None:
        try:
            status, payload = func()
        except logic.ControlPanelError as exc:
            LOGGER.warning("Control panel error: %s", exc.message)
            self._send_json(exc.status, {"message": exc.message})
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.exception("Unhandled server error: %s", exc)
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"message": "خطای داخلی سرور"})
        else:
            self._send_json(status, payload)

    # endregion

    # region HTTP verbs
    def do_GET(self) -> None:  # noqa: N802  # required by BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        path = parsed.path or "/"

        if path.startswith("/api/"):
            self._dispatch_get_api(path)
            return

        if path == "/" or path == "/index.html":
            self._serve_index()
            return

        if path.startswith("/assets/"):
            self._serve_static(path)
            return

        if path == "/healthz":
            self._send_json(HTTPStatus.OK, logic.get_health())
            return

        self.send_error(HTTPStatus.NOT_FOUND, "File not found")

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"

        if not path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Invalid endpoint")
            return

        body = self._read_json_body()

        if path == "/api/v1/commands":
            self._handle_api(lambda: (HTTPStatus.CREATED, logic.create_command(body)))
        elif path == "/api/v1/blocklist":
            self._handle_api(lambda: (HTTPStatus.CREATED, logic.add_block_item(body)))
        elif path == "/api/v1/bot/toggle":
            active = bool(body.get("active"))
            self._handle_api(lambda: (HTTPStatus.OK, logic.toggle_bot(active)))
        elif path == "/api/v1/cache/invalidate":
            self._handle_api(lambda: (HTTPStatus.OK, logic.invalidate_cache()))
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"

        if not path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Invalid endpoint")
            return

        body = self._read_json_body()

        if path == "/api/v1/settings":
            self._handle_api(lambda: (HTTPStatus.OK, logic.update_settings(body)))
            return

        if path.startswith("/api/v1/commands/"):
            command_id = path.rsplit("/", 1)[-1]
            self._handle_api(lambda: (HTTPStatus.OK, logic.update_command(command_id, body)))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"

        if not path.startswith("/api/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Invalid endpoint")
            return

        if path.startswith("/api/v1/commands/"):
            command_id = path.rsplit("/", 1)[-1]
            self._handle_api(lambda: (HTTPStatus.OK, logic.delete_command(command_id)))
            return

        if path.startswith("/api/v1/blocklist/"):
            item_id = path.rsplit("/", 1)[-1]
            self._handle_api(lambda: (HTTPStatus.OK, logic.remove_block_item(item_id)))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    # endregion

    # region API dispatch
    def _dispatch_get_api(self, path: str) -> None:
        if path == "/api/v1/metrics":
            self._handle_api(lambda: (HTTPStatus.OK, logic.get_metrics()))
        elif path == "/api/v1/commands":
            self._handle_api(lambda: (HTTPStatus.OK, logic.get_commands()))
        elif path == "/api/v1/blocklist":
            self._handle_api(lambda: (HTTPStatus.OK, logic.get_blocklist()))
        elif path == "/api/v1/settings":
            self._handle_api(lambda: (HTTPStatus.OK, logic.get_settings()))
        elif path == "/api/v1/audit-log":
            self._handle_api(lambda: (HTTPStatus.OK, logic.get_audit_log()))
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    # endregion

    # region static files
    def _serve_index(self) -> None:
        index_path = WEB_ROOT / "index.html"
        if not index_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "index.html not found")
            return
        content = index_path.read_text("utf-8")
        self._send_text(HTTPStatus.OK, content, "text/html; charset=utf-8")

    def _serve_static(self, path: str) -> None:
        rel = path.lstrip("/")
        target = (WEB_ROOT / rel).resolve()
        if not str(target).startswith(str(WEB_ROOT.resolve())):
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
            return
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return
        mime, _ = mimetypes.guess_type(str(target))
        content_type = mime or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    # endregion


class ThreadedHTTPServer(_ThreadingHTTPServer):
    """Threading HTTP server with daemon threads enabled.

    Python's :class:`http.server.ThreadingHTTPServer` already mixes in
    :class:`socketserver.ThreadingMixIn`. Subclassing it alongside the mixin on
    some interpreters (notably CPython 3.8 on Windows) can raise a Method
    Resolution Order (MRO) error. We only need to override ``daemon_threads``
    so inheriting directly from ``ThreadingHTTPServer`` keeps compatibility
    while preserving the threaded behaviour."""

    daemon_threads = True


def start_control_panel_server(host: str = "0.0.0.0", port: int = 8080) -> Optional[ThreadedHTTPServer]:
    if not WEB_ROOT.exists():
        LOGGER.error("Control panel assets not found at %s", WEB_ROOT)
        return None

    try:
        server = ThreadedHTTPServer((host, port), ControlPanelRequestHandler)
    except OSError as exc:
        LOGGER.error("Failed to start control panel server on %s:%s - %s", host, port, exc)
        return None

    thread = threading.Thread(target=server.serve_forever, name="control-panel", daemon=True)
    thread.start()
    LOGGER.info("Control panel available at http://%s:%s", host or "127.0.0.1", port)
    return server
