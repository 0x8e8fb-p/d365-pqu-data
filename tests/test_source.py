from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import FIXTURES
from d365_pqu.errors import SourceFetchError
from d365_pqu.source import (
    fetch_markdown,
    parse_markdown_date,
    resolve_source_commit,
)


class _Result:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


def test_resolve_source_commit_reads_ls_remote() -> None:
    commit = "a" * 40

    def runner(args, **kwargs):
        assert args[:2] == ["git", "ls-remote"]
        assert kwargs["check"] is True
        return _Result(f"{commit}\trefs/heads/main\n")

    assert resolve_source_commit(runner=runner) == commit


def test_resolve_source_commit_rejects_bad_output() -> None:
    def runner(args, **kwargs):
        return _Result("not-a-commit\trefs/heads/main\n")

    with pytest.raises(SourceFetchError):
        resolve_source_commit(runner=runner)


def test_fetch_markdown_decodes_utf8() -> None:
    def opener(request, timeout):
        return io.BytesIO(b"# hello\n")

    markdown, url = fetch_markdown("b" * 40, opener=opener)
    assert markdown.startswith("# hello")
    assert "b" * 40 in url


def test_fetch_markdown_rejects_empty_response() -> None:
    def opener(request, timeout):
        return io.BytesIO(b"")

    with pytest.raises(SourceFetchError):
        fetch_markdown("b" * 40, opener=opener)


def test_fetch_markdown_rejects_oversized_response() -> None:
    def opener(request, timeout):
        return io.BytesIO(b"x" * (6 * 1024 * 1024))

    with pytest.raises(SourceFetchError):
        fetch_markdown("b" * 40, opener=opener)


def test_parse_markdown_date() -> None:
    markdown = (FIXTURES / "source-minimal.md").read_text(encoding="utf-8")
    assert parse_markdown_date(markdown) == "2026-09-21"
    assert parse_markdown_date("no front matter") is None
    assert parse_markdown_date("ms.date: 13/45/2026") is None


def test_fetch_source_uses_injected_transport() -> None:
    from d365_pqu.source import fetch_source

    markdown = (FIXTURES / "source-minimal.md").read_text(encoding="utf-8")

    def runner(args, **kwargs):
        return _Result(f"{'c' * 40}\trefs/heads/main\n")

    def opener(request, timeout):
        return io.BytesIO(markdown.encode())

    document = fetch_source(
        runner=runner,
        opener=opener,
        now=datetime(2026, 9, 24, tzinfo=UTC),
    )
    assert document.source_commit == "c" * 40
    assert document.markdown_date == "2026-09-21"
    assert len(document.sha256) == 64
    assert Path(__file__).exists()
