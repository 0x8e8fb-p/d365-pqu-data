from __future__ import annotations

import pytest

from conftest import E2E_SYNC_AT, FIXTURES, LIVE_FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

REGION_KEY = "d365-pqu-region"
MINIMAL = FIXTURES / "source-minimal.md"
UPDATED = FIXTURES / "source-updated.md"
UPDATED_AT = "2026-09-28T03:30:00Z"


def _live(fixture_site) -> str:
    return fixture_site((LIVE_FIXTURES, E2E_SYNC_AT))


def _text(locator) -> str:
    return " ".join((locator.text_content() or "").split())


def test_train_page_deep_link(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/train/10.0.48-PQU-6")
    page = opened.page
    assert page.title() == "10.0.48 PQU-6 · PQU Console"
    assert page.locator("#train-heading").text_content() == "10.0.48 PQU-6"
    assert page.locator("#tabs a[aria-current]").text_content() == "Trains"
    badges = _text(page.locator(".train-badges"))
    assert "In-Progress" in badges
    assert "New" in badges
    assert "Newest active train" in badges
    assert _text(page.locator("#train-phase")).endswith(
        "Day 13 of 25 · Now: Station 4 sandbox (28 Sep \u2013 1 Oct)"
    )

    facts = page.locator("#train-facts > div")
    by_label = {_text(item.locator("dt")): _text(item.locator("dd")) for item in facts.all()}
    assert by_label["Change cutoff"] == "Wed 16 Sep 2026 12 days ago"
    assert by_label["Train"] == "Wed 16 Sep \u2013 Sat 10 Oct 25 days"
    assert by_label["Application build"] == "10.0.2645.136 Newest build published for 10.0.48"
    assert by_label["Platform build"] == "7.0.7996.119"
    assert by_label["UEP version"] == "10.0.48.7"
    assert by_label["Version 10.0.48"].startswith("Supported End of service in 141 days")

    chart = page.locator("#rollout-chart")
    assert chart.locator(".rollout-row[data-station]").count() == 6
    assert chart.locator(".rollout-row[data-station='1'] .rollout-bar").count() == 1
    assert chart.locator(".rollout-row[data-station='4'] .bar-sandbox.bar-current").count() == 1
    assert chart.locator(".rollout-row[data-station='4'] .bar-production.bar-upcoming").count() == 1
    assert chart.locator(".rollout-row[data-station='2'] .bar-done").count() == 2
    assert chart.locator(".rollout-today").count() == 1
    label = chart.locator(".rollout-plot").get_attribute("aria-label") or ""
    assert label.startswith(
        "Station rollout for 10.0.48 PQU-6, 16 Sep \u2013 11 Oct 2026. Today is 28 Sep 2026."
    )

    row = page.locator("#station-table tbody tr[data-station='4']")
    assert (
        _text(row.locator("td").nth(0))
        == "Mon 28 Sep \u2013 Thu 1 Oct Calculated: In progress · day 1 of 4"
    )
    assert (
        _text(row.locator("td").nth(1)) == "Sat 3 Oct \u2013 Sun 4 Oct Calculated: Starts in 5 days"
    )
    assert _text(page.locator("#station-table tbody tr[data-station='1'] td").nth(1)) == "N/A"

    siblings = page.locator(".train-siblings a")
    assert siblings.nth(0).get_attribute("href") == "#/train/10.0.48-PQU-5"
    assert siblings.nth(1).get_attribute("href") == "#/train/10.0.48-PQU-7"

    source = page.locator("#train-source")
    article = source.get_by_role("link", name="Release schedule for proactive quality updates")
    assert (article.get_attribute("href") or "").endswith(
        "quality-updates-schedule#high-level-pqu-train-schedule"
    )
    raw = source.locator("a[href^='https://raw.githubusercontent.com/MicrosoftDocs/']")
    assert raw.count() == 1
    assert _text(raw).startswith("Markdown at commit ")
    assert (
        "No changes recorded since this dataset first saw the train on 28 Sep 2026 · 08:30 IST."
        in _text(page.locator("#train-changes"))
    )
    opened.assert_clean()


def test_trains_table_links_to_the_train_page(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/trains?version=10.0.48")
    page = opened.page
    toggle = page.get_by_role("button", name="Expand station windows for 10.0.48-PQU-6")
    toggle.click()
    assert page.locator("#pqu-table .station-detail").count() == 1
    page.locator("#pqu-table").get_by_role("link", name="10.0.48-PQU-6", exact=True).click()
    page.wait_for_function("() => location.hash === '#/train/10.0.48-PQU-6'")
    wait_for_render(page)
    assert page.evaluate("document.activeElement.id") == "train-heading"
    crumb = page.locator(".crumbs a")
    assert crumb.get_attribute("href") == "#/trains?version=10.0.48"
    crumb.click()
    page.wait_for_function("() => location.hash === '#/trains?version=10.0.48'")
    wait_for_render(page)
    assert page.locator("#version-filter").input_value() == "10.0.48"
    opened.assert_clean()


def test_saved_region_station_is_highlighted(fixture_site, open_page) -> None:
    opened = open_page(
        _live(fixture_site), "#/train/10.0.48-PQU-6", storage={REGION_KEY: "North Europe"}
    )
    page = opened.page
    assert _text(page.locator("#train-your-station")).startswith(
        "North Europe (your region) is on Station 4."
    )
    assert page.locator("#station-table tr.is-yours").get_attribute("data-station") == "4"
    assert "Your station" in _text(page.locator("#station-table tr.is-yours"))
    assert page.locator("#rollout-chart .rollout-row.is-yours").get_attribute("data-station") == "4"
    opened.assert_clean()


def test_train_changes_after_an_update(fixture_site, open_page) -> None:
    base = fixture_site((MINIMAL, E2E_SYNC_AT), (UPDATED, UPDATED_AT))
    opened = open_page(base, "#/train/10.0.48-PQU-6")
    page = opened.page
    changes = page.locator("#train-change-list li.change")
    assert [_text(item) for item in changes.all()] == [
        "Platform build changed from 7.0.7996.119 to 7.0.7996.130",
        "UEP version changed from 10.0.48.7 to 10.0.48.8",
    ]
    when = page.locator("#train-change-list .change-when")
    assert _text(when).startswith("28 Sep 2026 · 09:00 IST · Microsoft commit ")
    commit = when.locator("a")
    assert (commit.get_attribute("href") or "").startswith(
        "https://github.com/MicrosoftDocs/dynamics-365-unified-operations-public/commit/"
    )

    page.locator(".train-siblings a[rel='prev']").click()
    page.wait_for_function("() => location.hash === '#/train/10.0.48-PQU-5'")
    wait_for_render(page)
    assert [_text(item) for item in page.locator("#train-change-list li.change").all()] == [
        "Status changed from In-Progress to Completed",
        "UEP version removed (was 10.0.48.6)",
        "Station schedule changed from published to not published",
        "Schedules removed for Stations 1, 2, 3, 4, 5 and 6",
    ]
    assert page.locator("#no-stations").count() == 1
    assert page.locator("#rollout-chart").count() == 0
    opened.assert_clean()


def test_unknown_and_differently_cased_train_ids(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/train/10.0.99-PQU-1")
    page = opened.page
    assert page.title() == "Train not found · PQU Console"
    assert page.locator("#train-heading").text_content() == "Train not found"
    assert (
        _text(page.locator("#train-missing"))
        == "“10.0.99-PQU-1” is not in Microsoft's current schedule."
    )
    link = page.get_by_role("link", name="Search all trains")
    assert link.get_attribute("href") == "#/trains?q=10.0.99-PQU-1"

    page.evaluate("location.hash = '#/train/10.0.48-pqu-6'")
    page.wait_for_function("() => location.hash === '#/train/10.0.48-PQU-6'")
    wait_for_render(page)
    assert page.locator("#train-heading").text_content() == "10.0.48 PQU-6"
    opened.assert_clean()


def test_find_my_build(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/versions")
    page = opened.page
    field = page.locator("#build-input")
    assert field.get_attribute("placeholder") == "For example 10.0.2645.136"
    result = page.locator("#build-result")

    def find(value: str) -> str:
        field.fill(value)
        page.locator("#build-form button[type='submit']").click()
        return _text(result.locator(".build-headline"))

    assert find("10.0.2527.160") == "10.0.47 PQU-8 · 5 newer builds published"
    assert page.evaluate("location.hash") == "#/versions?build=10.0.2527.160"
    assert "Newest 10.0.47 build published: 10.0.2527.215 (10.0.47 PQU-13)." in _text(result)
    assert result.locator(".build-headline a").get_attribute("href") == "#/train/10.0.47-PQU-8"

    assert find("7.0.7858.134") == "10.0.47 PQU-8 · 5 newer builds published"
    assert "7.0.7858.134 is the platform build of 10.0.47 PQU-8" in _text(result)
    assert (
        find("10.0.2527.170")
        == "Between 10.0.47 PQU-8 and 10.0.47 PQU-9 · 5 newer builds published"
    )
    assert find("10.0.2527.215") == "10.0.47 PQU-13 · No newer build published"
    assert find("10.0.2527.300") == "Newer than every 10.0.47 build listed"
    assert find("10.0.1999.5") == "No train in Microsoft's schedule uses build line 10.0.1999"
    assert "10.0.46 (10.0.2428.x), 10.0.47 (10.0.2527.x) and 10.0.48 (10.0.2645.x)" in _text(result)

    field.fill("10.0.2527")
    page.locator("#build-form button[type='submit']").click()
    assert _text(result.locator(".build-invalid")) == (
        "Enter a four-part build number, for example 10.0.2645.136 (application) "
        "or 7.0.7996.119 (platform)."
    )
    opened.assert_clean()


def test_build_deep_link_focuses_the_version(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/versions?build=10.0.2527.160&version=10.0.47")
    page = opened.page
    assert page.locator("#build-input").input_value() == "10.0.2527.160"
    assert _text(page.locator("#build-result .build-headline")) == (
        "10.0.47 PQU-8 · 5 newer builds published"
    )
    assert "is-target" in (page.locator("#version-10-0-47").get_attribute("class") or "")
    assert page.evaluate("document.activeElement.id") == "version-10-0-47-title"
    opened.assert_clean()
