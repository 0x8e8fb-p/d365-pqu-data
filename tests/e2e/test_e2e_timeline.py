from __future__ import annotations

import pytest

from conftest import E2E_SYNC_AT, LIVE_FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

IN_PROGRESS = [
    "10.0.46-PQU-8",
    "10.0.47-PQU-12",
    "10.0.47-PQU-13",
    "10.0.48-PQU-5",
    "10.0.48-PQU-6",
]


def _live(fixture_site) -> str:
    return fixture_site((LIVE_FIXTURES, E2E_SYNC_AT))


def _text(locator) -> str:
    return " ".join((locator.text_content() or "").split())


def _hash(page) -> str:
    return str(page.evaluate("location.hash"))


def _bars(page) -> list[str]:
    return [str(bar.get_attribute("data-pqu")) for bar in page.locator("#timeline a.tl-bar").all()]


def test_toggle_between_table_and_timeline(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains")
    page = opened.page
    assert page.locator("#display-table").get_attribute("aria-pressed") == "true"
    assert page.locator("#pqu-table").is_visible()
    assert not page.locator("#zoom").is_visible()

    page.locator("#display-timeline").click()
    page.wait_for_function("() => location.hash === '#/trains?view=timeline'")
    assert page.locator("#display-timeline").get_attribute("aria-pressed") == "true"
    assert page.evaluate("document.activeElement.id") == "display-timeline"
    assert page.locator("#timeline").is_visible()
    assert page.locator("#pqu-table").count() == 0
    assert page.locator("#zoom").is_visible()
    assert not page.locator("#page-size").is_visible()
    assert not page.locator("#calc-note").is_visible()
    assert page.title() == "PQU train timeline · D365 PQU Tracker"
    assert _text(page.locator("#filter-note")) == "59 of 59 trains match · 23 on the timeline"

    page.locator("#display-table").click()
    page.wait_for_function("() => location.hash === '#/trains'")
    assert page.locator("#pqu-table").is_visible()
    assert page.locator("#page-size").is_visible()
    assert page.title() == "PQU trains · D365 PQU Tracker"
    opened.assert_clean()


def test_timeline_lanes_bars_and_today_line(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains?view=timeline")
    page = opened.page
    assert page.title() == "PQU train timeline · D365 PQU Tracker"
    assert _text(page.locator("#timeline-range")) == "29 Aug \u2013 28 Nov 2026"
    lanes = page.locator("#timeline .tl-lane")
    assert [lane.get_attribute("data-version") for lane in lanes.all()] == [
        "10.0.46",
        "10.0.47",
        "10.0.48",
        "10.0.49",
    ]
    # Today (28 Sep) sits in the middle of day 31 of the 92-day range.
    today = float(
        page.locator("#timeline .tl-today").evaluate("el => el.style.getPropertyValue('--f')")
    )
    assert abs(today - 30.5 / 92) < 1e-9

    bar = page.locator("#timeline a.tl-bar[data-pqu='10.0.48-PQU-6']")
    assert bar.get_attribute("href") == "#/train/10.0.48-PQU-6"
    assert "status-in-progress" in (bar.get_attribute("class") or "")
    assert bar.get_attribute("aria-label") == (
        "10.0.48 PQU-6, In-Progress, 16 Sep \u2013 10 Oct 2026, Day 13 of 25 (calculated)"
    )
    early = page.locator("#timeline a.tl-bar[data-pqu='10.0.46-PQU-8']")
    assert early.get_attribute("aria-label") == (
        "10.0.46 PQU-8, In-Progress, 31 Aug \u2013 3 Oct 2026, change cutoff 21 Aug 2026, "
        "Day 29 of 34 (calculated)"
    )
    lane = page.locator("#timeline .tl-lane[data-version='10.0.48'] ul.tl-bars")
    assert lane.get_attribute("aria-labelledby") == "tl-lane-10-0-48"
    assert page.locator("#tl-lane-10-0-48").text_content() == "10.0.48"
    assert page.locator("#timeline .tl-cutoff").count() > 0

    legend = [_text(item) for item in page.locator("#timeline .tl-legend li").all()]
    assert legend == ["In-Progress", "Not Started", "Completed", "Change cutoff", "Today"]
    assert _text(page.locator("#timeline-outside")) == (
        "35 matching trains fall outside this range. Show all dates"
    )
    not_drawn = page.locator(".tl-not-drawn[data-pqu='10.0.46-PQU-1']")
    assert _text(not_drawn) == (
        "Not drawn: 10.0.46 PQU-1. Microsoft lists the start as 9 Feb 2025 and the "
        "change cutoff as 4 Feb 2026; the years differ."
    )
    assert page.locator("#timeline a.tl-bar[data-pqu='10.0.46-PQU-1']").count() == 0
    assert "calculated for Mon 28 Sep 2026 (Asia/Kolkata)" in _text(
        page.locator("#timeline-calc-note")
    )
    opened.assert_clean()


def test_filters_apply_to_the_timeline(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains?view=timeline&status=In-Progress")
    page = opened.page
    assert sorted(_bars(page)) == IN_PROGRESS
    assert _text(page.locator("#filter-note")) == "5 of 59 trains match · 5 on the timeline"
    assert page.locator(".tl-not-drawn").count() == 0

    page.locator("#version-filter").select_option("10.0.48")
    page.wait_for_function("() => location.hash.includes('version=10.0.48')")
    assert _hash(page) == "#/trains?status=In-Progress&version=10.0.48&view=timeline"
    assert _bars(page) == ["10.0.48-PQU-5", "10.0.48-PQU-6"]
    assert [lane.get_attribute("data-version") for lane in page.locator(".tl-lane").all()] == [
        "10.0.48"
    ]

    page.locator("#search").fill("no such train")
    page.wait_for_function("() => location.hash.includes('q=no')")
    assert _text(page.locator("#timeline-empty")) == "No trains match these filters."

    page.locator("#reset-filters").click()
    page.wait_for_function("() => location.hash === '#/trains?view=timeline'")
    wait_for_render(page)
    assert page.locator("#display-timeline").get_attribute("aria-pressed") == "true"
    assert len(_bars(page)) == 23
    opened.assert_clean()


def test_zoom_changes_the_range(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains?view=timeline")
    page = opened.page
    page.locator("#zoom-6m").click()
    page.wait_for_function("() => location.hash === '#/trains?view=timeline&zoom=6m'")
    assert page.locator("#zoom-6m").get_attribute("aria-pressed") == "true"
    assert _text(page.locator("#timeline-range")) == "29 Jul 2026 \u2013 28 Jan 2027"
    assert _text(page.locator("#filter-note")) == "59 of 59 trains match · 37 on the timeline"
    january = page.locator("#timeline .tl-month-label", has_text="Jan")
    assert _text(january) == "Jan 2027"

    page.locator("#timeline-show-all").click()
    page.wait_for_function("() => location.hash === '#/trains?view=timeline&zoom=all'")
    assert page.evaluate("document.activeElement.id") == "zoom-all"
    assert _text(page.locator("#timeline-range")) == "4 Mar 2026 \u2013 19 Jun 2027"
    assert len(_bars(page)) == 58
    assert page.locator("#timeline-outside").count() == 0
    canceled = page.locator("#timeline a.tl-bar[data-pqu='10.0.47-PQU-2']")
    assert "status-canceled" in (canceled.get_attribute("class") or "")
    assert "Canceled" in _text(page.locator("#timeline .tl-legend"))
    opened.assert_clean()


def test_keyboard_reaches_bars_and_opens_the_train(fixture_site, open_page) -> None:
    route = "#/trains?status=In-Progress&version=10.0.48&view=timeline"
    opened = open_page(_live(fixture_site), route)
    page = opened.page
    page.locator("#zoom-all").focus()
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.dataset.pqu") == "10.0.48-PQU-5"
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.dataset.pqu") == "10.0.48-PQU-6"
    outline = page.evaluate("getComputedStyle(document.activeElement).outlineStyle")
    assert outline == "solid"
    page.keyboard.press("Enter")
    page.wait_for_function("() => location.hash === '#/train/10.0.48-PQU-6'")
    wait_for_render(page)
    assert page.locator("#train-heading").text_content() == "10.0.48 PQU-6"
    assert page.locator(".crumbs a").get_attribute("href") == route

    page.go_back()
    page.wait_for_function(f"() => location.hash === '{route}'")
    wait_for_render(page)
    assert page.locator("#timeline").is_visible()
    assert _bars(page) == ["10.0.48-PQU-5", "10.0.48-PQU-6"]
    opened.assert_clean()
