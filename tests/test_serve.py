from __future__ import annotations

import urllib.request
from pathlib import Path

import pytest

from d365_pqu.cli import build_parser
from d365_pqu.errors import PublishError
from d365_pqu.serve import LOOPBACK_HOST, create_server, serve_in_background


def _site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    (site / "calendar").mkdir(parents=True)
    (site / "index.html").write_text("<!DOCTYPE html><title>ok</title>", encoding="utf-8")
    (site / "calendar" / "station-1.ics").write_text("BEGIN:VCALENDAR\r\n", encoding="utf-8")
    return site


def test_server_binds_loopback_only(tmp_path: Path) -> None:
    server = create_server(_site(tmp_path), 0, quiet=True)
    try:
        assert server.server_address[0] == LOOPBACK_HOST == "127.0.0.1"
    finally:
        server.server_close()


def test_server_serves_site_with_explicit_mime_types(tmp_path: Path) -> None:
    with serve_in_background(_site(tmp_path)) as base:
        assert base.startswith("http://127.0.0.1:")
        with urllib.request.urlopen(base, timeout=10) as response:
            assert response.status == 200
            assert response.headers["Cache-Control"] == "no-store"
            assert b"<title>ok</title>" in response.read()
        with urllib.request.urlopen(base + "calendar/station-1.ics", timeout=10) as response:
            assert response.headers["Content-Type"].startswith("text/calendar")


def test_server_requires_built_site(tmp_path: Path) -> None:
    with pytest.raises(PublishError, match="build-site"):
        create_server(tmp_path / "missing", 0)


def test_cli_exposes_serve_command() -> None:
    args = build_parser().parse_args(["serve", "--port", "8123"])
    assert args.command == "serve"
    assert args.port == 8123
