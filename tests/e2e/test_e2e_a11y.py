"""Accessibility audit of every view: names, references, headings, landmarks and focus.

A dependency-free check of the WCAG failures a DOM can show: controls and links without an
accessible name, references to missing ids, duplicate ids, skipped heading levels, images
without a text alternative, tables without captions, and interactive elements nested inside
each other.
"""

from __future__ import annotations

import pytest

from conftest import E2E_SYNC_AT, LIVE_FIXTURES, wait_for_render

pytestmark = pytest.mark.e2e

REGION_KEY = "d365-pqu-region"
AUDIT = """() => {
  const problems = [];
  const byId = (id) => document.getElementById(id);
  const visible = (node) => Boolean(node.offsetWidth || node.offsetHeight || node.getClientRects().length);
  const short = (node) => node.outerHTML.replace(/\\s+/g, " ").slice(0, 90);

  const counts = new Map();
  for (const node of document.querySelectorAll("[id]")) {
    counts.set(node.id, (counts.get(node.id) || 0) + 1);
  }
  for (const [id, count] of counts) {
    if (count > 1) problems.push(`duplicate id #${id}`);
  }
  for (const attribute of ["aria-labelledby", "aria-describedby", "aria-controls"]) {
    for (const node of document.querySelectorAll(`[${attribute}]`)) {
      for (const id of node.getAttribute(attribute).split(/\\s+/).filter(Boolean)) {
        if (!byId(id)) problems.push(`${attribute} points to missing #${id}`);
      }
    }
  }
  const nameOf = (node) => {
    const labelledBy = node.getAttribute("aria-labelledby");
    if (labelledBy) {
      return labelledBy.split(/\\s+/).map((id) => (byId(id) || {}).textContent || "").join(" ").trim();
    }
    const label = (node.getAttribute("aria-label") || "").trim();
    if (label) return label;
    if (node.labels && node.labels.length) {
      return [...node.labels].map((item) => item.textContent || "").join(" ").trim();
    }
    const content = (node.textContent || "").trim();
    if (content && !["INPUT", "SELECT", "TEXTAREA"].includes(node.tagName)) return content;
    return (node.getAttribute("title") || "").trim();
  };
  for (const node of document.querySelectorAll("a[href], button, input, select, textarea, summary, [role='button']")) {
    if (!visible(node) || node.type === "hidden") continue;
    if (!nameOf(node)) problems.push(`no accessible name: ${short(node)}`);
  }
  for (const node of document.querySelectorAll("img")) {
    if (!node.hasAttribute("alt")) problems.push(`img without alt: ${short(node)}`);
  }
  for (const node of document.querySelectorAll("svg")) {
    const hidden = node.closest("[aria-hidden='true']");
    const labelled = node.getAttribute("role") === "img" && (node.getAttribute("aria-label") || node.getAttribute("aria-labelledby"));
    if (!hidden && !labelled) problems.push(`svg without text alternative: ${short(node)}`);
  }
  for (const node of document.querySelectorAll("[role='img']")) {
    if (!node.getAttribute("aria-label") && !node.getAttribute("aria-labelledby")) problems.push(`role=img without a name: ${short(node)}`);
  }
  for (const node of document.querySelectorAll("a a, a button, button a, button button, summary a, summary button, a input, button input")) {
    problems.push(`interactive element inside another: ${short(node)}`);
  }
  for (const table of document.querySelectorAll("table")) {
    if (!table.querySelector("caption") && !table.getAttribute("aria-label") && !table.getAttribute("aria-labelledby")) {
      problems.push(`table without a caption: ${table.id || short(table)}`);
    }
  }
  const h1 = [...document.querySelectorAll("h1")].filter(visible);
  if (h1.length !== 1) problems.push(`${h1.length} visible h1 elements`);
  let level = 1;
  for (const heading of document.querySelectorAll("main h2, main h3, main h4, main h5, main h6")) {
    if (!visible(heading)) continue;
    const next = Number(heading.tagName[1]);
    if (next > level + 1) problems.push(`heading jumps from h${level} to h${next}: ${heading.textContent.trim().slice(0, 50)}`);
    level = next;
  }
  if (!document.documentElement.lang) problems.push("no lang attribute");
  if (document.querySelectorAll("main").length !== 1) problems.push("expected one main landmark");
  if (!document.title.trim()) problems.push("empty title");
  return problems;
}"""
ROUTES = [
    "#/",
    "#/region",
    "#/region/North%20Europe",
    "#/trains",
    "#/trains?view=timeline&zoom=all",
    "#/train/10.0.48-PQU-6",
    "#/train/10.0.99-PQU-1",
    "#/versions?build=10.0.2527.160",
    "#/learn",
    "#/learn/faq/what-is-the-biweekly-cadence-for-pqu",
    "#/changes",
    "#/data",
    "#/no-such-page",
]


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_every_view_passes_the_audit(fixture_site, open_page, theme: str) -> None:
    storage = {REGION_KEY: "North Europe", "d365-pqu-theme": theme}
    opened = open_page(fixture_site((LIVE_FIXTURES, E2E_SYNC_AT)), "#/", storage=storage)
    page = opened.page
    problems: dict[str, list[str]] = {}
    for route in ROUTES:
        page.evaluate(f"() => {{ location.hash = '{route}'; }}")
        wait_for_render(page)
        if route == "#/":
            page.locator("#ov-calendar summary").click()
        if route == "#/trains":
            page.locator("#pqu-table .row-toggle").first.click()
        found = page.evaluate(AUDIT)
        if found:
            problems[route] = found
    page.locator("#health-toggle").click()
    found = page.evaluate(AUDIT)
    if found:
        problems["health panel"] = found
    assert problems == {}
    opened.assert_clean()


def test_skip_link_moves_focus_to_the_content(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((LIVE_FIXTURES, E2E_SYNC_AT)), "#/trains")
    page = opened.page
    page.keyboard.press("Tab")
    assert page.evaluate("() => document.activeElement.textContent") == "Skip to content"
    page.keyboard.press("Enter")
    assert page.evaluate("() => document.activeElement.id") == "main"
    page.keyboard.press("Tab")
    focused = page.evaluate("() => document.activeElement.closest('main') !== null")
    assert focused
    opened.assert_clean()


def test_theme_toggle_keeps_one_name_and_reports_its_state(fixture_site, open_page) -> None:
    opened = open_page(fixture_site((LIVE_FIXTURES, E2E_SYNC_AT)), "#/")
    page = opened.page
    toggle = page.locator("#theme-toggle")
    assert (toggle.get_attribute("aria-label"), toggle.get_attribute("aria-pressed")) == (
        "Light theme",
        "false",
    )
    toggle.click()
    assert (toggle.get_attribute("aria-label"), toggle.get_attribute("aria-pressed")) == (
        "Light theme",
        "true",
    )
    assert page.evaluate("() => document.documentElement.dataset.theme") == "light"
    assert toggle.get_attribute("title") == "Switch to the dark theme"
    opened.assert_clean()
