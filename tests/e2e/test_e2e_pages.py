"""The site as GitHub Pages serves it: under /d365-pqu-data/ on an https origin, with 404.html
returned for any missing path. Requests are answered from the built site, not the network."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

from conftest import E2E_NOW, E2E_SYNC_AT, LIVE_FIXTURES, build_fixture_site, parse_instant
from d365_pqu.config import PAGES_BASE_URL

pytestmark = pytest.mark.e2e

RECORD_CSP = (
    "window.__csp = [];"
    "document.addEventListener('securitypolicyviolation', (event) => "
    "window.__csp.push(`${event.violatedDirective} ${event.blockedURI}`));"
)


@pytest.fixture(scope="module")
def pages_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_fixture_site(tmp_path_factory.mktemp("pages"), [(LIVE_FIXTURES, E2E_SYNC_AT)])


@pytest.fixture
def pages_page(e2e_browser: Any, pages_site: Path) -> Iterator[tuple[Any, list[str], list[str]]]:
    parsed = urlparse(PAGES_BASE_URL)
    prefix = parsed.path.rstrip("/")
    context = e2e_browser.new_context(timezone_id="Asia/Kolkata", locale="en-IN")
    context.add_init_script(RECORD_CSP)

    def handler(route: Any) -> None:
        path = urlparse(route.request.url).path
        relative = path.removeprefix(prefix).lstrip("/") if path.startswith(prefix) else None
        target = pages_site / relative if relative is not None else None
        if target is not None and (relative == "" or path.endswith("/")):
            target = target / "index.html"
        if target is not None and target.is_file():
            route.fulfill(status=200, path=str(target))
        else:
            route.fulfill(status=404, path=str(pages_site / "404.html"))

    context.route(f"{parsed.scheme}://{parsed.netloc}/**", handler)
    page = context.new_page()
    page.clock.set_fixed_time(parse_instant(E2E_NOW))
    errors: list[str] = []
    failed: list[str] = []
    page.on(
        "console", lambda message: errors.append(message.text) if message.type == "error" else None
    )
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on(
        "response", lambda response: failed.append(response.url) if response.status >= 400 else None
    )
    yield page, errors, failed
    context.close()


# Chromium logs every error response, including the 404 status of the not-found page itself.
NOT_FOUND_LOG = "Failed to load resource: the server responded with a status of 404 (Not Found)"


def test_a_missing_path_shows_the_styled_404_page(
    pages_page: tuple[Any, list[str], list[str]],
) -> None:
    page, errors, failed = pages_page
    missing = f"{PAGES_BASE_URL}/train/10.0.48-PQU-6/details"
    response = page.goto(missing)
    assert response is not None and response.status == 404
    # Only the page itself is missing; its stylesheet and icon load from the site root.
    assert failed == [missing]
    assert errors == [NOT_FOUND_LOG]
    errors.clear()
    assert page.title() == "Page not found · D365 PQU Tracker"
    assert page.locator("h1").text_content() == "Page not found"
    # The stylesheet loaded from the site root even at a nested path; the system theme is light.
    background = page.evaluate("() => getComputedStyle(document.body).backgroundColor")
    assert background == "rgb(251, 251, 249)"
    assert page.evaluate("() => document.documentElement.dataset.theme") == "light"
    links = {
        str(link.text_content()): str(link.get_attribute("href"))
        for link in page.locator(".not-found-links a").all()
    }
    assert links == {
        "Open the dashboard": "/d365-pqu-data/",
        "PQU trains": "/d365-pqu-data/#/trains",
        "Data & API": "/d365-pqu-data/#/data",
    }
    assert page.evaluate("() => window.__csp") == []

    page.get_by_role("link", name="PQU trains").click()
    page.wait_for_selector("body[data-ready='true']")
    assert page.url == f"{PAGES_BASE_URL}/#/trains"
    assert page.locator("#pqu-table tbody tr").count() == 20
    assert page.evaluate("() => window.__csp") == []
    assert errors == []


def test_the_404_page_follows_the_saved_theme(pages_page: tuple[Any, list[str], list[str]]) -> None:
    page, errors, failed = pages_page
    page.add_init_script("window.localStorage.setItem('d365-pqu-theme', 'dark')")
    page.goto(f"{PAGES_BASE_URL}/nothing-here")
    assert page.evaluate("() => document.documentElement.dataset.theme") == "dark"
    assert page.evaluate("() => getComputedStyle(document.body).backgroundColor") == (
        "rgb(22, 22, 20)"
    )
    assert failed == [f"{PAGES_BASE_URL}/nothing-here"]
    assert errors == [NOT_FOUND_LOG]


def test_every_view_runs_under_the_published_address_without_csp_violations(
    pages_page: tuple[Any, list[str], list[str]],
) -> None:
    page, errors, failed = pages_page
    page.goto(f"{PAGES_BASE_URL}/")
    page.wait_for_selector("body[data-ready='true']")
    routes = [
        "#/region/North%20Europe",
        "#/trains?view=timeline&zoom=all",
        "#/train/10.0.48-PQU-6",
        "#/versions?build=10.0.2527.160",
        "#/learn",
        "#/changes",
        "#/data",
    ]
    for route in routes:
        page.evaluate(f"() => {{ location.hash = '{route}'; }}")
        page.wait_for_function(
            "() => document.getElementById('view').dataset.renderedHash === location.hash"
        )
    page.locator("#health-toggle").click()
    assert page.locator("#health-panel").is_visible()
    assert page.evaluate("() => window.__csp") == []
    assert failed == []
    assert errors == []
