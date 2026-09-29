from __future__ import annotations

import pytest

from conftest import E2E_SYNC_AT, FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

MINIMAL = FIXTURES / "source-minimal.md"
UPDATED = FIXTURES / "source-updated.md"
# Same steps as the train page tests, so the session builds this site once.
UPDATED_AT = "2026-09-28T03:30:00Z"
REPOSITORY = "MicrosoftDocs/dynamics-365-unified-operations-public"
PQU5_LINES = [
    "Status changed from In-Progress to Completed",
    "UEP version removed (was 10.0.48.6)",
    "Station schedule changed from published to not published",
    "Schedules removed for Stations 1, 2, 3, 4, 5 and 6",
]


def _updated(fixture_site) -> str:
    return fixture_site((MINIMAL, E2E_SYNC_AT), (UPDATED, UPDATED_AT))


def _text(locator) -> str:
    return " ".join((locator.text_content() or "").split())


def _subjects(page) -> list[str]:
    return [
        str(item.get_attribute("data-subject"))
        for item in page.locator("#change-days .change-subject").all()
    ]


def _lines(page, subject: str) -> list[str]:
    group = page.locator(f"#change-days .change-subject[data-subject='{subject}']")
    return [_text(item) for item in group.locator("li.change").all()]


def test_changes_are_grouped_by_day_check_and_subject(fixture_site, open_page) -> None:
    opened = open_page(_updated(fixture_site), "#/changes")
    page = opened.page
    assert page.title() == "Changes · D365 PQU Tracker"
    assert page.locator("#tabs a[aria-current='page']").text_content() == "Changes"
    assert _text(page.locator("#changes-summary")) == (
        "10 changes found in 1 check since tracking began on 28 Sep 2026 · 08:30 IST."
    )
    assert "checked every hour" in _text(page.locator(".changes-method"))

    days = page.locator("#change-days li.change-day")
    assert days.count() == 1
    assert days.first.get_attribute("data-day") == "2026-09-28"
    assert _text(days.first.locator(".change-day-title")) == "Mon 28 Sep 2026 · today"
    when = page.locator("#change-days .change-when")
    assert _text(when).startswith("09:00 IST · Microsoft commit ")
    commit = when.locator("a")
    assert (commit.get_attribute("href") or "").startswith(
        f"https://github.com/{REPOSITORY}/commit/"
    )

    article = "Release schedule for proactive quality updates"
    assert _subjects(page) == ["10.0.48 PQU-5", "10.0.48 PQU-6", "10.0.48 PQU-7", article]
    assert _lines(page, "10.0.48 PQU-5") == PQU5_LINES
    assert _lines(page, "10.0.48 PQU-7") == [
        "Application build published: 10.0.2645.140",
        "Platform build published: 7.0.7996.135",
    ]
    assert _lines(page, article) == [
        "Section \u201cMore information\u201d removed",
        "Microsoft updated the text of \u201cDetailed station schedules\u201d · Read on Microsoft Learn",
    ]
    removed = page.locator(".change-subject[data-subject='10.0.48 PQU-5'] li.change").nth(3)
    assert "change-removed" in (removed.get_attribute("class") or "")
    assert len((removed.get_attribute("data-change") or "").split()) == 6

    guidance = page.locator(f".change-subject[data-subject='{article}']")
    assert (guidance.locator(".change-subject-link").get_attribute("href") or "").endswith(
        "/get-started/quality-updates-schedule"
    )
    learn = guidance.get_by_role("link", name="Read on Microsoft Learn")
    assert (learn.get_attribute("href") or "").endswith("quality-updates-schedule#schedule")

    feed = page.locator(".changes a.feed-link")
    assert feed.get_attribute("href") == "./feed.xml"
    head = page.locator("link[rel='alternate'][type='application/atom+xml']")
    assert head.get_attribute("href") == "./feed.xml"

    page.locator(".change-subject[data-subject='10.0.48 PQU-6'] a.change-subject-link").click()
    page.wait_for_function("() => location.hash === '#/train/10.0.48-PQU-6'")
    wait_for_render(page)
    assert page.locator("#train-heading").text_content() == "10.0.48 PQU-6"
    opened.assert_clean()


