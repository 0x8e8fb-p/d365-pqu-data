from __future__ import annotations

import pytest

from conftest import E2E_SYNC_AT, FIXTURES, LIVE_FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

REGION_KEY = "d365-pqu-region"
VISIBLE_TEXT = """el => {
  let text = el.innerText;
  for (const node of el.querySelectorAll('.visually-hidden')) {
    const hidden = (node.textContent || '').trim();
    if (hidden) {
      text = text.replace(hidden, '');
    }
  }
  return text;
}"""


def _visible(locator) -> str:
    """Text a sighted reader sees: hidden screen-reader labels removed, whitespace collapsed."""
    return " ".join(str(locator.evaluate(VISIBLE_TEXT)).split())


def _text(locator) -> str:
    return " ".join((locator.text_content() or "").split())


def _live(fixture_site) -> str:
    return fixture_site((LIVE_FIXTURES, E2E_SYNC_AT))


def _agenda_day(page, day: str):
    return page.locator(f"#agenda li.agenda-day[data-day='{day}']")


def test_overview_is_the_landing_page(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site))
    page = opened.page
    assert page.locator("#tabs a").first.inner_text() == "Overview"
    assert page.locator("#tabs a[aria-current='page']").inner_text() == "Overview"
    # Today's date, in the viewer's time zone, is the page heading.
    assert page.locator("#overview-heading").text_content() == "Monday 28 September 2026"
    assert page.locator("h1").count() == 1
    assert page.title() == "Overview · D365 PQU Tracker"
    summary = page.locator("#ov-summary")
    assert summary.locator(".visually-hidden").text_content() == "Summary: "
    assert _visible(summary) == (
        "Microsoft lists 5 trains as In-Progress. The next change cutoff, for 10.0.48 PQU-7, is "
        "in 2 days (Wed 30 Sep). 10.0.47, 10.0.48 and 10.0.49 are in service."
    )
    # Calculated words are set in italics; Microsoft's values are not.
    assert summary.locator(".calc").all_text_contents() == ["in 2 days", "in service"]
    note = page.locator(".page-head .calc-note")
    assert _text(note) == (
        "Italic values are calculated from Microsoft's published dates for Mon 28 Sep 2026 "
        "(Asia/Kolkata)."
    )
    opened.assert_clean()


def test_in_progress_table_lists_every_running_train_with_its_phase(
    fixture_site, open_page
) -> None:
    opened = open_page(_live(fixture_site))
    page = opened.page
    rows = page.locator("#ov-running tbody tr")
    assert [row.get_attribute("data-pqu") for row in rows.all()] == [
        "10.0.46-PQU-8",
        "10.0.47-PQU-12",
        "10.0.47-PQU-13",
        "10.0.48-PQU-5",
        "10.0.48-PQU-6",
    ]
    headers = page.locator("#ov-running thead th").all_text_contents()
    assert headers == ["Train", "Application build", "Where it is today"]
    stale = page.locator("#ov-running tr[data-pqu='10.0.48-PQU-5']")
    assert "Scheduled end passed 2 days ago" in _text(stale)
    assert "Microsoft still lists this train as In-Progress" in _text(stale)
    running = page.locator("#ov-running tr[data-pqu='10.0.48-PQU-6']")
    phase = running.locator(".phase-line")
    assert _visible(phase) == "Day 13 of 25 · Now: Station 4 sandbox (28 Sep \u2013 1 Oct)"
    assert phase.locator(".visually-hidden").text_content() == "Calculated: "
    assert "calc" in (phase.get_attribute("class") or "")
    assert _text(running.locator("td").first) == "10.0.2645.136"
    assert running.locator(".tag-new").text_content() == "New"
    link = page.get_by_role("link", name="All in-progress trains")
    link.click()
    wait_for_render(page)
    assert page.evaluate("location.hash") == "#/trains?status=In-Progress"
    assert page.locator("#pqu-table tbody tr:not(.station-detail)").count() == 5
    opened.assert_clean()


