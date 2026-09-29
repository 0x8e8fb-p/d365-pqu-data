"""The page stays current while it is open: new data, the date, and clock-dependent states."""

from __future__ import annotations

from typing import Any

import pytest

from conftest import E2E_SYNC_AT, FIXTURES, LIVE_FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

MINIMAL = FIXTURES / "source-minimal.md"
UPDATED = FIXTURES / "source-updated.md"
UPDATED_AT = "2026-09-28T03:30:00Z"
REGION_KEY = "d365-pqu-region"


def _text(locator) -> str:
    return " ".join((locator.text_content() or "").split())


def _status(page) -> str:
    return _text(page.locator("#app-status"))


def _pqu5_status(page) -> str:
    row = page.locator(
        "#pqu-table tbody tr", has=page.locator("a.train-id", has_text="10.0.48-PQU-5")
    )
    return _text(row.locator(".status-cell .status"))


def _swap_api(page, old_base: str, new_base: str) -> dict[str, bool]:
    """Serve ``old_base``'s API documents from ``new_base`` once ``switch["on"]`` is set."""
    switch = {"on": False}

    def handler(route: Any) -> None:
        if not switch["on"]:
            route.continue_()
            return
        response = route.fetch(url=route.request.url.replace(old_base, new_base))
        route.fulfill(response=response)

    page.route(f"{old_base}api/**", handler)
    return switch


def test_new_data_is_loaded_in_place_while_the_page_stays_open(fixture_site, open_page) -> None:
    before = fixture_site((MINIMAL, E2E_SYNC_AT))
    after = fixture_site((MINIMAL, E2E_SYNC_AT), (UPDATED, UPDATED_AT))
    opened = open_page(before, "#/trains", clock="install")
    page = opened.page
    switch = _swap_api(page, before, after)
    assert _pqu5_status(page) == "In-Progress"

    search = page.locator("#search")
    search.click()
    search.press_sequentially("10.0.48")
    page.wait_for_function("() => location.hash === '#/trains?q=10.0.48'")
    page.evaluate("() => document.getElementById('search').setSelectionRange(3, 5)")

    # Nothing is fetched before a check interval has passed.
    page.clock.run_for("30:00")
    assert _status(page) == ""
    switch["on"] = True
    page.clock.run_for("31:00")
    page.wait_for_function("() => document.getElementById('app-status').textContent !== ''")
    assert _status(page) == "Updated with the data published 28 Sep 2026 · 09:00 IST."
    assert _pqu5_status(page) == "Completed"

    # The reader's place is kept: focus, typed text, selection and filters.
    assert page.evaluate("() => document.activeElement.id") == "search"
    assert search.input_value() == "10.0.48"
    assert page.evaluate(
        "() => [document.activeElement.selectionStart, document.activeElement.selectionEnd]"
    ) == [3, 5]
    assert page.evaluate("() => location.hash") == "#/trains?q=10.0.48"
    assert page.locator("#health-toggle").get_attribute("data-state") == "healthy"
    opened.assert_clean()


def test_a_check_without_new_data_changes_nothing(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((MINIMAL, E2E_SYNC_AT)), "#/trains", clock="install")
    page = opened.page
    requests: list[str] = []
    page.on("request", lambda request: requests.append(request.url))
    marker = page.evaluate(
        "() => { const row = document.querySelector('#pqu-table tbody tr'); row.dataset.marker = 'kept'; return true; }"
    )
    assert marker
    with page.expect_response("**/api/health.json"):
        page.clock.run_for("01:01:00")
    page.wait_for_timeout(200)
    fetched = sorted({url.rsplit("/", 1)[-1] for url in requests})
    assert fetched == ["health.json", "metadata.json"]
    # The table was not redrawn.
    assert page.locator("#pqu-table tbody tr[data-marker='kept']").count() == 1
    assert _status(page) == ""
    opened.assert_clean()


