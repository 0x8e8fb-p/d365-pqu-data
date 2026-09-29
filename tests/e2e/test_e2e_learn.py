from __future__ import annotations

import pytest

from conftest import E2E_SYNC_AT, FIXTURES, LIVE_FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

REGION_KEY = "d365-pqu-region"
FAQ_BIWEEKLY = "what-is-the-biweekly-cadence-for-pqu"


def _live(fixture_site) -> str:
    return fixture_site((LIVE_FIXTURES, E2E_SYNC_AT))


def _step(page, station: int):
    return page.locator(f"#rollout-steps li.step[data-station='{station}']")


def _window(step, kind: str) -> tuple[str, str]:
    line = step.locator(".step-window", has_text=kind)
    state = line.locator(".window-state")
    return (
        line.locator(".window-dates").inner_text(),
        (state.text_content() or "") if state.count() else "",
    )


def _next_windows(page, geo: str) -> list[str]:
    row = page.locator(f"#maintenance-table tbody tr[data-geo='{geo}']")
    return row.locator(".next-windows li").all_inner_texts()


def test_brief_cards_quote_the_overview_with_links_and_attribution(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/learn")
    page = opened.page
    assert page.locator("#learn-heading").inner_text() == "How proactive quality updates work"
    assert page.locator("#tabs a[aria-current='page']").inner_text() == "Learn"
    cards = page.locator("#brief-cards article")
    assert cards.locator("h3").all_inner_texts() == [
        "What are PQUs?",
        "Why is Microsoft introducing PQUs?",
        "What investments is Microsoft making to enable safe deployments of PQUs?",
    ]
    assert "cumulative builds of hotfixes" in cards.first.inner_text()
    wide = cards.nth(2)
    assert wide.locator("li strong").all_inner_texts() == [
        "Higher-quality concise payloads",
        "Safe deployment rollout process",
        "Fallback via flighting",
    ]
    link = cards.first.get_by_role("link", name="Read on Microsoft Learn")
    assert link.get_attribute("href") == (
        "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/"
        "quality-updates#what-are-pqus"
    )
    assert link.get_attribute("rel") == "noopener noreferrer"
    source = page.locator("#learn-brief > .source-line").inner_text()
    assert source == (
        "Source: Proactive quality updates overview (Microsoft Learn, CC BY 4.0) · "
        "updated 26 Mar 2026"
    )
    license_note = page.locator("#learn-license")
    assert "Converted to structured text" in license_note.inner_text()
    license_link = license_note.get_by_role(
        "link", name="Creative Commons Attribution 4.0 International"
    )
    assert license_link.get_attribute("href") == "https://creativecommons.org/licenses/by/4.0/"
    assert license_link.get_attribute("rel") == "noopener noreferrer"
    opened.assert_clean()


def test_rollout_steps_follow_the_selected_train(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/learn", storage={REGION_KEY: "North Europe"})
    page = opened.page
    assert page.locator("#rollout-train").input_value() == "10.0.48-PQU-6"
    assert page.locator("#rollout-steps li.step").count() == 6
    assert "five days before the start of the PQU train" in (
        page.locator("#rollout-intro").inner_text()
    )
    station_1 = _step(page, 1)
    assert station_1.locator(".step-note").inner_text() == "Only for opted-in environments"
    assert _window(station_1, "Production") == ("N/A", "")
    # 10.0.48 PQU-6 has finished Stations 1 to 3 and is at Station 4 today.
    assert "is-done" in (station_1.get_attribute("class") or "")
    assert "is-done" in (_step(page, 3).get_attribute("class") or "")
    station_4 = _step(page, 4)
    assert "is-yours" in (station_4.get_attribute("class") or "")
    assert "is-current" in (station_4.get_attribute("class") or "")
    assert station_4.locator(".tag-yours").inner_text() == "Your station"
    assert _window(station_4, "Sandbox") == (
        "28 Sep \u2013 1 Oct",
        "Calculated: In progress · day 1 of 4",
    )
    assert _window(station_4, "Production") == (
        "3\u20134 Oct",
        "Calculated: Starts in 5 days",
    )
    station_5 = _step(page, 5)
    assert "is-done" not in (station_5.get_attribute("class") or "")
    assert "is-current" not in (station_5.get_attribute("class") or "")
    station_3 = _step(page, 3)
    assert station_3.locator(".step-regions summary").inner_text() == "11 regions"
    page.locator("#rollout-train").select_option("10.0.47-PQU-13")
    assert _window(_step(page, 4), "Sandbox") == (
        "5\u20138 Oct",
        "Calculated: Starts in 7 days",
    )
    assert page.locator("#rollout-rules .callout").count() == 3
    opened.assert_clean()


def test_maintenance_table_converts_windows_to_the_viewer_zone(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/learn", storage={REGION_KEY: "North Europe"})
    page = opened.page
    rows = page.locator("#maintenance-table tbody tr")
    assert rows.count() == 15
    headers = page.locator("#maintenance-table thead th").all_inner_texts()
    assert headers[4] == "Next windows (Asia/Kolkata)"
    assert _next_windows(page, "Europe") == [
        "Sat 3 Oct 03:30 \u2013 09:30 IST",
        "Sun 4 Oct 03:30 \u2013 09:30 IST",
    ]
    assert _next_windows(page, "India") == [
        "Sat 3 Oct 00:00 \u2013 06:00 IST",
        "Sun 4 Oct 00:00 \u2013 06:00 IST",
    ]
    europe = page.locator("#maintenance-table tbody tr[data-geo='Europe']")
    assert "is-yours" in (europe.get_attribute("class") or "")
    assert europe.locator("td").last.inner_text() == "North Europe, West Europe"
    assert europe.locator("td").nth(0).inner_text() == "Friday and Saturday"
    assert europe.locator("td").nth(2).inner_text() == "Six hours"
    assert "A planned maintenance window typically occurs during the dark hours" in (
        page.locator("#learn-maintenance .section-lead").inner_text()
    )
    experience = page.locator(
        "#maintenance-qa details",
        has_text="What is the experience during the near-zero-downtime maintenance window?",
    )
    experience.locator("summary").click()
    assert experience.locator(".qa-sub h4").all_inner_texts() == [
        "Interactive usage",
        "Batch service",
        "Priority-based scheduling",
    ]
    opened.assert_clean()


def test_maintenance_table_in_another_zone(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/learn", zone="America/Los_Angeles", locale="en-US")
    page = opened.page
    assert _next_windows(page, "Europe") == [
        "Fri 2 Oct 15:00 \u2013 21:00 PDT",
        "Sat 3 Oct 15:00 \u2013 21:00 PDT",
    ]
    assert "Pick your region" in page.locator(".rollout-controls").inner_text()
    opened.assert_clean()


def test_faq_search_filters_questions(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/learn")
    page = opened.page
    items = page.locator("#faq-list details")
    assert items.count() == 29
    status = page.locator("#faq-status")
    assert status.inner_text() == "29 questions from Microsoft's FAQ."
    search = page.locator("#faq-search")
    search.fill("exclusions")
    visible = page.locator("#faq-list details:not([hidden]) summary")
    assert visible.all_inner_texts() == [
        "Can customers request exclusions from the new biweekly cadence?"
    ]
    assert status.inner_text() == "1 of 29 questions match."
    search.fill("  STATION 1 ")
    assert visible.count() >= 3
    search.fill("no such words anywhere")
    assert status.inner_text() == "No questions match."
    search.fill("")
    assert visible.count() == 29
    assert "open a support case" in page.locator("#learn-faq .faq-extra").inner_text()
    assert "sovereign cloud" in page.locator("#faq-intro").inner_text()
    opened.assert_clean()


def test_faq_deep_link_opens_and_focuses_the_answer(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), f"#/learn/faq/{FAQ_BIWEEKLY}")
    page = opened.page
    item = page.locator(f"#faq-{FAQ_BIWEEKLY}")
    assert item.get_attribute("open") is not None
    assert page.locator("#faq-list details[open]").count() == 1
    assert page.evaluate("document.activeElement.textContent") == (
        "What is the biweekly cadence for PQU?"
    )
    assert "two\u2011week cadence" in item.inner_text()
    assert page.title() == "What is the biweekly cadence for PQU? · Learn · D365 PQU Tracker"
    box = item.locator("summary").bounding_box()
    header = page.locator("header.site-header").bounding_box()
    assert box is not None and header is not None
    # Scrolled to the answer and not hidden under the header.
    assert header["y"] + header["height"] <= box["y"] < 400
    link = item.get_by_role("link", name="Open on Microsoft Learn")
    assert link.get_attribute("href") == (
        "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/"
        f"quality-updates-faq#{FAQ_BIWEEKLY}"
    )
    opened.assert_clean()


def test_opening_and_closing_an_answer_updates_the_address(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/learn")
    page = opened.page
    slug = "can-customers-delay-reschedule-or-pause-a-pqu"
    summary = page.locator(f"#faq-{slug} summary")
    summary.click()
    page.wait_for_function(f"() => location.hash === '#/learn/faq/{slug}'")
    assert (
        page.title()
        == "Can customers delay, reschedule, or pause a PQU? · Learn · D365 PQU Tracker"
    )
    summary.click()
    page.wait_for_function("() => location.hash === '#/learn'")
    assert page.title() == "Learn · D365 PQU Tracker"
    page.evaluate(f"location.hash = '#/learn/faq/{FAQ_BIWEEKLY}'")
    wait_for_render(page)
    assert page.locator(f"#faq-{FAQ_BIWEEKLY}").get_attribute("open") is not None
    page.evaluate("location.hash = '#/learn/faq/not-a-real-question'")
    wait_for_render(page)
    assert "That question is not in Microsoft's current FAQ." in (
        page.locator("#learn-faq .inline-alert").inner_text()
    )
    opened.assert_clean()


def test_jump_nav_lands_each_section_at_the_top(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/learn")
    page = opened.page
    for label, section in (("FAQ", "learn-faq"), ("Maintenance windows", "learn-maintenance")):
        page.locator(".jump-nav button", has_text=label).click()
        heading = page.locator(f"#{section}-heading")
        assert page.evaluate("document.activeElement.id") == f"{section}-heading"
        box = heading.bounding_box()
        assert box is not None
        assert 0 <= box["y"] < 300
    opened.assert_clean()


def test_rich_text_renderer_never_creates_markup_or_unsafe_links(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/learn")
    result = opened.page.evaluate(
        """() => {
          const box = document.createElement('div');
          box.append(...PQU.ui.rich.blocks([
            { type: 'paragraph', runs: [
              { text: '<img src=x onerror="window.__pwned=1">' },
              { text: 'script link', href: 'javascript:window.__pwned=2' },
              { text: 'plain http', href: 'http://example.com/' },
              { text: 'data link', href: 'data:text/html,<b>x</b>' },
              { text: 'good', href: 'https://learn.microsoft.com/x', strong: true }
            ] },
            { type: 'list', ordered: true, start: 3, items: [
              [{ type: 'paragraph', runs: [{ text: '<script>window.__pwned=3</script>' }] }]
            ] },
            { type: 'callout', kind: '"><svg onload=alert(1)>', blocks: [
              { type: 'paragraph', runs: [{ text: 'note text' }] }
            ] },
            { type: 'table', header: [[{ text: 'H' }]], rows: [[[{ text: '<b>cell</b>' }]]] },
            { type: 'dataset', name: 'trains' },
            { type: 'unknown', runs: [{ text: 'dropped' }] }
          ]));
          return {
            unsafe: box.querySelectorAll('img, script, svg, b, iframe').length,
            links: [...box.querySelectorAll('a')].map((a) => [a.getAttribute('href'), a.getAttribute('rel'), a.textContent]),
            pwned: window.__pwned || 0,
            text: box.textContent,
            olStart: box.querySelector('ol').getAttribute('start'),
            calloutLabel: box.querySelector('.callout-label').textContent
          };
        }"""
    )
    assert result["unsafe"] == 0
    assert result["links"] == [["https://learn.microsoft.com/x", "noopener noreferrer", "good"]]
    assert result["pwned"] == 0
    assert '<img src=x onerror="window.__pwned=1">' in result["text"]
    assert "<b>cell</b>" in result["text"]
    assert "dropped" not in result["text"]
    assert result["olStart"] == "3"
    assert result["calloutLabel"] == "Note"
    opened.assert_clean()


def test_learn_page_without_optional_articles(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((FIXTURES / "source-minimal.md", E2E_SYNC_AT)), "#/learn")
    page = opened.page
    assert "“Proactive quality updates overview” is not part of this dataset." in (
        page.locator("#learn-brief").inner_text()
    )
    assert "“Proactive quality updates FAQ” is not part of this dataset." in (
        page.locator("#learn-faq").inner_text()
    )
    assert "maintenance windows are not available in this dataset" in (
        page.locator("#learn-maintenance").inner_text()
    )
    assert page.locator("#rollout-steps li.step").count() == 6
    assert page.locator("#rollout-train").input_value() == "10.0.48-PQU-6"
    assert page.locator("#rollout-rules .callout").count() == 1
    opened.assert_clean()


def test_learn_document_failure_keeps_dataset_parts(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/learn", routes={"**/api/learn.json": 500})
    page = opened.page
    assert "Microsoft's Learn content could not be loaded." in (
        page.locator(".learn > .inline-alert").inner_text()
    )
    assert page.locator("#maintenance-table tbody tr").count() == 15
    assert page.locator("#rollout-steps li.step").count() == 6
    assert page.locator("#learn-license").count() == 0


def _cell(page, category: str, group: str, column: int) -> tuple[str, str]:
    row = page.locator(f"#insight-table-{category} tbody tr[data-group='{group}']")
    cell = row.locator("td").nth(column)
    note = cell.locator(".cell-note")
    return (
        cell.locator(".cell-value").inner_text(),
        note.inner_text() if note.count() else "",
    )


def test_what_the_data_says_shows_calculated_figures_next_to_the_faq(
    fixture_site, open_page
) -> None:
    opened = open_page(_live(fixture_site), "#/learn")
    page = opened.page
    order = page.locator(".learn-body > .learn-section").evaluate_all(
        "nodes => nodes.map(n => n.id)"
    )
    assert order == [
        "learn-brief",
        "learn-rollout",
        "learn-maintenance",
        "learn-insights",
        "learn-faq",
    ]
    assert page.locator(".jump-nav button").all_inner_texts() == [
        "In brief",
        "Rollouts",
        "Maintenance windows",
        "What the data says",
        "FAQ",
    ]
    figures = page.locator("#insight-highlights .figure-item")
    assert figures.locator(".figure-value").all_inner_texts() == ["14 days", "5 days", "91 days"]
    assert (
        figures.first.locator(".figure-title").text_content()
        == "Days between train starts · 10.0.49"
    )
    assert figures.first.locator(".figure-summary").inner_text() == (
        "10.0.49: a new train starts every 14 days, or 2 weeks "
        "(median of 16 intervals; range 14\u201321 days)."
    )
    assert (
        "Microsoft doesn't publish them" in page.locator("#learn-insights .calc-note").inner_text()
    )

    assert _cell(page, "trains", "10.0.46", 0) == ("28 days", "6 intervals, 28\u201335 days")
    assert _cell(page, "trains", "10.0.47", 0) == ("14 days", "16 intervals, 14\u201321 days")
    assert _cell(page, "trains", "10.0.47", 1) == ("0 days", "17 trains")
    assert _cell(page, "trains", "10.0.47", 3) == ("17 trains", "")
    assert _cell(page, "stations", "station-4", 0) == ("12 days", "5 trains, 12\u201314 days")
    assert page.locator("#insights-stations .insight-lead").inner_text() == (
        "Production updates start a median of 5 days after sandbox updates "
        "(25 station windows; range 5\u201312 days)."
    )
    service = page.locator("#insights-service-updates .insight-list > div")
    assert service.first.locator("dt").inner_text() == "Days between general availability dates"
    assert service.first.locator("dd").inner_text() == "91 days\n6 intervals, 77\u2013105 days"

    method = page.locator("#insights-trains .insight-method")
    assert method.get_attribute("open") is None
    method.locator("summary").click()
    left_out = method.locator(".left-out li").all_inner_texts()
    assert left_out[0] == (
        "Left out 10.0.46-PQU-1: Source warning: Change cutoff 2026-02-04 and train start "
        "2025-02-09 are in different years"
    )
    stations_method = page.locator("#insights-stations .insight-method")
    stations_method.locator("summary").click()
    assert "Left out Station 1: Only for opted-in environments" in (stations_method.inner_text())
    source = page.locator("#insights-service-updates .source-line")
    assert source.inner_text() == (
        "Calculated from Service update availability (updated 4 Jun 2026)."
    )
    assert source.locator("a").get_attribute("href") == (
        "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/"
        "public-preview-releases"
    )
    opened.assert_clean()


def test_figures_from_a_schedule_only_dataset(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((FIXTURES / "source-minimal.md", E2E_SYNC_AT)), "#/learn")
    page = opened.page
    figures = page.locator("#insight-highlights .figure-item")
    assert figures.locator(".figure-value").all_inner_texts() == ["14 days", "5 days"]
    assert figures.nth(1).locator(".figure-summary").inner_text() == (
        "Production updates start a median of 5 days after sandbox updates (10 station windows)."
    )
    assert page.locator("#insights-service-updates").count() == 0
    assert _cell(page, "trains", "10.0.48", 0) == ("14 days", "2 intervals")
    opened.assert_clean()


def test_missing_figures_document_is_reported(fixture_site, open_page) -> None:
    opened = open_page(_live(fixture_site), "#/learn", routes={"**/api/insights.json": 404})
    page = opened.page
    assert page.locator("#learn-insights .inline-alert").inner_text() == (
        "The calculated figures could not be loaded."
    )
    assert page.locator("#faq-list details").count() == 29
