from __future__ import annotations

import json

import pytest

from conftest import E2E_SYNC_AT, LIVE_FIXTURES, fixture_commit, wait_for_render

pytestmark = pytest.mark.e2e

REPOSITORY = "MicrosoftDocs/dynamics-365-unified-operations-public"


def _live(fixture_site) -> str:
    return fixture_site((LIVE_FIXTURES, E2E_SYNC_AT))


def _text(locator) -> str:
    return " ".join((locator.text_content() or "").split())


def test_data_view_lists_every_published_file(fixture_site, open_page) -> None:
    base = _live(fixture_site)
    opened = open_page(base, "#/data")
    page = opened.page
    assert page.title() == "Data & API · PQU Console"
    assert page.locator("#data-heading").text_content() == "Data & API"
    assert page.locator("#data-link").get_attribute("aria-current") == "page"
    assert page.locator("#tabs a[aria-current]").count() == 0

    facts = {
        _text(item.locator("dt")): _text(item.locator("dd"))
        for item in page.locator("#data-facts > div").all()
    }
    assert (
        facts["Generated"] == "28 Sep 2026 · 08:30 IST Microsoft's articles are checked every hour"
    )
    assert facts["Records"].startswith("59 trains · 30 station window rows")
    assert facts["Schema version"] == "1.1.0"

    index = json.loads(page.request.get(base + "api/index.json").text())
    files = page.locator("#data-files li.data-file")
    assert files.count() == len(index["endpoints"])
    master = page.locator("#data-files li.data-file[data-path='./pqu.json']")
    assert _text(master.locator("h4")) == "PQU master"
    assert _text(master.locator(".data-address code")) == f"{base}api/pqu.json"
    links = {
        str(link.get_attribute("aria-label")): str(link.get_attribute("href"))
        for link in master.locator(".data-links a").all()
    }
    assert links == {
        "PQU master (JSON)": "./api/pqu.json",
        "PQU master (CSV)": "./api/pqu.csv",
        "PQU master (Schema)": "./schemas/pqu.schema.json",
    }
    feed = page.locator("#data-files li.data-file[data-path='./../feed.xml'] .data-links a")
    assert (feed.get_attribute("href"), feed.text_content()) == ("./feed.xml", "Atom")

    # Every link on the page that points into the site resolves.
    hrefs = page.locator("#view a[href^='./']").evaluate_all("links => links.map((a) => a.href)")
    assert len(hrefs) > 40
    for href in sorted(set(hrefs)):
        response = page.request.get(href)
        assert response.status == 200, href

    sources = page.locator("#data-sources tbody tr")
    assert sources.count() == 5
    schedule = page.locator("#data-sources tr[data-source='schedule']")
    assert "Release schedule for proactive quality updates · required" in _text(schedule)
    assert _text(schedule.locator(".source-state")) == "Current"
    # Fixture builds record the commit the harness gives the first sync step.
    commit_id = fixture_commit(0)
    commit = schedule.get_by_role("link", name=commit_id[:7])
    assert commit.get_attribute("href") == f"https://github.com/{REPOSITORY}/commit/{commit_id}"

    calendars = page.locator("#data-calendars li")
    assert calendars.count() == 7
    station = page.locator("#data-calendars li[data-path='./../calendar/station-4.ics']")
    assert _text(station).startswith("PQU Station 4 windows · 10 events")
    subscribe = station.get_by_role("link", name="Subscribe to PQU Station 4 windows")
    assert (
        subscribe.get_attribute("href")
        == "webcal://" + base.split("://", 1)[1] + "calendar/station-4.ics"
    )

    llms = page.locator("#data-more").get_by_role("link", name="llms.txt")
    response = page.request.get(base + "llms.txt")
    assert llms.get_attribute("href") == "./llms.txt"
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert response.text().startswith("# D365 PQU dataset\n")
    opened.assert_clean()


def test_footer_link_opens_the_data_view(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains")
    page = opened.page
    assert page.locator("#data-link").get_attribute("aria-current") is None
    page.locator("#data-link").click()
    page.wait_for_function("() => location.hash === '#/data'")
    wait_for_render(page)
    assert page.evaluate("() => document.activeElement.id") == "data-heading"
    assert page.locator("#data-link").get_attribute("aria-current") == "page"
    page.locator("#tabs a", has_text="Trains").click()
    wait_for_render(page)
    assert page.locator("#data-link").get_attribute("aria-current") is None
    opened.assert_clean()


def test_missing_index_still_shows_the_sources(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/data", routes={"**/api/index.json": 404})
    page = opened.page
    assert _text(page.locator("#data-error")) == "The API index could not be loaded."
    assert page.locator("#data-sources tbody tr").count() == 5
    assert page.locator("#data-files").count() == 0