def test_days_and_times_follow_the_viewer_time_zone(fixture_site, open_page) -> None:
    opened = open_page(
        _updated(fixture_site), "#/changes", zone="America/Los_Angeles", locale="en-US"
    )
    page = opened.page
    day = page.locator("#change-days li.change-day")
    # 03:30 UTC on 28 Sep is 20:30 on 27 Sep in Los Angeles, which is still today there.
    assert day.get_attribute("data-day") == "2026-09-27"
    assert _text(day.locator(".change-day-title")) == "Sun 27 Sep 2026 · today"
    assert _text(page.locator("#change-days .change-when")).startswith("20:30 PDT")
    assert "Times are shown in America/Los Angeles." in _text(page.locator(".changes-method"))
    opened.assert_clean()


def test_filters_narrow_the_list_and_live_in_the_url(fixture_site, open_page) -> None:
    opened = open_page(_updated(fixture_site), "#/changes")
    page = opened.page
    options = page.locator("#changes-kind option").all_text_contents()
    assert options == [
        "All changes (10)",
        "Trains (7)",
        "Station schedules (1)",
        "Microsoft guidance (2)",
    ]

    page.locator("#changes-kind").select_option("guidance")
    page.wait_for_function("() => location.hash === '#/changes?kind=guidance'")
    assert _subjects(page) == ["Release schedule for proactive quality updates"]
    assert _text(page.locator("#changes-status")) == "2 changes of 10 match."

    page.locator("#changes-kind").select_option("")
    page.locator("#changes-search").fill("pqu-7")
    page.wait_for_function("() => location.hash === '#/changes?q=pqu-7'")
    assert _subjects(page) == ["10.0.48 PQU-7"]
    assert _text(page.locator("#changes-status")) == "2 changes of 10 match."

    page.locator("#changes-search").fill("stations 1, 2")
    assert _lines(page, "10.0.48 PQU-5") == [PQU5_LINES[3]]

    page.locator("#changes-search").fill("no such change")
    assert _text(page.locator("#changes-none")) == (
        "No changes match these filters. Show all changes"
    )
    page.get_by_role("button", name="Show all changes").click()
    page.wait_for_function("() => location.hash === '#/changes'")
    assert page.evaluate("document.activeElement.id") == "changes-kind"
    assert page.locator("#changes-search").input_value() == ""
    assert _text(page.locator("#changes-status")) == ""
    assert len(_subjects(page)) == 4
    opened.assert_clean()


def test_deep_links_restore_filters(fixture_site, open_page) -> None:
    opened = open_page(_updated(fixture_site), "#/changes?kind=pqu&q=PQU-6")
    page = opened.page
    assert page.locator("#changes-kind").input_value() == "pqu"
    assert page.locator("#changes-search").input_value() == "PQU-6"
    assert _subjects(page) == ["10.0.48 PQU-6"]
    assert _lines(page, "10.0.48 PQU-6") == [
        "Platform build changed from 7.0.7996.119 to 7.0.7996.130",
        "UEP version changed from 10.0.48.7 to 10.0.48.8",
    ]

    page.evaluate("location.hash = '#/changes?kind=bogus'")
    page.wait_for_function(
        "() => document.querySelector('#view').dataset.renderedHash.includes('bogus')"
    )
    assert page.locator("#changes-kind").input_value() == ""
    assert len(_subjects(page)) == 4
    opened.assert_clean()


def test_a_new_history_says_nothing_has_changed_yet(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((MINIMAL, E2E_SYNC_AT)), "#/changes")
    page = opened.page
    assert _text(page.locator("#changes-summary")) == (
        "No changes detected since tracking began on 28 Sep 2026 · 08:30 IST."
    )
    assert page.locator("#changes-kind").count() == 0
    assert page.locator("#change-days").count() == 0
    opened.assert_clean()


def test_a_missing_history_is_reported(fixture_site, open_page) -> None:
    opened = open_page(_updated(fixture_site), "#/changes", routes={"**/api/changes.json": 404})
    page = opened.page
    assert _text(page.locator("#changes-error")) == "The change history could not be loaded."
    assert page.locator("#change-days").count() == 0


def test_health_panel_links_to_the_changes(fixture_site, open_page) -> None:
    opened = open_page(_updated(fixture_site), "#/")
    page = opened.page
    page.locator("#health-toggle").click()
    page.locator("#health-panel").get_by_role("link", name="See changes").click()
    page.wait_for_function("() => location.hash === '#/changes'")
    wait_for_render(page)
    assert not page.locator("#health-panel").is_visible()
    assert page.evaluate("document.activeElement.id") == "changes-heading"
    opened.assert_clean()