def test_next_dates_list_names_the_change_cutoff(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site))
    rows = opened.page.locator("#ov-next li")
    assert rows.count() == 4
    assert _text(rows.first) == "Wed 30 Sep in 2 days 10.0.48 PQU-7 · change cutoff and train start"
    assert rows.first.locator(".calc").text_content() == "in 2 days"
    opened.assert_clean()


def test_region_block_prompts_until_a_region_is_saved(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site))
    page = opened.page
    block = page.locator("#ov-region")
    assert "Pick your Azure region" in block.inner_text()
    block.get_by_role("link", name="Pick your region").click()
    wait_for_render(page)
    assert page.evaluate("location.hash") == "#/region"
    assert page.locator("#agenda").count() == 0
    opened.assert_clean()


def test_saved_region_shows_its_next_production_window(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), storage={REGION_KEY: "North Europe"})
    page = opened.page
    block = page.locator("#ov-region")
    assert block.locator(".ov-region-name").inner_text() == "North Europe · Station 4"
    big = block.locator(".ov-big")
    assert big.locator(".visually-hidden").text_content() == "Next production window: "
    assert _visible(big) == "Sat 3 Oct \u2013 Sun 4 Oct"
    facts = {
        _text(item.locator("dt")): _text(item.locator("dd"))
        for item in block.locator(".ov-region-facts > div").all()
    }
    assert facts["Next production window"].endswith("10.0.48 PQU-6 · starts in 5 days")
    assert "Europe dark hours that weekend" in facts
    assert block.locator(".ov-dark-hours li").all_inner_texts() == [
        "Sat 3 Oct 03:30 \u2013 09:30 IST",
        "Sun 4 Oct 03:30 \u2013 09:30 IST",
    ]
    assert facts["Sandbox now"] == "10.0.48 PQU-6 · in progress · day 1 of 4"
    opened.assert_clean()


def test_versions_list_shows_serviced_versions_newest_first(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site))
    rows = opened.page.locator("#ov-versions li")
    assert [row.get_attribute("data-version") for row in rows.all()] == [
        "10.0.49",
        "10.0.48",
        "10.0.47",
    ]
    assert _visible(rows.first) == (
        "10.0.49 Generally available First autoupdate in 4 days · Fri 2 Oct"
    )
    assert rows.first.locator(".phase-name .visually-hidden").text_content() == "Calculated: "
    assert (
        rows.nth(2)
        .locator(".ov-version-next")
        .inner_text()
        .endswith("End of service in 53 days · Fri 20 Nov")
    )
    assert rows.first.locator("a.ov-version").get_attribute("href") == "#/versions?version=10.0.49"
    finder = opened.page.locator("#ov-find-build a")
    assert finder.text_content() == "Find my build"
    finder.click()
    opened.page.wait_for_function("() => location.hash === '#/versions'")
    wait_for_render(opened.page)
    assert opened.page.locator("#build-finder").is_visible()
    opened.assert_clean()


def test_agenda_covers_fourteen_days_filtered_to_the_saved_station(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), storage={REGION_KEY: "North Europe"})
    page = opened.page
    assert page.locator("#ov-agenda-title").inner_text() == "Next 14 days · Station 4"
    days = page.locator("#agenda li.agenda-day").evaluate_all(
        "items => items.map(i => i.dataset.day)"
    )
    assert days == [
        "2026-09-28",
        "2026-09-30",
        "2026-10-02",
        "2026-10-03",
        "2026-10-05",
        "2026-10-07",
        "2026-10-10",
    ]
    today = _agenda_day(page, "2026-09-28")
    assert "is-today" in (today.get_attribute("class") or "")
    assert _text(today.locator(".agenda-date")) == "Mon 28 Sep today"
    assert [item.get_attribute("data-event") for item in today.locator(".agenda-event").all()] == [
        "sandbox_window:10.0.48-PQU-6:station-4"
    ]
    cutoff_day = _agenda_day(page, "2026-09-30")
    assert _text(cutoff_day.locator(".agenda-event").first) == "Change cutoff 10.0.48 PQU-7"
    production = _agenda_day(page, "2026-10-03").locator(".agenda-event")
    assert [_text(item) for item in production.all()] == [
        "Production window 10.0.48 PQU-6 · Station 4 · 3\u20134 Oct"
    ]
    assert page.locator("#agenda .agenda-event[data-event*='station-5']").count() == 0
    assert _text(_agenda_day(page, "2026-10-02")).endswith("First autoupdate 10.0.49")
    opened.assert_clean()


