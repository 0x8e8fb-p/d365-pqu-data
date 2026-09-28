from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError

import pytest

from conftest import FIXTURES, LIVE_FIXTURES
from d365_pqu.config import SCHEDULE_SPEC, SOURCE_SPECS
from d365_pqu.errors import SourceFetchError
from d365_pqu.source import (
    bundle_from_directory,
    fetch_bundle,
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


def _live_opener(fail: set[str] | None = None):
    requested: list[str] = []

    def opener(request, timeout):
        url = request.full_url
        requested.append(url)
        name = url.rsplit("/", 1)[-1]
        if name in (fail or set()):
            raise HTTPError(url, 503, "Service Unavailable", {}, None)
        return io.BytesIO((LIVE_FIXTURES / name).read_bytes())

    return opener, requested


def _runner(args, **kwargs):
    return _Result(f"{'c' * 40}\trefs/heads/main\n")


def test_fetch_bundle_reads_every_article_at_one_commit() -> None:
    opener, requested = _live_opener()
    bundle = fetch_bundle(runner=_runner, opener=opener, now=datetime(2026, 9, 28, tzinfo=UTC))
    assert bundle.commit == "c" * 40
    assert bundle.errors == {}
    assert set(bundle.documents) == {spec.key for spec in SOURCE_SPECS}
    assert len(requested) == len(SOURCE_SPECS)
    assert all(f"/{'c' * 40}/articles/" in url for url in requested)
    service = bundle.documents["service_updates"]
    assert service.key == "service_updates"
    assert service.file_path.endswith("get-started/public-preview-releases.md")
    assert service.article_url == (
        "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/"
        "public-preview-releases"
    )
    assert service.markdown_date == "2026-06-04"
    assert bundle.schedule.markdown_date == "2026-09-21"


def test_fetch_bundle_records_optional_failures_and_raises_for_required() -> None:
    opener, _ = _live_opener(fail={"public-preview-releases.md"})
    bundle = fetch_bundle(runner=_runner, opener=opener, now=datetime(2026, 9, 28, tzinfo=UTC))
    assert "service_updates" not in bundle.documents
    assert "503" in bundle.errors["service_updates"]
    opener, _ = _live_opener(fail={"quality-updates-schedule.md"})
    with pytest.raises(SourceFetchError, match="503"):
        fetch_bundle(runner=_runner, opener=opener, now=datetime(2026, 9, 28, tzinfo=UTC))


def test_bundle_from_directory_skips_missing_optional_articles(tmp_path: Path) -> None:
    (tmp_path / "quality-updates-schedule.md").write_bytes(
        (LIVE_FIXTURES / "quality-updates-schedule.md").read_bytes()
    )
    bundle = bundle_from_directory(tmp_path, commit="d" * 40)
    assert set(bundle.documents) == {"schedule"}
    assert bundle.errors == {}
    assert bundle.schedule.raw_url.endswith(f"/{'d' * 40}/{SCHEDULE_SPEC.file_path}")
    (tmp_path / "quality-updates-schedule.md").unlink()
    with pytest.raises(SourceFetchError, match="required"):
        bundle_from_directory(tmp_path, commit="d" * 40)
