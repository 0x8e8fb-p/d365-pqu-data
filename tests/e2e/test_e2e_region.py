from __future__ import annotations

import pytest

from conftest import E2E_SYNC_AT, FIXTURES, LIVE_FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

REGION_KEY = "d365-pqu-region"


def _live(fixture_site) -> str:
    return fixture_site((LIVE_FIXTURES, E2E_SYNC_AT))


def _card(page, pqu_id: str, container: str = "#window-list"):
    return page.locator(f"{container} article.window-card[data-pqu='{pqu_id}']")


def _line(card, kind: str) -> tuple[str, str]:
    """(dates, calculated state) of a card's sandbox or production line."""
    line = card.locator(".window-line", has_text=kind)
    state = line.locator(".window-state")
    return (
        line.locator(".window-dates").inner_text(),
        (state.text_content() or "") if state.count() else "",
    )


def test_picker_lists_every_station_and_filters_regions(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/region")
    page = opened.page
    assert page.locator("#region-heading").inner_text() == "Find your update windows"
    intro = page.locator("#region-intro").inner_text()
    assert "find the region and the station-to-region mapping" in intro
    assert "Station 1 is the first release station." in intro
    assert "Source: Release schedule for proactive quality updates" in intro
    assert (
        page.locator("#region-rules summary").text_content().startswith("Microsoft's rollout rules")
    )
    cards = page.locator("#station-grid .station-card")
    assert cards.locator("h3").all_text_contents() == [f"Station {n}" for n in range(1, 7)]
    assert cards.first.locator(".station-note").inner_text() == "Only for opted-in environments"
    assert page.locator("#station-grid a").count() == 30
    search = page.locator("#region-search")
    search.fill("north eu")
    visible = page.locator("#station-grid li:not([hidden]) a")
    assert visible.all_inner_texts() == ["North Europe"]
    assert page.locator("#region-search-status").inner_text() == "1 matching region."
    assert page.locator("#station-grid .station-card:not([hidden]) h3").all_text_contents() == [
        "Station 4"
    ]
    search.fill("atlantis")
    assert page.locator("#region-search-status").inner_text() == "No region matches."
    search.fill("north eu")
    search.press("Enter")
    wait_for_render(page)
    assert page.evaluate("location.hash") == "#/region/North%20Europe"
    assert page.evaluate(f"localStorage.getItem('{REGION_KEY}')") == "North Europe"
    assert page.locator("#region-save").inner_text().startswith("Saved as your region.")
    opened.assert_clean()


def test_region_shows_station_windows_and_dark_hours_in_ist(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/region/North%20Europe")
    page = opened.page
    assert page.locator("#region-heading").inner_text() == "North Europe"
    assert page.title() == "North Europe · My region · PQU Console"
    facts = dict(
        zip(
            page.locator("#region-facts dt").all_text_contents(),
            page.locator("#region-facts dd").all_inner_texts(),
            strict=True,
        )
    )
    assert facts["Station"] == "Station 4"
    assert facts["Also on Station 4"] == (
        "Brazil South, East Asia, East US, Japan West, UAE Central and UK West"
    )
    maintenance = facts["Maintenance window (dark hours)"]
    assert maintenance.startswith("Europe · Friday and Saturday · 22:00 UTC · Six hours")
    assert "Geography matched from the region name." in maintenance
    assert "Next: Fri 2 Oct 22:00 UTC = Sat 3 Oct 03:30 IST · until 09:30 IST" in maintenance

    cards = page.locator("#window-list article.window-card")
    assert [card.get_attribute("data-pqu") for card in cards.all()] == [
        "10.0.48-PQU-6",
        "10.0.47-PQU-13",
    ]
    current = _card(page, "10.0.48-PQU-6")
    assert "is-current" in (current.get_attribute("class") or "")
    assert _line(current, "Sandbox") == (
        "Mon 28 Sep \u2013 Thu 1 Oct",
        "Calculated: In progress · day 1 of 4",
    )
    assert _line(current, "Production") == (
        "Sat 3 Oct \u2013 Sun 4 Oct",
        "Calculated: Starts in 5 days",
    )
    assert current.locator(".dark-hours li").all_inner_texts() == [
        "Fri 2 Oct 22:00 UTC = Sat 3 Oct 03:30 IST · until 09:30 IST",
        "Sat 3 Oct 22:00 UTC = Sun 4 Oct 03:30 IST · until 09:30 IST",
    ]
    past = page.locator("#past-windows")
    assert past.locator("summary").text_content() == "Earlier windows · 3"
    unscheduled = page.locator("#unscheduled li").all_inner_texts()
    assert unscheduled[0].startswith("10.0.48 PQU-7")
    assert unscheduled[0].endswith("train starts Wed 30 Sep (in 2 days)")
    assert page.get_by_role("link", name="All 32 Not Started trains").count() == 1
    rules = page.locator("#region-rules")
    rules.locator("summary").click()
    assert "schedule shows a range of four days" in rules.inner_text()
    opened.assert_clean()


def test_dark_hours_follow_the_chosen_zone_and_mark_the_current_window(
    fixture_site, open_page
) -> None:
    opened = open_page(
        _live(fixture_site),
        "#/region/North%20Europe",
        zone="America/Los_Angeles",
        locale="en-US",
        now="2026-10-02T23:00:00Z",
    )
    page = opened.page
    items = _card(page, "10.0.48-PQU-6").locator(".dark-hours li")
    assert items.first.inner_text() == (
        "Fri 2 Oct 22:00 UTC = Fri 2 Oct 15:00 PDT · until 21:00 PDT Now"
    )
    assert "occ-now" in (items.first.get_attribute("class") or "")
    assert "occ-upcoming" in (items.nth(1).get_attribute("class") or "")
    opened.assert_clean()


def test_sovereign_cloud_has_no_window_and_no_guess(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/region/DoD")
    page = opened.page
    assert page.locator("#region-heading").inner_text() == "DoD"
    facts = page.locator("#region-facts").inner_text()
    assert "Station 6" in facts
    assert "Microsoft's planned maintenance table doesn't list a window for this cloud." in facts
    assert page.locator(".dark-hours").count() == 0
    assert [
        card.get_attribute("data-pqu")
        for card in page.locator("#window-list article.window-card").all()
    ] == ["10.0.47-PQU-12", "10.0.46-PQU-8", "10.0.48-PQU-6", "10.0.47-PQU-13"]
    opened.assert_clean()


def test_unknown_and_differently_cased_region_names(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/region/Atlantis")
    page = opened.page
    assert "Atlantis is not in Microsoft's station-to-region mapping." in (
        page.locator(".inline-alert").inner_text()
    )
    assert page.locator("#station-grid").is_visible()
    page.evaluate("location.hash = '#/region/north%20europe'")
    wait_for_render(page)
    assert page.locator("#region-heading").inner_text() == "North Europe"
    opened.assert_clean()


def test_saved_region_is_shared_with_the_trains_view(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains", storage={REGION_KEY: "North Europe"})
    page = opened.page
    assert page.locator("#region-select").input_value() == "North Europe"
    assert page.evaluate("location.hash") == "#/trains?region=North%20Europe"
    assert page.locator("#filter-note").inner_text().endswith("· Station 4 context")
    page.get_by_role("link", name="Open North Europe in My region").click()
    wait_for_render(page)
    assert page.locator("#region-heading").inner_text() == "North Europe"

    page.locator("#tabs a", has_text="Trains").click()
    wait_for_render(page)
    page.locator("#region-select").select_option("East US")
    assert page.evaluate(f"localStorage.getItem('{REGION_KEY}')") == "East US"
    page.locator("#tabs a", has_text="My region").click()
    wait_for_render(page)
    assert page.evaluate("location.hash") == "#/region/East%20US"
    assert page.locator("#region-heading").inner_text() == "East US"

    page.locator("#tabs a", has_text="Trains").click()
    wait_for_render(page)
    page.locator("#reset-filters").click()
    assert page.evaluate(f"localStorage.getItem('{REGION_KEY}')") is None
    assert page.evaluate("location.hash") == "#/trains"
    opened.assert_clean()


def test_save_and_forget_a_shared_region_link(fixture_site, open_page) -> None:
    opened = open_page(
        _live(fixture_site), "#/region/West%20US", storage={REGION_KEY: "North Europe"}
    )
    page = opened.page
    assert page.locator("#region-heading").inner_text() == "West US"
    assert page.evaluate(f"localStorage.getItem('{REGION_KEY}')") == "North Europe"
    page.get_by_role("button", name="Save as my region").click()
    assert page.evaluate(f"localStorage.getItem('{REGION_KEY}')") == "West US"
    page.get_by_role("button", name="Forget").click()
    assert page.evaluate(f"localStorage.getItem('{REGION_KEY}')") is None
    assert page.get_by_role("button", name="Save as my region").count() == 1
    opened.assert_clean()


def test_region_without_maintenance_article_explains_what_is_missing(
    fixture_site, open_page
) -> None:
    opened = open_page(
        fixture_site((FIXTURES / "source-minimal.md", E2E_SYNC_AT)), "#/region/India%20Central"
    )
    page = opened.page
    assert "maintenance windows are not available in this dataset" in (
        page.locator("#region-facts").inner_text()
    )
    assert "No current or upcoming Station 2 windows in Microsoft's schedule." in (
        page.locator("#view").inner_text()
    )
    page.locator("#past-windows summary").click()
    card = _card(page, "10.0.48-PQU-6", "#past-windows")
    assert _line(card, "Production") == (
        "Sat 26 Sep \u2013 Sun 27 Sep",
        "Calculated: Ended yesterday",
    )
    opened.assert_clean()