def test_midnight_recalculates_dates_and_keeps_open_answers(fixture_site, open_page) -> None:
    site = fixture_site((LIVE_FIXTURES, E2E_SYNC_AT))
    first = "faq-what-is-the-biweekly-cadence-for-pqu"
    second = "faq-why-is-the-rollout-schedule-changing-from-28-days-to-a-biweekly-cadence"
    # 23:59:30 in India on Monday 28 September.
    opened = open_page(site, "#/learn", clock="install", now="2026-09-28T18:29:30Z")
    page = opened.page
    page.locator(f"#{first} > summary").click()
    page.locator(f"#{second} > summary").click()
    page.wait_for_function(f"() => location.hash === '#/learn/faq/{second.removeprefix('faq-')}'")
    hash_before = page.evaluate("() => location.hash")

    page.clock.run_for("01:00")
    page.wait_for_function("() => document.getElementById('app-status').textContent !== ''")
    assert _status(page) == "Dates and countdowns recalculated for Tue 29 Sep 2026."
    assert page.locator(f"#{first}").get_attribute("open") is not None
    assert page.locator(f"#{second}").get_attribute("open") is not None
    # Reopening the first answer must not rewrite the address.
    page.wait_for_timeout(100)
    assert page.evaluate("() => location.hash") == hash_before
    assert page.evaluate("() => document.activeElement.parentElement.id") == second

    page.evaluate("() => { location.hash = '#/'; }")
    wait_for_render(page)
    assert page.locator("#overview-heading").text_content() == "Tuesday 29 September 2026"
    opened.assert_clean()


def test_dark_hours_turn_on_when_the_window_starts(fixture_site, open_page) -> None:
    site = fixture_site((LIVE_FIXTURES, E2E_SYNC_AT))
    # Europe's Friday window starts at 22:00 UTC.
    opened = open_page(
        site,
        "#/region/North%20Europe",
        clock="install",
        now="2026-10-02T21:59:30Z",
        storage={REGION_KEY: "North Europe"},
    )
    page = opened.page
    friday = page.locator("#window-list tr[data-pqu='10.0.48-PQU-6'] .dark-hours li").first
    assert "occ-upcoming" in (friday.get_attribute("class") or "")
    page.locator("#region-calendar-station-address").focus()

    page.clock.run_for("01:00")
    page.wait_for_function(
        "() => document.querySelector(\"#window-list tr[data-pqu='10.0.48-PQU-6'] .dark-hours li\").classList.contains('occ-now')"
    )
    assert "Now" in _text(friday)
    assert page.evaluate("() => document.activeElement.id") == "region-calendar-station-address"
    assert _status(page) == ""
    opened.assert_clean()


def test_the_health_pill_follows_the_clock(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((MINIMAL, E2E_SYNC_AT)), "#/trains", clock="install")
    page = opened.page
    assert page.locator("#health-toggle").get_attribute("data-state") == "healthy"
    assert page.locator("#sync-time").text_content() == "checked 1 h ago"
    page.locator("#health-toggle").click()
    page.locator("#health-panel a").first.focus()
    focused = page.evaluate("() => document.activeElement.textContent")

    # The last check was at 03:00 UTC; three missed hourly checks make the data stale.
    page.clock.run_for("02:01:00")
    page.wait_for_function(
        "() => document.getElementById('health-toggle').dataset.state === 'stale'"
    )
    assert page.locator("#sync-time").text_content() == "checked 3 h ago"
    assert page.evaluate("() => document.activeElement.textContent") == focused
    opened.assert_clean()


def test_a_placeholder_shows_while_a_view_loads(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((LIVE_FIXTURES, E2E_SYNC_AT)), "#/trains")
    page = opened.page
    held: list[Any] = []
    page.route("**/api/insights.json", lambda route: held.append(route))
    page.evaluate("() => { location.hash = '#/learn'; }")
    page.wait_for_selector("#view .skeleton")
    assert page.locator("#view").get_attribute("aria-busy") == "true"
    assert page.locator("#view .skeleton").get_attribute("aria-hidden") == "true"
    page.wait_for_function("() => true")
    assert held
    held[0].continue_()
    wait_for_render(page)
    assert page.locator("#view .skeleton").count() == 0
    assert page.locator("#view").get_attribute("aria-busy") is None
    assert page.locator("#learn-heading").is_visible()
    opened.assert_clean()
