"""
Local HTTP Server for ProjectPulsewire Web Dashboard.
"""

import http.server
import json
import logging
import mimetypes
import os
import socket
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from projectpulsewire.web.api import ApiHandler

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"


def get_network_ips() -> list:
    """Discover all non-loopback local network IP addresses."""
    ips = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.2)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass

    return ips


def _is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a TCP port is currently in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        test_host = "127.0.0.1" if host in ("0.0.0.0", "") else host
        return s.connect_ex((test_host, port)) == 0


def find_available_port(start_port: int = 8080, max_attempts: int = 20, host: str = "0.0.0.0") -> int:
    """Find the next available port starting from start_port."""
    for port in range(start_port, start_port + max_attempts):
        if not _is_port_in_use(port, host):
            return port
    return start_port


class PulsewireRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Handles HTTP requests for static assets and REST API endpoints."""

    server_instance: Optional['PulsewireServer'] = None

    def __init__(self, *args, **kwargs):
        # We serve from the web package directory
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        """Print real-time HTTP server access logs to terminal stdout."""
        now = time.strftime("%H:%M:%S")
        client = self.client_address[0] if hasattr(self, "client_address") else "127.0.0.1"
        msg = format % args

        # Colorize output
        if any(code in msg for code in (" 200 ", " 204 ", " 304 ")):
            color = "\033[92m"  # Green
        elif any(code in msg for code in (" 400 ", " 404 ")):
            color = "\033[93m"  # Yellow
        elif any(code in msg for code in (" 500 ", " 502 ", " 503 ")):
            color = "\033[91m"  # Red
        else:
            color = "\033[96m"  # Cyan

        reset = "\033[0m"
        dim = "\033[90m"
        print(f" {dim}[{now}]{reset} [{client}] {color}{msg}{reset}", flush=True)

    def _send_json(self, data: Any, status_code: int = 200) -> None:
        """Send JSON HTTP response."""
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(payload)

    def _send_error(self, message: str, status_code: int = 400) -> None:
        """Send standardized JSON error response."""
        self._send_json({"success": False, "error": message}, status_code=status_code)

    def _read_json_body(self) -> Dict[str, Any]:
        """Read and parse JSON request body."""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self) -> None:
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        """Handle GET requests for pages, assets, and REST API."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query_params = urllib.parse.parse_qs(parsed_url.query)

        # 1. REST API Routing
        if path.startswith("/api/"):
            self._handle_api_get(path, query_params)
            return

        # 2. Main HTML Page
        if path in ("/", "/index.html"):
            index_path = TEMPLATES_DIR / "index.html"
            if index_path.exists():
                self._serve_file(index_path, "text/html; charset=utf-8")
                return
            else:
                self._send_error("Template index.html not found", 404)
                return

        # 3. Favicon shortcut
        if path == "/favicon.ico":
            fav_path = STATIC_DIR / "img" / "favicon.svg"
            if fav_path.exists():
                self._serve_file(fav_path, "image/svg+xml")
                return

        # 4. Static Assets (/static/*)
        if path.startswith("/static/"):
            rel_path = path[len("/static/"):]
            file_path = STATIC_DIR / rel_path
            if file_path.exists() and file_path.is_file():
                mime_type, _ = mimetypes.guess_type(str(file_path))
                if not mime_type:
                    if file_path.suffix == ".css":
                        mime_type = "text/css"
                    elif file_path.suffix == ".js":
                        mime_type = "application/javascript"
                    elif file_path.suffix == ".svg":
                        mime_type = "image/svg+xml"
                    else:
                        mime_type = "application/octet-stream"
                self._serve_file(file_path, mime_type)
                return

        self._send_error(f"Path not found: {path}", 404)

    def do_POST(self) -> None:
        """Handle POST requests for mutations and actions."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        payload = self._read_json_body()

        if path.startswith("/api/"):
            self._handle_api_post(path, payload)
            return

        self._send_error(f"Unknown POST path: {path}", 404)

    def _serve_file(self, file_path: Path, content_type: str) -> None:
        """Serve a static file with correct content type."""
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            if "html" not in content_type:
                # Cache static assets for 1 hour
                self.send_header("Cache-Control", "public, max-age=3600")
            else:
                self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            logger.error(f"Error serving {file_path}: {e}")
            self._send_error(f"Could not read file: {e}", 500)

    def _handle_api_get(self, path: str, query_params: Dict[str, list]) -> None:
        """Dispatch API GET requests."""
        try:
            if path == "/api/status":
                self._send_json(ApiHandler.get_status())
            elif path == "/api/presets":
                self._send_json(ApiHandler.get_presets(query_params))
            elif path.startswith("/api/presets/"):
                preset_name = urllib.parse.unquote(path[len("/api/presets/"):])
                detail = ApiHandler.get_preset_detail(preset_name)
                if detail:
                    self._send_json(detail)
                else:
                    self._send_error(f"Preset '{preset_name}' not found", 404)
            elif path == "/api/irs":
                self._send_json(ApiHandler.get_irs(query_params))
            elif path.startswith("/api/irs/"):
                irs_name = urllib.parse.unquote(path[len("/api/irs/"):])
                detail = ApiHandler.get_irs_detail(irs_name)
                if detail:
                    self._send_json(detail)
                else:
                    self._send_error(f"IRS file '{irs_name}' not found", 404)
            elif path == "/api/audio-stack":
                self._send_json(ApiHandler.get_audio_stack())
            elif path == "/api/updates":
                self._send_json(ApiHandler.get_updates())
            elif path == "/api/guide/irs":
                self._send_json(ApiHandler.get_irs_guide())
            else:
                self._send_error(f"Unknown API endpoint: {path}", 404)
        except Exception as e:
            logger.exception(f"Error handling GET {path}: {e}")
            self._send_error(f"Internal API error: {str(e)}", 500)

    def _handle_api_post(self, path: str, payload: Dict[str, Any]) -> None:
        """Dispatch API POST requests."""
        try:
            if path == "/api/presets/install":
                res = ApiHandler.install_presets(payload)
                self._send_json(res, status_code=200 if res.get("success") else 400)
            elif path == "/api/presets/remove":
                res = ApiHandler.remove_presets(payload)
                self._send_json(res, status_code=200 if res.get("success") else 400)
            elif path == "/api/presets/source":
                res = ApiHandler.set_preset_source(payload)
                self._send_json(res, status_code=200 if res.get("success") else 400)
            elif path == "/api/irs/install":
                res = ApiHandler.install_irs(payload)
                self._send_json(res, status_code=200 if res.get("success") else 400)
            elif path == "/api/irs/remove":
                res = ApiHandler.remove_irs(payload)
                self._send_json(res, status_code=200 if res.get("success") else 400)
            elif path == "/api/audio-stack/install":
                res = ApiHandler.install_audio_stack(payload)
                self._send_json(res, status_code=200 if res.get("success") else 400)
            elif path == "/api/updates/upgrade":
                res = ApiHandler.perform_upgrade()
                self._send_json(res, status_code=200 if res.get("success") else 400)
            elif path == "/api/server/shutdown":
                self._send_json({"success": True, "message": "Server shutting down..."})
                if self.server_instance:
                    threading.Thread(target=self.server_instance.stop, daemon=True).start()
            else:
                self._send_error(f"Unknown POST endpoint: {path}", 404)
        except Exception as e:
            logger.exception(f"Error handling POST {path}: {e}")
            self._send_error(f"Internal API error: {str(e)}", 500)


class PulsewireServer:
    """Multi-threaded HTTP Server for ProjectPulsewire."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self._server: Optional[http.server.ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False

    @property
    def url(self) -> str:
        display_host = "127.0.0.1" if self.host in ("0.0.0.0", "") else self.host
        return f"http://{display_host}:{self.port}"

    def start(self, block: bool = True) -> None:
        """Start the web server."""
        PulsewireRequestHandler.server_instance = self
        self._server = http.server.ThreadingHTTPServer((self.host, self.port), PulsewireRequestHandler)
        self._running = True

        if block:
            try:
                self._server.serve_forever()
            except (KeyboardInterrupt, SystemExit):
                self.stop()
        else:
            self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Gracefully stop the server."""
        if self._server and self._running:
            self._running = False
            # Call shutdown in background to avoid deadlock
            threading.Thread(target=self._server.shutdown, daemon=True).start()
            self._server.server_close()


def start_server(host: str = "0.0.0.0", port: int = 8080, open_browser: bool = True) -> Tuple[PulsewireServer, int]:
    """
    Launch the web server with automatic port resolution and optional browser launch.
    """
    actual_port = find_available_port(start_port=port, host=host)
    server = PulsewireServer(host=host, port=actual_port)

    if open_browser:
        def _open():
            time.sleep(0.3)
            webbrowser.open(server.url)
        threading.Thread(target=_open, daemon=True).start()

    return server, actual_port
