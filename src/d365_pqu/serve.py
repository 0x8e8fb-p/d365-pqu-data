"""Local preview server for the generated static site.

The server binds to the loopback interface only. It is a development convenience with no
authentication, so it must never listen on a public interface.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from d365_pqu.errors import PublishError

LOOPBACK_HOST = "127.0.0.1"
MIME_TYPES = {
    ".ics": "text/calendar; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".xml": "application/atom+xml; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


class SiteRequestHandler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, **MIME_TYPES}  # noqa: RUF012
    quiet = False

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        if not self.quiet:
            super().log_message(format, *args)


class QuietSiteRequestHandler(SiteRequestHandler):
    quiet = True


def create_server(site_dir: Path, port: int = 8000, *, quiet: bool = False) -> ThreadingHTTPServer:
    """Create (but do not start) a loopback-only HTTP server for ``site_dir``."""
    site = Path(site_dir)
    if not (site / "index.html").is_file():
        raise PublishError(f"No built site found at {site}; run build-site first")
    handler_class = QuietSiteRequestHandler if quiet else SiteRequestHandler
    handler = partial(handler_class, directory=str(site))
    return ThreadingHTTPServer((LOOPBACK_HOST, port), handler)


@contextmanager
def serve_in_background(site_dir: Path) -> Iterator[str]:
    """Serve ``site_dir`` on an ephemeral loopback port and yield the base URL."""
    server = create_server(site_dir, 0, quiet=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = LOOPBACK_HOST, int(server.server_address[1])
    try:
        yield f"http://{host}:{port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
