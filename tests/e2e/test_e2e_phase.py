from __future__ import annotations

import pytest

from conftest import E2E_SYNC_AT, FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

MINIMAL = FIXTURES / "source-minimal.md"


def _status_text(page, pqu_id: str) -> str:
    row = page.locator("#pqu-table tbody tr", has_text=pqu_id).first
    return row.locator("td.status-cell").inner_text()


def test_phase_lines_follow_published_dates_in_ist(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((MINIMAL, E2E_SYNC_AT)), "#/trains")
    page = opened.page
    ended = _status_text(page, "10.0.48-PQU-5")
    assert "In-Progress" in ended
    assert "Scheduled end passed 2 days ago" in ended
    assert "Microsoft still lists this train as In-Progress (article updated 21 Sep 2026)." in ended
    running = _status_text(page, "10.0.48-PQU-6")
    assert "Day 13 of 25 · Now: Station 4 sandbox (28 Sep \u2013 1 Oct)" in running
    upcoming = _status_text(page, "10.0.48-PQU-7")
    assert "Due soon" in upcoming
    assert "Cutoff and start in 2 days · Wed 30 Sep" in upcoming
    canceled = _status_text(page, "10.0.47-PQU-2")
    assert canceled.strip() == "Canceled"
    note = page.locator("#calc-note").inner_text()
    assert "Mon 28 Sep 2026 (Asia/Kolkata)" in note
    caption = page.locator("#pqu-table caption").text_content() or ""
    assert "Mon 28 Sep 2026, in Asia/Kolkata" in caption
    opened.assert_clean()


def test_phase_lines_use_the_viewer_calendar_day(fixture_site, open_page) -> None:
    opened = open_page(
        fixture_site((MINIMAL, E2E_SYNC_AT)),
        "#/trains",
        zone="America/Los_Angeles",
        locale="en-US",
    )
    page = opened.page
    running = _status_text(page, "10.0.48-PQU-6")
    assert "Day 12 of 25 · Now: Stations 2 and 3 production (26\u201327 Sep)" in running
    ended = _status_text(page, "10.0.48-PQU-5")
    assert (
        "Scheduled end passed 1 day ago · Now: Stations 5 and 6 production (26\u201327 Sep)"
        in ended
    )
    assert "Microsoft still lists" not in ended
    assert "Sun 27 Sep 2026 (America/Los Angeles)" in page.locator("#calc-note").inner_text()
    opened.assert_clean()


def test_zone_choice_is_applied_and_survives_reload(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((MINIMAL, E2E_SYNC_AT)), "#/trains")
    page = opened.page
    select = page.locator("#zone-select")
    assert select.input_value() == "auto"
    assert page.locator("#zone-select option[value='UTC']").count() == 1
    assert page.locator("#zone-select optgroup[label='Europe'] option").count() > 20
    select.select_option("America/Los_Angeles")
    wait_for_render(page)
    assert "Day 12 of 25" in _status_text(page, "10.0.48-PQU-6")
    page.reload()
    page.wait_for_selector("body[data-ready='true']")
    assert page.locator("#zone-select").input_value() == "America/Los_Angeles"
    assert "Day 12 of 25" in _status_text(page, "10.0.48-PQU-6")
    page.locator("#zone-select").select_option("auto")
    wait_for_render(page)
    assert "Day 13 of 25" in _status_text(page, "10.0.48-PQU-6")
    page.locator("#health-toggle").click()
    assert "IST" in page.locator("#health-panel").inner_text()
    opened.assert_clean()


def test_search_matches_calculated_phase_text(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((MINIMAL, E2E_SYNC_AT)), "#/trains")
    page = opened.page
    page.locator("#search").fill("station 4 sandbox")
    rows = page.locator("#pqu-table tbody tr")
    assert rows.count() == 1
    assert "10.0.48-PQU-6" in rows.first.inner_text()
    page.locator("#search").fill("still lists")
    assert rows.count() == 1
    assert "10.0.48-PQU-5" in rows.first.inner_text()
    opened.assert_clean()
