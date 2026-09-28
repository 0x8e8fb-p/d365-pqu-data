from __future__ import annotations

import re

import pytest

from conftest import E2E_SYNC_AT, FIXTURES, LIVE_FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

MINIMAL = FIXTURES / "source-minimal.md"
BROKEN = FIXTURES / "source-broken.md"


def test_pill_reports_up_to_date_when_recently_checked(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((MINIMAL, E2E_SYNC_AT)))
    page = opened.page
    pill = page.locator("#health-toggle")
    assert pill.get_attribute("data-state") == "healthy"
    assert page.locator("#sync-label").inner_text() == "Up to date"
    assert page.locator("#sync-time").inner_text() == "checked 1 h ago"
    assert page.locator("#health-status").inner_text() == "Data status: Up to date"
    pill.click()
    panel = page.locator("#health-panel").inner_text()
    assert "Check schedule\nevery hour" in panel
    assert "Dataset last changed\n28 Sep 2026 · 08:30 IST · 1 h ago" in panel
    assert "Last successful check" not in panel
    opened.assert_clean()


def test_pill_reports_a_failed_check_and_keeps_the_last_dataset(fixture_site, open_page) -> None:
    base = fixture_site((MINIMAL, E2E_SYNC_AT), (BROKEN, "2026-09-28T03:45:00Z", "fail"))
    opened = open_page(base, "#/trains")
    page = opened.page
    assert page.locator("#health-toggle").get_attribute("data-state") == "failed"
    assert page.locator("#sync-label").inner_text() == "Last check failed"
    assert page.locator("#sync-time").inner_text() == "checked 15 min ago"
    page.locator("#health-toggle").click()
    panel = page.locator("#health-panel").inner_text()
    assert "Last successful check\n28 Sep 2026 · 08:30 IST · 1 h ago" in panel
    assert "The last valid dataset is still shown." in panel
    assert "ParserError: High-level PQU train table headers changed" in panel
    assert page.locator("#pqu-table tbody tr").count() == 4
    opened.assert_clean()


def test_pill_reports_source_warnings_and_flags_the_row(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((LIVE_FIXTURES, E2E_SYNC_AT)), "#/trains")
    page = opened.page
    assert page.locator("#health-toggle").get_attribute("data-state") == "warnings"
    assert page.locator("#sync-label").inner_text() == "1 source warning"
    flag = page.locator("#pqu-table tbody tr.has-flag .flag")
    assert flag.count() == 1
    label = flag.get_attribute("aria-label") or ""
    assert label.startswith("Source warning: Microsoft lists the start as 9 Feb 2025")
    assert "4 Feb 2026" in label
    assert "10.0.46-PQU-1" in page.locator("#pqu-table tbody tr.has-flag").inner_text()

    page.locator("#health-toggle").click()
    panel = page.locator("#health-panel")
    assert panel.is_visible()
    assert page.locator("#health-toggle").get_attribute("aria-expanded") == "true"
    text = panel.text_content() or ""
    assert "Source warnings (1)" in text
    assert "the years differ" in text
    assert "Microsoft article updated" in text
    assert "21 Sep 2026" in text
    page.keyboard.press("Escape")
    assert not panel.is_visible()
    opened.assert_clean()


def test_warning_link_opens_the_affected_train(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((LIVE_FIXTURES, E2E_SYNC_AT)))
    page = opened.page
    page.locator("#health-toggle").click()
    page.get_by_role("link", name="Show 10.0.46-PQU-1").click()
    page.wait_for_function("() => location.hash === '#/train/10.0.46-PQU-1'")
    wait_for_render(page)
    assert page.locator("#train-heading").text_content() == "10.0.46 PQU-1"
    flag = page.locator(".train-flag").text_content() or ""
    assert "Source warning:" in flag
    assert "the years differ" in flag
    assert not page.locator("#health-panel").is_visible()
    opened.assert_clean()


def test_pill_reports_stale_after_three_missed_checks(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((MINIMAL, E2E_SYNC_AT)), now="2026-09-29T12:00:00Z")
    page = opened.page
    assert page.locator("#health-toggle").get_attribute("data-state") == "stale"
    assert page.locator("#sync-label").inner_text() == "Stale"
    page.locator("#health-toggle").click()
    text = page.locator("#health-panel").inner_text()
    assert "No successful check in the last 33 hours" in text
    assert re.search(r"Checks are scheduled every \d+ (hours|minutes)|every hour", text)
    opened.assert_clean()


def test_pill_reports_unavailable_when_dataset_fails_to_load(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((MINIMAL, E2E_SYNC_AT)), routes={"**/api/pqu.json": 503})
    page = opened.page
    assert page.locator("#health-toggle").get_attribute("data-state") == "unavailable"
    assert page.locator("#sync-label").inner_text() == "Unavailable"
    banner = page.locator("#load-error")
    assert banner.is_visible()
    assert "503" in banner.inner_text()
    assert page.locator("#pqu-table").count() == 0


def test_missing_optional_document_only_disables_its_feature(fixture_site, open_page) -> None:
    opened = open_page(
        fixture_site((MINIMAL, E2E_SYNC_AT)), "#/trains", routes={"**/api/stations.json": 404}
    )
    page = opened.page
    assert page.locator("#pqu-table tbody tr").count() == 4
    assert "Station schedules could not be loaded" in page.locator(".inline-alert").inner_text()
    assert page.locator("#health-toggle").get_attribute("data-state") == "healthy"
    page.locator("#health-toggle").click()
    assert "Could not load: station schedules." in page.locator("#health-panel").inner_text()
