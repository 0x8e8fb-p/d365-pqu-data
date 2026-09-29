from __future__ import annotations

import pytest

from conftest import E2E_SYNC_AT, FIXTURES, LIVE_FIXTURES

pytestmark = pytest.mark.e2e

FOOTNOTE = FIXTURES / "source-footnote.md"


def _row(page, pqu_id: str):
    return page.locator("#pqu-table tbody tr", has_text=pqu_id).first


def test_rules_panel_quotes_microsoft_callouts_with_source(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((LIVE_FIXTURES, E2E_SYNC_AT)), "#/trains")
    page = opened.page
    note = page.locator("#train-table-note").inner_text()
    assert note.startswith("The following table shows the high-level train schedule.")
    panel = page.locator("#rules-panel")
    summary = panel.locator("summary").inner_text()
    assert "Microsoft's rollout rules" in summary
    assert "3 notes · updated 21 Sep 2026" in summary
    assert panel.get_attribute("open") is None
    panel.locator("summary").click()
    body = panel.locator(".rules-body")
    assert body.locator(".callout").count() == 3
    assert [label.inner_text() for label in body.locator(".callout-label").all()] == [
        "Important",
        "Note",
        "Important",
    ]
    text = body.inner_text()
    assert "receive PQUs on weekends" in text
    assert "schedule shows a range of four days" in text
    assert body.locator(".callout").first.locator("ol > li").count() == 3
    source = panel.locator(".rules-source a")
    assert source.inner_text() == "Release schedule for proactive quality updates"
    assert source.get_attribute("href") == (
        "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/"
        "quality-updates-schedule"
    )
    assert source.get_attribute("rel") == "noopener noreferrer"
    opened.assert_clean()


def test_new_station_schedules_are_marked(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((LIVE_FIXTURES, E2E_SYNC_AT)), "#/trains?status=On-Going")
    page = opened.page
    marked = sorted(
        row.locator("a.train-id").inner_text()
        for row in page.locator("#pqu-table tbody tr", has=page.locator(".tag-new")).all()
    )
    assert marked == ["10.0.46-PQU-8", "10.0.47-PQU-13", "10.0.48-PQU-6"]
    assert _row(page, "10.0.48-PQU-5").locator(".tag-new").count() == 0
    opened.assert_clean()


def test_status_footnote_is_shown_under_the_status(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((FOOTNOTE, E2E_SYNC_AT)), "#/trains")
    page = opened.page
    cell = _row(page, "10.0.47-PQU-2").locator("td.status-cell")
    assert cell.locator(".status").inner_text() == "Canceled"
    assert cell.locator(".status-note").inner_text() == (
        "Microsoft note: PQU will occur only on Station-1. Releases for other stations have been "
        "canceled due to the holiday deployment freeze, and the build will be available for "
        "manual uptake."
    )
    assert page.locator("#health-toggle").get_attribute("data-state") == "healthy"
    opened.assert_clean()


def test_missing_learn_document_hides_notes_with_a_message(fixture_site, open_page) -> None:
    opened = open_page(
        fixture_site((LIVE_FIXTURES, E2E_SYNC_AT)), "#/trains", routes={"**/api/learn.json": 404}
    )
    page = opened.page
    assert page.locator("#rules-panel").count() == 0
    assert "schedule notes could not be loaded" in page.locator(".inline-alert").inner_text()
    assert page.locator("#pqu-table tbody tr").count() == 20
