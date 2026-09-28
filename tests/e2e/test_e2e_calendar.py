from __future__ import annotations

import pytest

from conftest import E2E_SYNC_AT, LIVE_FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

REGION_KEY = "d365-pqu-region"


def _live(fixture_site) -> str:
    return fixture_site((LIVE_FIXTURES, E2E_SYNC_AT))


def _text(locator) -> str:
    return " ".join((locator.text_content() or "").split())


def test_my_region_offers_its_station_calendar(fixture_site, open_page) -> None:
    base = _live(fixture_site)
    opened = open_page(base, "#/region/North%20Europe")
    page = opened.page
    section = page.locator("#region-calendar")
    assert _text(section.locator("h3")) == "Add to your calendar"

    station = page.locator("#region-calendar-station")
    assert station.get_attribute("data-calendar") == "station-4.ics"
    assert _text(station.locator(".calendar-title")) == "Station 4 windows · 10 events"
    address = f"{base.rstrip('/')}/calendar/station-4.ics"
    field = page.locator("#region-calendar-station-address")
    assert field.input_value() == address
    assert field.get_attribute("readonly") is not None
    subscribe = station.get_by_role("link", name="Subscribe to Station 4 windows")
    assert subscribe.get_attribute("href") == "webcal://" + address.split("://", 1)[1]
    download = station.get_by_role("link", name="Download .ics for Station 4 windows")
    assert download.get_attribute("href") == "./calendar/station-4.ics"
    assert download.get_attribute("download") == "d365-pqu-station-4.ics"

    milestones = page.locator("#region-calendar-milestones")
    assert _text(milestones.locator(".calendar-title")) == (
        "Change cutoffs and service updates · 101 events"
    )

    field.focus()
    selected = page.evaluate(
        "(() => { const f = document.activeElement; return f.value.slice(f.selectionStart, f.selectionEnd); })()"
    )
    assert selected == address
    opened.assert_clean()


def test_the_linked_calendars_are_served(fixture_site, open_page) -> None:
    base = _live(fixture_site)
    opened = open_page(base, "#/region/North%20Europe")
    page = opened.page
    for href in (
        page.locator("#region-calendar-station .calendar-download").get_attribute("href"),
        page.locator("#region-calendar-milestones .calendar-download").get_attribute("href"),
    ):
        assert href is not None
        response = page.request.get(base.rstrip("/") + "/" + href.removeprefix("./"))
        assert response.status == 200
        assert response.headers["content-type"] == "text/calendar; charset=utf-8"
        body = response.body()
        assert body.startswith(b"BEGIN:VCALENDAR\r\n")
    station = page.request.get(base.rstrip("/") + "/calendar/station-4.ics").body()
    assert b"UID:production_window:10.0.48-PQU-6:station-4@" in station
    opened.assert_clean()


def test_overview_calendar_follows_the_saved_region(fixture_site, open_page) -> None:
    base = _live(fixture_site)
    opened = open_page(base, "#/")
    page = opened.page
    details = page.locator("#ov-calendar")
    assert details.get_attribute("open") is None
    details.locator("summary").click()
    assert page.locator("#ov-calendar-milestones").is_visible()
    assert page.locator("#ov-calendar-station").count() == 0
    hint = details.get_by_role("link", name="pick your region")
    assert hint.get_attribute("href") == "#/region"
    opened.assert_clean()

    saved = open_page(base, "#/", storage={REGION_KEY: "North Europe"})
    page = saved.page
    page.locator("#ov-calendar summary").click()
    station = page.locator("#ov-calendar-station")
    assert station.get_attribute("data-calendar") == "station-4.ics"
    assert _text(station.locator(".calendar-title")) == "Station 4 windows · 10 events"
    assert page.locator("#ov-calendar").get_by_role("link", name="pick your region").count() == 0
    saved.assert_clean()


def test_counts_are_left_out_when_the_key_dates_are_missing(fixture_site, open_page) -> None:
    opened = open_page(
        _live(fixture_site), "#/region/North%20Europe", routes={"**/api/events.json": 404}
    )
    page = opened.page
    wait_for_render(page)
    assert _text(page.locator("#region-calendar-station .calendar-title")) == "Station 4 windows"
    assert page.locator("#region-calendar-station .calendar-download").count() == 1
