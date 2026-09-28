from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest

from conftest import FIXTURES, REPO_ROOT, build_fixture_site
from d365_pqu.config import PAGES_BASE_URL
from d365_pqu.feed import (
    ENTRY_ID_PREFIX,
    FEED_ID,
    FEED_LIMIT,
    change_href,
    describe_change,
    feed_document,
)

ATOM = "{http://www.w3.org/2005/Atom}"
MINIMAL = FIXTURES / "source-minimal.md"
UPDATED = FIXTURES / "source-updated.md"
FIRST = "2026-09-28T03:00:00Z"
SECOND = "2026-09-28T03:30:00Z"
REPOSITORY = "MicrosoftDocs/dynamics-365-unified-operations-public"


@pytest.fixture(scope="module")
def updated_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("feed")
    return build_fixture_site(root, [(MINIMAL, FIRST), (UPDATED, SECOND)])


def _feed(site: Path) -> ElementTree.Element:
    return ElementTree.fromstring((site / "feed.xml").read_bytes())


def _json(site: Path, name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((site / "api" / name).read_text(encoding="utf-8"))
    return document


def _change(**values: Any) -> dict[str, Any]:
    change = {
        "change_id": "c" * 20,
        "changed_at": SECOND,
        "pqu_id": "dataset",
        "entity": "pqu",
        "change_type": "modified",
        "field": None,
        "old_value": None,
        "new_value": None,
        "source_commit": "a" * 40,
    }
    change.update(values)
    return change


def test_feed_lists_the_recorded_changes_newest_first(updated_site: Path) -> None:
    feed = _feed(updated_site)
    assert feed.tag == f"{ATOM}feed"
    assert feed.findtext(f"{ATOM}id") == FEED_ID
    assert feed.findtext(f"{ATOM}updated") == SECOND
    links = {link.get("rel"): link.get("href") for link in feed.findall(f"{ATOM}link")}
    assert links == {
        "self": f"{PAGES_BASE_URL}/feed.xml",
        "alternate": f"{PAGES_BASE_URL}/#/changes",
    }
    assert feed.findtext(f"{ATOM}author/{ATOM}name") == "D365 PQU dataset"

    changes = _json(updated_site, "changes.json")["records"]
    entries = feed.findall(f"{ATOM}entry")
    assert len(entries) == len(changes) == 15
    assert [entry.findtext(f"{ATOM}id") for entry in entries] == [
        f"{ENTRY_ID_PREFIX}{change['change_id']}" for change in changes
    ]

    first = entries[0]
    assert first.findtext(f"{ATOM}title") == (
        "10.0.48 PQU-5: Status changed from In-Progress to Completed"
    )
    assert first.findtext(f"{ATOM}updated") == SECOND
    commit = changes[0]["source_commit"]
    related = {link.get("rel"): link for link in first.findall(f"{ATOM}link")}
    assert related["alternate"].get("href") == f"{PAGES_BASE_URL}/#/train/10.0.48-PQU-5"
    assert related["related"].get("href") == f"https://github.com/{REPOSITORY}/commit/{commit}"
    category = first.find(f"{ATOM}category")
    assert category is not None
    assert (category.get("term"), category.get("label")) == ("pqu", "Trains")
    content = first.find(f"{ATOM}content")
    assert content is not None
    assert content.get("type") == "text"
    assert content.text == (
        f"Status changed from In-Progress to Completed. Found in Microsoft commit "
        f"{commit[:7]} of {REPOSITORY}."
    )

    titles = [entry.findtext(f"{ATOM}title") for entry in entries]
    assert "10.0.48 PQU-7: Application build published: 10.0.2645.140" in titles
    assert "10.0.48 PQU-5: Station 1 schedule removed" in titles
    removed = next(
        entry
        for entry in entries
        if entry.findtext(f"{ATOM}title")
        == "Release schedule for proactive quality updates: Section \u201cMore information\u201d removed"
    )
    link = removed.find(f"{ATOM}link[@rel='alternate']")
    assert link is not None
    assert (link.get("href") or "").endswith("/quality-updates-schedule#more-information")


def test_feed_is_deterministic(updated_site: Path) -> None:
    changes = _json(updated_site, "changes.json")["records"]
    metadata = _json(updated_site, "metadata.json")
    built = (updated_site / "feed.xml").read_bytes()
    assert feed_document(changes, metadata) == built
    assert feed_document(list(changes), dict(metadata)) == built
    assert built.startswith(b"<?xml version='1.0' encoding='utf-8'?>\n<feed xmlns=")


def test_a_feed_without_changes_is_valid(tmp_path: Path) -> None:
    site = build_fixture_site(tmp_path, [(MINIMAL, FIRST)])
    feed = _feed(site)
    assert feed.findall(f"{ATOM}entry") == []
    metadata = _json(site, "metadata.json")
    assert feed.findtext(f"{ATOM}updated") == metadata["first_published_at"] == FIRST
    for tag in ("id", "title", "updated", "author", "link"):
        assert feed.find(f"{ATOM}{tag}") is not None


def test_the_feed_keeps_the_newest_entries() -> None:
    changes = [
        _change(
            change_id=f"{index:020d}",
            changed_at=f"2026-09-{1 + index // 24:02d}T{index % 24:02d}:00:00Z",
            pqu_id="10.0.48-PQU-6",
            field="status",
            old_value="Not Started",
            new_value="In-Progress",
        )
        for index in range(150)
    ]
    feed = ElementTree.fromstring(feed_document(changes, {"first_published_at": FIRST}))
    ids = [entry.findtext(f"{ATOM}id") for entry in feed.findall(f"{ATOM}entry")]
    assert len(ids) == FEED_LIMIT
    assert ids[0] == f"{ENTRY_ID_PREFIX}{149:020d}"
    assert ids[-1] == f"{ENTRY_ID_PREFIX}{50:020d}"
    assert feed.findtext(f"{ATOM}updated") == "2026-09-07T05:00:00Z"


def test_feed_text_is_escaped_and_valid_xml() -> None:
    change = _change(
        pqu_id="10.0.48-PQU-6",
        field="status_note",
        old_value=None,
        new_value="Paused <until> \u201cfurther\u201d notice & review\x0b",
    )
    feed = ElementTree.fromstring(feed_document([change], {}))
    entry = feed.find(f"{ATOM}entry")
    assert entry is not None
    assert entry.findtext(f"{ATOM}title") == (
        "10.0.48 PQU-6: Microsoft's status note published: "
        "Paused <until> \u201cfurther\u201d notice & review"
    )
    # Without repository provenance there is no commit link.
    assert entry.find(f"{ATOM}link[@rel='related']") is None


SAMPLES = [
    _change(pqu_id="10.0.49-PQU-1", change_type="added", new_value={"status": "Not Started"}),
    _change(pqu_id="10.0.49-PQU-2", change_type="added", new_value={}),
    _change(pqu_id="10.0.46-PQU-1", change_type="removed", old_value={"status": "Completed"}),
    _change(pqu_id="10.0.48-PQU-6", field="train_end_date", old_value="2026-10-10", new_value=""),
    _change(
        pqu_id="10.0.48-PQU-6", field="station_schedule_available", old_value=None, new_value=True
    ),
    _change(pqu_id="10.0.48-PQU-6", field="release_number", old_value=6, new_value=7),
    _change(
        pqu_id="10.0.48-PQU-6",
        entity="station",
        change_type="added",
        field="station.5",
        new_value={
            "sandbox_start_date": "2026-12-28",
            "sandbox_end_date": "2027-01-02",
            "production_start_date": "2027-01-09",
            "production_end_date": "2027-01-10",
        },
    ),
    _change(
        pqu_id="10.0.48-PQU-6",
        entity="station",
        change_type="modified",
        field="station.4.production_end_date",
        old_value="2026-10-04",
        new_value="2026-10-05",
    ),
    _change(pqu_id="10.0.48-PQU-6", entity="station", change_type="removed", field=None),
    _change(
        entity="region",
        change_type="added",
        field="region.Z\u00fcrich North",
        new_value={"station": 4, "region": "Z\u00fcrich North", "is_region": True},
    ),
    _change(entity="region", change_type="removed", field="region.Old Region", old_value={}),
    _change(
        entity="region",
        field="region.North Europe",
        old_value={"station": 3, "region": "North Europe", "maintenance_geo": None},
        new_value={"station": 4, "region": "North Europe", "maintenance_geo": "Europe"},
    ),
    _change(entity="service_update", change_type="added", field="10.0.50", new_value={}),
    _change(entity="service_update", change_type="removed", field="10.0.44", old_value={}),
    _change(
        entity="service_update",
        field="10.0.49#general_availability_date",
        old_value="2026-09-11",
        new_value="2026-09-18",
    ),
    _change(entity="service_update", field="10.0.49#is_major", old_value=False, new_value=True),
    _change(
        entity="service_update", field="10.0.49#release_label", old_value=None, new_value="CY26Q4"
    ),
    _change(
        entity="maintenance_window",
        field="Europe#days",
        old_value=["Friday", "Saturday"],
        new_value=["Saturday"],
    ),
    _change(entity="maintenance_window", field="Europe#duration_hours", old_value=6, new_value=6.5),
    _change(
        entity="maintenance_window",
        field="Asia Pacific#start_time_utc",
        old_value="13:00",
        new_value="14:00",
    ),
    _change(
        entity="guidance",
        change_type="added",
        field="pqu_faq#new-question",
        new_value={
            "title": "A new question?",
            "url": "https://learn.microsoft.com/en-us/dynamics365/x#new-question",
        },
    ),
    _change(entity="guidance", field="unknown#section", old_value={}, new_value={}),
    _change(entity="guidance", change_type="removed", field="pqu_faq#gone", old_value={}),
    _change(entity="future_entity", change_type="added", field="something"),
]


def _node() -> str:
    node = shutil.which("node")
    if node:
        return node
    if os.environ.get("REQUIRE_NODE") == "1":
        pytest.fail("REQUIRE_NODE=1 but node is not installed")
    pytest.skip("node is not installed")


def test_descriptions_and_links_match_the_dashboard(updated_site: Path) -> None:
    """The feed and the dashboard must describe and link every change the same way."""
    node = _node()
    changes = [*_json(updated_site, "changes.json")["records"], *SAMPLES]
    labels = {
        key: entry["label"]
        for key, entry in _json(updated_site, "metadata.json")["sources"].items()
    }
    script = """
const changes = require('./src/d365_pqu/static/js/core/changes.js');
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = input.changes.map((change) => {
  const described = changes.describe(change, { sourceLabel: (key) => input.labels[key] || null });
  return [described.subject, described.text, changes.hrefFor(change)];
});
process.stdout.write(JSON.stringify(out));
"""
    result = subprocess.run(
        [node, "-e", script],
        input=json.dumps({"changes": changes, "labels": labels}),
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    browser = json.loads(result.stdout)
    python = []
    for change in changes:
        described = describe_change(change, source_label=labels.get)
        python.append([described["subject"], described["text"], change_href(change)])
    assert python == browser
    # Spot-check a few against the wording people read.
    by_text = {text for _, text, _ in python}
    assert (
        "Station 5 schedule published: sandbox 28 Dec 2026 \u2013 2 Jan 2027, production 9\u201310 Jan 2027"
        in by_text
    )
    assert "Maintenance window days changed from Friday and Saturday to Saturday" in by_text
    assert (
        "Region details changed: station 3 \u2192 4; maintenance geo none \u2192 Europe" in by_text
    )
    assert ["Z\u00fcrich North", "Added to Station 4", "#/region/Z%C3%BCrich%20North"] in python
