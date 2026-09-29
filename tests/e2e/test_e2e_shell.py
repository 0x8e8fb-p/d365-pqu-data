from __future__ import annotations

import pytest

from conftest import E2E_SYNC_AT, FIXTURES, LIVE_FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

MINIMAL = FIXTURES / "source-minimal.md"
TAB_ORDER = ["Overview", "My region", "Trains", "Versions", "Learn", "Changes"]


def _live(fixture_site) -> str:
    return fixture_site((LIVE_FIXTURES, E2E_SYNC_AT))


def _rows(page):
    return page.locator("#pqu-table tbody tr:not(.station-detail)")


def test_tabs_follow_the_route_and_move_focus_to_the_view(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains")
    page = opened.page
    labels = page.locator("#tabs a").all_inner_texts()
    assert {"Trains", "Versions"} <= set(labels)
    assert labels == [label for label in TAB_ORDER if label in labels]
    assert page.locator("#tabs a[aria-current='page']").inner_text() == "Trains"
    assert page.title() == "PQU trains · D365 PQU Tracker"

    page.locator("#tabs a", has_text="Versions").focus()
    page.keyboard.press("Enter")
    wait_for_render(page)
    assert page.evaluate("location.hash") == "#/versions"
    assert page.locator("#tabs a[aria-current='page']").inner_text() == "Versions"
    assert page.evaluate("document.activeElement.id") == "versions-heading"
    assert page.title() == "Service updates · D365 PQU Tracker"
    opened.assert_clean()


def test_deep_link_restores_filters(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains?status=On-Going&version=10.0.48")
    page = opened.page
    assert page.locator("#status-filter").input_value() == "On-Going"
    assert page.locator("#version-filter").input_value() == "10.0.48"
    rows = _rows(page)
    assert rows.count() == 13
    assert set(rows.locator("td:nth-child(2)").all_inner_texts()) == {"10.0.48"}
    assert page.locator("#filter-note").inner_text() == "13 of 59 trains shown · 1 due soon"
    opened.assert_clean()


def test_status_options_come_from_the_data(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains")
    options = opened.page.locator("#status-filter option").all_inner_texts()
    assert options == [
        "All statuses (59)",
        "On-Going (37)",
        "In-Progress (5)",
        "Not Started (32)",
        "Completed (21)",
        "Canceled (1)",
    ]
    opened.assert_clean()


def test_filter_sort_and_page_changes_are_written_to_the_url(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains")
    page = opened.page
    page.locator("#status-filter").select_option("Not Started")
    assert page.evaluate("location.hash") == "#/trains?status=Not%20Started"
    page.locator(".th-sort[data-sort='train_start_date']").click()
    page.locator(".th-sort[data-sort='train_start_date']").click()
    assert page.evaluate("location.hash") == (
        "#/trains?status=Not%20Started&sort=train_start_date&dir=desc"
    )
    page.locator("#next-page").click()
    assert page.evaluate("location.hash").endswith("&page=2")
    page.locator("#search").fill("10.0.49")
    page.wait_for_function("() => location.hash.includes('q=10.0.49')")
    assert page.evaluate("location.hash") == (
        "#/trains?q=10.0.49&status=Not%20Started&sort=train_start_date&dir=desc"
    )
    page.reload()
    page.wait_for_selector("body[data-ready='true']")
    assert page.locator("#search").input_value() == "10.0.49"
    assert page.locator("#status-filter").input_value() == "Not Started"
    header = page.locator("th", has=page.locator(".th-sort[data-sort='train_start_date']"))
    assert header.get_attribute("aria-sort") == "descending"
    assert _rows(page).first.inner_text().startswith("10.0.49-PQU-17")
    page.locator("#reset-filters").click()
    assert page.evaluate("location.hash") == "#/trains"
    assert _rows(page).count() == 20
    opened.assert_clean()


def test_back_button_returns_to_the_filtered_view(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains")
    page = opened.page
    page.locator("#version-filter").select_option("10.0.47")
    page.locator("#tabs a", has_text="Versions").click()
    wait_for_render(page)
    page.go_back()
    wait_for_render(page)
    assert page.evaluate("location.hash") == "#/trains?version=10.0.47"
    assert page.locator("#version-filter").input_value() == "10.0.47"
    assert _rows(page).count() == 17
    assert page.evaluate("document.activeElement.id") == "schedule-heading"
    opened.assert_clean()


def test_unknown_route_shows_not_found(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/nowhere/at-all")
    page = opened.page
    assert page.locator("#not-found-heading").inner_text() == "Page not found"
    assert "#/nowhere/at-all" in page.locator("#view").inner_text()
    assert page.locator("#tabs a[aria-current]").count() == 0
    assert page.title() == "Page not found · D365 PQU Tracker"
    opened.assert_clean()


def test_versions_show_todays_lifecycle_phase(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/versions")
    page = opened.page

    def row(version: str):
        return page.locator(f"#version-table tr#version-{version.replace('.', '-')}")

    def phase(version: str) -> str:
        return " ".join((row(version).locator(".phase-name").text_content() or "").split())

    assert phase("10.0.46") == "Calculated: End of service"
    assert "End of service · 38 days ago" in (row("10.0.46").text_content() or "")
    assert phase("10.0.49") == "Calculated: Generally available"
    assert "First autoupdate in 4 days · Fri 2 Oct" in (row("10.0.49").text_content() or "")
    # The next milestone is marked in the dates.
    assert row("10.0.49").locator("td.is-next").text_content() == "2 Oct 2026"
    assert phase("10.0.50") == "Calculated: Upcoming"
    assert "Preview in 25 days · Fri 23 Oct" in (row("10.0.50").text_content() or "")
    assert phase("10.0.47") == "Calculated: Supported"
    majors = [
        version
        for version in ("10.0.45", "10.0.46", "10.0.47", "10.0.48", "10.0.49", "10.0.50", "10.0.51")
        if row(version).locator(".tag-major").count()
    ]
    assert majors == ["10.0.45", "10.0.47", "10.0.49", "10.0.51"]
    headers = page.locator("#version-table thead th").all_text_contents()
    assert headers == [
        "Version",
        "Today",
        "Preview",
        "Latest preview update",
        "General availability",
        "First autoupdate",
        "Second autoupdate",
        "End of service",
    ]

    trains = page.locator("#version-trains tr.version-trains[data-version='10.0.47'] td")
    assert trains.all_text_contents()[:5] == ["17", "2", "4", "10", "1"]
    assert " ".join((trains.nth(5).text_content() or "").split()) == (
        "10.0.2527.215 Platform 7.0.7858.174 · 10.0.47 PQU-13"
    )

    plot = page.locator("#lifecycle-chart .lc-plot")
    assert plot.get_attribute("role") == "img"
    assert plot.get_attribute("aria-label") == (
        "Lifecycle of 7 service updates from 28 Jul 2025 to 19 Nov 2027. Today is 28 Sep 2026. "
        "The table below lists every date."
    )
    lanes = page.locator("#lifecycle-chart .lc-row[data-version]")
    assert lanes.count() == 7
    assert [
        lane.get_attribute("data-version")
        for lane in page.locator("#lifecycle-chart .lc-row.is-past").all()
    ] == ["10.0.46", "10.0.45"]
    assert page.locator("#lifecycle-chart .lc-today").count() == 1
    stats = dict(
        zip(
            page.locator("#version-stats dt").all_text_contents(),
            page.locator("#version-stats dd").all_text_contents(),
            strict=True,
        )
    )
    assert stats == {
        "In service today": "10.0.47, 10.0.48 and 10.0.49",
        "Next milestone": "10.0.49 first autoupdate · Fri 2 Oct 2026 (in 4 days)",
        "Next end of service": "10.0.47 · Fri 20 Nov 2026 (in 53 days)",
    }
    rules = page.locator("#service-update-rules")
    rules.locator("summary").click()
    assert "A sandbox autoupdate occurs seven days before the production update." in (
        rules.inner_text()
    )
    page.locator("#version-trains").get_by_role("link", name="Show 10.0.47 trains").click()
    wait_for_render(page)
    assert page.locator("#version-filter").input_value() == "10.0.47"
    opened.assert_clean()


def test_versions_without_the_lifecycle_article_still_list_train_versions(
    fixture_site, open_page
) -> None:
    opened = open_page(fixture_site((MINIMAL, E2E_SYNC_AT)), "#/versions")
    page = opened.page
    assert "not part of this dataset" in page.locator(".inline-alert").inner_text()
    rows = page.locator("#version-table tbody tr")
    assert [
        " ".join((header.text_content() or "").split()) for header in rows.locator("th").all()
    ] == ["10.0.48", "10.0.47"]
    assert rows.first.locator(".phase-name").text_content() == "No lifecycle dates"
    assert page.locator("#version-stats").count() == 0
    assert page.locator("#lifecycle-chart").count() == 0
    opened.assert_clean()
