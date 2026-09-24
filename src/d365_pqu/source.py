from __future__ import annotations

import hashlib
import re
import subprocess
import urllib.request
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.error import HTTPError, URLError

from d365_pqu.config import (
    MAX_SOURCE_BYTES,
    SOURCE_ARTICLE_URL,
    SOURCE_BRANCH,
    SOURCE_BRANCH_URL,
    SOURCE_FILE_PATH,
    SOURCE_RAW_TEMPLATE,
    SOURCE_REPO,
    SOURCE_REPO_URL,
)
from d365_pqu.errors import SourceFetchError
from d365_pqu.models import SourceDocument

_FRONT_MATTER_DATE = re.compile(r"^ms\.date:\s*(\d{2})/(\d{2})/(\d{4})\s*$", re.MULTILINE)


class CommandRunner(Protocol):
    def __call__(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
        timeout: float,
    ) -> Any: ...


class UrlOpen(Protocol):
    def __call__(self, request: urllib.request.Request, timeout: float) -> Any: ...


def default_runner(
    args: list[str],
    *,
    capture_output: bool,
    text: bool,
    check: bool,
    timeout: float,
) -> Any:
    return subprocess.run(
        args,
        capture_output=capture_output,
        text=text,
        check=check,
        timeout=timeout,
    )


def default_opener(request: urllib.request.Request, timeout: float) -> Any:
    return urllib.request.urlopen(request, timeout=timeout)


def resolve_source_commit(
    repo: str = SOURCE_REPO,
    branch: str = SOURCE_BRANCH,
    runner: CommandRunner = default_runner,
    timeout: float = 60.0,
) -> str:
    url = f"https://github.com/{repo}.git"
    try:
        result = runner(
            ["git", "ls-remote", url, f"refs/heads/{branch}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SourceFetchError(f"Could not resolve {repo}@{branch}: {exc}") from exc
    output = (result.stdout or "").strip()
    if not output:
        raise SourceFetchError(f"No commit found for {repo}@{branch}")
    commit = output.split()[0].strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise SourceFetchError(f"Unexpected source commit value: {commit!r}")
    return commit


def _read_response(response: Any) -> bytes:
    if hasattr(response, "__enter__"):
        with response as handle:
            return _read_limited(handle)
    return _read_limited(response)


def _read_limited(handle: Any) -> bytes:
    body = handle.read(MAX_SOURCE_BYTES + 1)
    if not isinstance(body, bytes):
        raise SourceFetchError("Source response was not bytes")
    if len(body) > MAX_SOURCE_BYTES:
        raise SourceFetchError(f"Source exceeded {MAX_SOURCE_BYTES} bytes")
    return body


def raw_url_for_commit(
    commit: str,
    *,
    repo: str = SOURCE_REPO,
    file_path: str = SOURCE_FILE_PATH,
) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{commit}/{file_path}"


def fetch_markdown(
    commit: str,
    opener: UrlOpen = default_opener,
    timeout: float = 60.0,
    *,
    repo: str = SOURCE_REPO,
    file_path: str = SOURCE_FILE_PATH,
) -> tuple[str, str]:
    raw_url = raw_url_for_commit(commit, repo=repo, file_path=file_path)
    request = urllib.request.Request(
        raw_url,
        headers={
            "User-Agent": "d365-pqu-data/1.0 (+https://github.com/0x8e8fb-p/d365-pqu-data)",
            "Accept": "text/plain, text/markdown, */*",
        },
    )
    try:
        body = _read_response(opener(request, timeout))
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise SourceFetchError(f"Could not download {raw_url}: {exc}") from exc
    try:
        markdown = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SourceFetchError("Source was not valid UTF-8") from exc
    if not markdown.strip():
        raise SourceFetchError("Source was empty")
    return markdown, raw_url


def parse_markdown_date(markdown: str) -> str | None:
    match = _FRONT_MATTER_DATE.search(markdown)
    if not match:
        return None
    month, day, year = (int(part) for part in match.groups())
    try:
        return datetime(year, month, day, tzinfo=UTC).date().isoformat()
    except ValueError:
        return None


def fetch_source(
    *,
    runner: CommandRunner = default_runner,
    opener: UrlOpen = default_opener,
    now: datetime | None = None,
    repo: str = SOURCE_REPO,
    branch: str = SOURCE_BRANCH,
    file_path: str = SOURCE_FILE_PATH,
) -> SourceDocument:
    retrieved_at = now or datetime.now(UTC)
    if retrieved_at.tzinfo is None:
        retrieved_at = retrieved_at.replace(tzinfo=UTC)
    commit = resolve_source_commit(repo=repo, branch=branch, runner=runner)
    markdown, raw_url = fetch_markdown(
        commit,
        opener=opener,
        repo=repo,
        file_path=file_path,
    )
    sha256 = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    warnings: list[str] = []
    markdown_date = parse_markdown_date(markdown)
    if markdown_date is None:
        warnings.append("Source front matter did not contain a valid ms.date value.")
    return SourceDocument(
        markdown=markdown,
        source_commit=commit,
        article_url=SOURCE_ARTICLE_URL,
        raw_url=raw_url,
        markdown_date=markdown_date,
        retrieved_at=retrieved_at,
        sha256=sha256,
        warnings=tuple(warnings),
    )


def source_links() -> dict[str, str]:
    return {
        "article_url": SOURCE_ARTICLE_URL,
        "raw_url": SOURCE_RAW_TEMPLATE.format(commit=SOURCE_BRANCH),
        "repository": SOURCE_REPO,
        "repository_url": SOURCE_REPO_URL,
        "branch_url": SOURCE_BRANCH_URL,
        "file_path": SOURCE_FILE_PATH,
    }
