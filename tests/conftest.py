from __future__ import annotations

import contextlib
import hashlib
import os
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
LIVE_FIXTURES = FIXTURES / "live"
SCHEMA_DIR = REPO_ROOT / "schema"

# Default browser clock for e2e tests: Monday 28 Sep 2026, 09:30 IST.
E2E_NOW = "2026-09-28T04:00:00Z"
E2E_SYNC_AT = "2026-09-28T03:00:00Z"


def parse_instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def fixture_commit(index: int) -> str:
    return hashlib.sha1(f"fixture-step-{index}".encode()).hexdigest()


Step = tuple[Path, str] | tuple[Path, str, str]


def build_fixture_site(root: Path, steps: Sequence[Step]) -> Path:
    """Run one sync per (source, instant[, "fail"]) step into ``root``, then build the site.

    ``source`` is a schedule Markdown file or a directory holding source articles by file name.
    A step marked ``"fail"`` must raise a pipeline error; its failed check is still recorded.
    """
    from d365_pqu.config import Paths
    from d365_pqu.errors import PquError
    from d365_pqu.pipeline import build_site, run_fixture_sync

    paths = Paths(
        root=root,
        data_dir=root / "data",
        excel_dir=root / "excel",
        schema_dir=SCHEMA_DIR,
        site_dir=root / "build" / "site",
        tests_dir=root / "tests",
    )
    for index, step in enumerate(steps):
        source, instant = step[0], step[1]
        expect_failure = len(step) > 2 and step[2] == "fail"
        try:
            run_fixture_sync(
                paths, source, commit=fixture_commit(index), now=parse_instant(instant)
            )
        except PquError:
            if not expect_failure:
                raise
        else:
            assert not expect_failure, f"step {index} ({source.name}) was expected to fail"
    build_site(paths)
    return paths.site_dir


@pytest.fixture(scope="session")
def fixture_site(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Callable[..., str]]:
    """Build (once per session) and serve a site; returns the loopback base URL."""
    from d365_pqu.serve import serve_in_background

    cache: dict[tuple[tuple[str, ...], ...], str] = {}
    stack = contextlib.ExitStack()

    def _site(*steps: Step) -> str:
        key = tuple(tuple(str(part) for part in step) for step in steps)
        if key not in cache:
            site = build_fixture_site(tmp_path_factory.mktemp("site"), steps)
            cache[key] = stack.enter_context(serve_in_background(site))
        return cache[key]

    yield _site
    stack.close()


@pytest.fixture(scope="session")
def e2e_browser() -> Iterator[Any]:
    required = os.environ.get("REQUIRE_E2E") == "1"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        if required:
            pytest.fail("REQUIRE_E2E=1 but Playwright is not installed")
        pytest.skip("Playwright is not installed")
    manager = sync_playwright().start()
    try:
        browser = manager.chromium.launch()
    except Exception as exc:
        manager.stop()
        if required:
            pytest.fail(f"REQUIRE_E2E=1 but Chromium could not start: {exc}")
        pytest.skip(f"Playwright Chromium is not installed: {exc}")
    yield browser
    browser.close()
    manager.stop()


@dataclass
class OpenedPage:
    page: Any
    errors: list[str] = field(default_factory=list)

    def assert_clean(self) -> None:
        assert self.errors == [], self.errors


def _responder(status: int) -> Callable[[Any, Any], None]:
    def handler(route: Any, request: Any) -> None:
        route.fulfill(status=status, body="")

    return handler


def wait_for_render(page: Any) -> None:
    """Wait until the view has rendered the current location hash."""
    page.wait_for_function(
        "() => document.getElementById('view').dataset.renderedHash === location.hash",
        timeout=10000,
    )


@pytest.fixture
def open_page(e2e_browser: Any) -> Iterator[Callable[..., OpenedPage]]:
    contexts: list[Any] = []

    def _open(
        base_url: str,
        route: str = "",
        *,
        zone: str = "Asia/Kolkata",
        now: str = E2E_NOW,
        locale: str = "en-IN",
        storage: dict[str, str] | None = None,
        width: int = 1360,
        routes: dict[str, int] | None = None,
        clock: str = "fixed",
        wait: bool = True,
        init_script: str | None = None,
    ) -> OpenedPage:
        context = e2e_browser.new_context(
            timezone_id=zone, locale=locale, viewport={"width": width, "height": 900}
        )
        contexts.append(context)
        if init_script:
            context.add_init_script(init_script)
        if storage:
            script = "".join(
                f"window.localStorage.setItem({key!r}, {value!r});"
                for key, value in storage.items()
            )
            context.add_init_script(f"try {{ {script} }} catch (error) {{}}")
        page = context.new_page()
        opened = OpenedPage(page)
        page.on("pageerror", lambda error: opened.errors.append(f"pageerror: {error}"))
        page.on(
            "console",
            lambda message: (
                opened.errors.append(f"console: {message.text}")
                if message.type == "error"
                else None
            ),
        )
        for pattern, status in (routes or {}).items():
            page.route(pattern, _responder(status))
        if clock == "install":
            page.clock.install(time=parse_instant(now))
        else:
            page.clock.set_fixed_time(parse_instant(now))
        page.goto(base_url + route)
        if wait:
            page.wait_for_selector("body[data-ready='true']", timeout=15000)
        return opened

    yield _open
    for context in contexts:
        context.close()
