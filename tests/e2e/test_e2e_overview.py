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


def _live(fixture_site) -> str:
    return fixture_site((LIVE_FIXTURES, E2E_SYNC_AT))


def _agenda_day(page, day: str):
    return page.locator(f"#agenda li.agenda-day[data-day='{day}']")


def test_overview_is_the_landing_page(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site))
    page = opened.page
    assert page.locator("#tabs a").first.inner_text() == "Overview"
    assert page.locator("#tabs a[aria-current='page']").inner_text() == "Overview"
    assert page.locator("#overview-heading").inner_text() == "Proactive quality updates today"
    assert page.title() == "Overview · PQU Console"
    assert page.locator(".overview .kicker").inner_text().lower() == "mon 28 sep 2026"
    summary = page.locator("#ov-summary")
    assert summary.locator(".visually-hidden").text_content() == "Summary: "
    assert _visible(summary) == (
        "Microsoft lists 5 trains as In-Progress, the next change cutoff is 10.0.48 PQU-7 in "
        "2 days (Wed 30 Sep) and 10.0.47, 10.0.48 and 10.0.49 are in service."
    )
    opened.assert_clean()


def test_in_progress_card_lists_every_running_train_with_its_phase(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site))
    page = opened.page
    items = page.locator("#ov-running li")
    assert [item.get_attribute("data-pqu") for item in items.all()] == [
        "10.0.46-PQU-8",
        "10.0.47-PQU-12",
        "10.0.47-PQU-13",
        "10.0.48-PQU-5",
        "10.0.48-PQU-6",
    ]
    stale = page.locator("#ov-running li[data-pqu='10.0.48-PQU-5']")
    assert "Scheduled end passed 2 days ago" in stale.inner_text()
    assert "Microsoft still lists this train as In-Progress" in stale.inner_text()
    running = page.locator("#ov-running li[data-pqu='10.0.48-PQU-6']")
    assert "Day 13 of 25 · Now: Station 4 sandbox (28 Sep \u2013 1 Oct)" in running.inner_text()
    assert running.locator(".chip-new").count() == 1
    link = page.get_by_role("link", name="All in-progress trains")
    link.click()
    wait_for_render(page)
    assert page.evaluate("location.hash") == "#/trains?status=In-Progress"
    assert page.locator("#pqu-table tbody tr:not(.station-detail)").count() == 5
    opened.assert_clean()


def test_next_dates_card_names_the_change_cutoff(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site))
    rows = opened.page.locator("#ov-next li").all_inner_texts()
    assert rows[0] == "Wed 30 Sep\nin 2 days\n10.0.48 PQU-7 · change cutoff and train start"
    assert len(rows) == 4
    opened.assert_clean()


def test_region_card_prompts_until_a_region_is_saved(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site))
    page = opened.page
    card = page.locator("#ov-region")
    assert "Pick your Azure region" in card.inner_text()
    card.get_by_role("link", name="Pick your region").click()
    wait_for_render(page)
    assert page.evaluate("location.hash") == "#/region"
    assert page.locator("#agenda").count() == 0
    opened.assert_clean()


def test_saved_region_shows_its_next_production_window(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), storage={REGION_KEY: "North Europe"})
    page = opened.page
    card = page.locator("#ov-region")
    assert card.locator(".ov-region-name").inner_text() == "North Europe · Station 4"
    big = card.locator(".ov-big")
    assert big.locator(".visually-hidden").text_content() == "Next production window: "
    assert _visible(big) == "Sat 3 Oct \u2013 Sun 4 Oct"
    assert "Production · 10.0.48 PQU-6 · Starts in 5 days" in card.inner_text()
    assert card.locator(".ov-dark-hours li").all_inner_texts() == [
        "Sat 3 Oct 03:30 \u2013 09:30 IST",
        "Sun 4 Oct 03:30 \u2013 09:30 IST",
    ]
    assert "Sandbox now: 10.0.48 PQU-6 (in progress · day 1 of 4)" in card.inner_text()
    opened.assert_clean()


def test_versions_card_shows_serviced_versions_newest_first(fixture_site, open_page) -> None:
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
    assert rows.first.locator(".ov-version-next .visually-hidden").text_content() == (
        "Calculated: "
    )
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
    assert [item.get_attribute("data-event") for item in today.locator(".agenda-event").all()] == [
        "sandbox_window:10.0.48-PQU-6:station-4"
    ]
    cutoff_day = _agenda_day(page, "2026-09-30")
    assert cutoff_day.locator(".agenda-event").first.inner_text() == ("Change cutoff 10.0.48 PQU-7")
    production = _agenda_day(page, "2026-10-03").locator(".agenda-event")
    assert production.all_inner_texts() == [
        "Production window 10.0.48 PQU-6 · Station 4 · 3\u20134 Oct"
    ]
    assert page.locator("#agenda .agenda-event[data-event*='station-5']").count() == 0
    assert _agenda_day(page, "2026-10-02").inner_text().endswith("First autoupdate 10.0.49")
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
    assert today.first.inner_text() == (
        "Sandbox window 10.0.47 PQU-12 · Station 5 · 28 Sep \u2013 1 Oct"
    )
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
    assert events.first.inner_text() == (
        "Sandbox window 10.0.47 PQU-12 · Station 5 · until Thu 1 Oct"
    )
    assert _agenda_day(page, "2026-09-28").count() == 0
    opened.assert_clean()


def test_insights_and_sources_strips(fixture_site, open_page) -> None:
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
    opened.assert_clean()


def test_overview_with_only_the_schedule_article(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((FIXTURES / "source-minimal.md", E2E_SYNC_AT)))
    page = opened.page
    assert _visible(page.locator("#ov-summary")) == (
        "Microsoft lists 2 trains as In-Progress and the next change cutoff is 10.0.48 PQU-7 "
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