def test_agenda_without_a_region_lists_every_station(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site))
    page = opened.page
    assert page.locator("#ov-agenda-title").inner_text() == "Next 14 days"
    stations = page.locator("#agenda .agenda-event[data-event^='production_window']")
    assert stations.count() == 10
    today = _agenda_day(page, "2026-09-28").locator(".agenda-event")
    assert today.count() == 5
    # Windows that start today show their dates; they are not "open" yet.
    assert _text(today.first) == "Sandbox window 10.0.47 PQU-12 · Station 5 · 28 Sep \u2013 1 Oct"
    # Running trains are in "In progress now", not repeated in the agenda.
    assert (
        page.locator("#agenda .agenda-event[data-event^='train_window:10.0.48-PQU-6']").count() == 0
    )
    opened.assert_clean()


def test_windows_already_open_are_listed_under_today(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), now="2026-09-29T04:00:00Z")
    page = opened.page
    today = _agenda_day(page, "2026-09-29")
    assert "is-today" in (today.get_attribute("class") or "")
    events = today.locator(".agenda-event")
    assert events.count() == 5
    assert _text(events.first) == "Sandbox window 10.0.47 PQU-12 · Station 5 · until Thu 1 Oct"
    assert events.first.locator(".calc").text_content() == "until Thu 1 Oct"
    assert _agenda_day(page, "2026-09-28").count() == 0
    opened.assert_clean()


def test_insights_and_sources_lists(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site))
    page = opened.page
    assert page.locator("#ov-insights li").all_inner_texts()[0] == (
        "10.0.49: a new train starts every 14 days, or 2 weeks "
        "(median of 16 intervals; range 14\u201321 days)."
    )
    sources = page.locator("#ov-sources a")
    assert sources.all_inner_texts() == [
        "Release schedule for proactive quality updates",
        "Service update availability",
        "Maintenance in self-service environments FAQ",
        "Proactive quality updates overview",
        "Proactive quality updates FAQ",
    ]
    assert all((link.get_attribute("rel") or "") == "noopener noreferrer" for link in sources.all())
    assert _text(page.locator("#ov-sources li").first).endswith(
        "Microsoft Learn · updated 21 Sep 2026"
    )
    opened.assert_clean()


def test_overview_with_only_the_schedule_article(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((FIXTURES / "source-minimal.md", E2E_SYNC_AT)))
    page = opened.page
    assert _visible(page.locator("#ov-summary")) == (
        "Microsoft lists 2 trains as In-Progress. The next change cutoff, for 10.0.48 PQU-7, is "
        "in 2 days (Wed 30 Sep)."
    )
    assert "not part of this dataset" in page.locator("#ov-versions").inner_text()
    assert [link.inner_text() for link in page.locator("#ov-sources a").all()] == [
        "Release schedule for proactive quality updates"
    ]
    opened.assert_clean()


def test_overview_after_the_last_published_date(fixture_site, open_page) -> None:
    opened = open_page(
        fixture_site((FIXTURES / "source-minimal.md", E2E_SYNC_AT)), now="2027-03-01T04:00:00Z"
    )
    page = opened.page
    assert (
        page.locator("#ov-next")
        .inner_text()
        .endswith("No upcoming change cutoffs or train starts in Microsoft's schedule.")
    )
    agenda = page.locator("#ov-agenda")
    assert agenda.locator("#agenda").count() == 0
    assert agenda.get_by_text("No published dates in the next 14 days.", exact=True).count() == 1
    assert agenda.locator("#ov-calendar").count() == 1
    assert page.locator("#health-toggle").get_attribute("data-state") == "stale"
