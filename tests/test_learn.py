from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from conftest import LIVE_FIXTURES, SCHEMA_DIR
from d365_pqu.errors import ParserError
from d365_pqu.learn import SCHEDULE_RULES, block_text, extract_article, learn_document
from d365_pqu.validation import validate_document

BASE = "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/"
ARTICLES = {
    "schedule": ("get-started/quality-updates-schedule.md", SCHEDULE_RULES),
    "pqu_overview": ("get-started/quality-updates.md", None),
    "pqu_faq": ("get-started/quality-updates-faq.md", None),
    "maintenance": ("deployment/plannedmaintenance-selfservice.md", None),
}


def _article(key: str) -> dict[str, Any]:
    relative, rules = ARTICLES[key]
    markdown = (LIVE_FIXTURES / Path(relative).name).read_text(encoding="utf-8")
    return extract_article(
        markdown,
        key=key,
        file_path=f"articles/fin-ops-core/dev-itpro/{relative}",
        article_url=BASE + relative[: -len(".md")],
        rules=rules,
    )


def _walk_runs(blocks: list[dict[str, Any]]):
    for block in blocks:
        if block["type"] == "paragraph":
            yield from block["runs"]
        elif block["type"] == "list":
            for item in block["items"]:
                yield from _walk_runs(item)
        elif block["type"] in ("callout", "quote"):
            yield from _walk_runs(block["blocks"])
        elif block["type"] == "table":
            for row in [block["header"], *block["rows"]]:
                for cell in row:
                    yield from cell


def _callouts(article: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (section["id"], block)
        for section in article["sections"]
        for block in section["blocks"]
        if block["type"] == "callout"
    ]


def test_schedule_article_keeps_guidance_and_replaces_data_tables() -> None:
    article = _article("schedule")
    assert article["title"] == "Release schedule for proactive quality updates"
    assert [section["id"] for section in article["sections"]] == [
        "intro",
        "station-to-region-mapping",
        "high-level-pqu-train-schedule",
        "schedule",
    ]
    intro = article["sections"][0]
    assert intro["url"] == BASE + "get-started/quality-updates-schedule"
    assert "published five days before the start of the PQU train" in block_text(intro["blocks"])
    datasets = [
        block["name"]
        for section in article["sections"]
        for block in section["blocks"]
        if block["type"] == "dataset"
    ]
    assert datasets == ["regions", "trains", "stations"]
    text = " ".join(block_text(section["blocks"]) for section in article["sections"])
    assert "App version:" not in text
    assert "INCLUDE" not in text
    assert "More information" not in [section["title"] for section in article["sections"]]


def test_schedule_article_extracts_microsoft_rollout_callouts() -> None:
    callouts = _callouts(_article("schedule"))
    assert [(section, block["kind"]) for section, block in callouts] == [
        ("station-to-region-mapping", "important"),
        ("high-level-pqu-train-schedule", "note"),
        ("schedule", "important"),
    ]
    first = callouts[0][1]["blocks"]
    assert first[0]["type"] == "list" and first[0]["ordered"] is True
    assert len(first[0]["items"]) == 3
    assert "receive PQUs on weekends" in block_text(first)
    assert "Canceled* - PQU will occur only on Station-1." in block_text(callouts[1][1]["blocks"])
    last = block_text(callouts[2][1]["blocks"])
    assert "schedule shows a range of four days" in last
    assert "can't predetermine which set of environments is updated" in last
    assert "dark-hour window" in last


def test_faq_article_converts_steps_callouts_and_drops_images() -> None:
    article = _article("pqu_faq")
    by_id = {section["id"]: section for section in article["sections"]}
    cadence = by_id["what-is-the-biweekly-cadence-for-pqu"]
    assert "two\u2011week cadence" in block_text(cadence["blocks"])
    steps = by_id["how-do-i-configure-my-production-environment-to-receive-pqu-updates-on-weekdays"]
    ordered = [block for block in steps["blocks"] if block["type"] == "list"]
    assert ordered and ordered[0]["ordered"] is True
    assert len(ordered[0]["items"]) == 6
    assert block_text(ordered[0]["items"][0]) == "Sign in to PPAC."
    nested = ordered[0]["items"][5]
    assert [block["type"] for block in nested] == ["paragraph", "callout"]
    everything = json.dumps(article)
    assert ":::image" not in everything
    assert "media/" not in everything
    assert "TO HERE" not in everything
    assert "additional-resources" not in by_id
    assert by_id["intro"]["blocks"][1]["type"] == "callout"


def test_maintenance_article_keeps_explicit_anchor_alias_and_nested_lists() -> None:
    article = _article("maintenance")
    by_id = {section["id"]: section for section in article["sections"]}
    windows = by_id["what-are-the-planned-maintenance-windows"]
    assert windows["aliases"] == ["windows"]
    assert any(block["type"] == "table" for block in windows["blocks"])
    batch = by_id["batch-service"]
    assert batch["level"] == 3
    bullet = next(block for block in batch["blocks"] if block["type"] == "list")
    assert bullet["items"][1][1]["type"] == "list"


def test_all_links_are_https_and_no_markup_survives() -> None:
    for key in ARTICLES:
        article = _article(key)
        for section in article["sections"]:
            assert section["url"].startswith("https://learn.microsoft.com/")
            for run in _walk_runs(section["blocks"]):
                assert not re.search(r"<[a-zA-Z/!]", run["text"]), (key, run)
                assert run["text"].strip() or run["text"] == " "
                if "href" in run:
                    assert run["href"].startswith("https://"), (key, run)


def test_section_hash_is_stable_and_sensitive_to_text() -> None:
    markdown = (LIVE_FIXTURES / "quality-updates-schedule.md").read_text(encoding="utf-8")

    def extract(text: str) -> dict[str, Any]:
        return extract_article(
            text,
            key="schedule",
            file_path="articles/x/y.md",
            article_url=BASE + "x",
            rules=SCHEDULE_RULES,
        )

    first = extract(markdown)
    second = extract(markdown)
    assert [s["text_sha256"] for s in first["sections"]] == [
        s["text_sha256"] for s in second["sections"]
    ]
    third = extract(markdown.replace("range of four days", "range of five days"))
    changed = [
        a["id"]
        for a, b in zip(first["sections"], third["sections"], strict=True)
        if a["text_sha256"] != b["text_sha256"]
    ]
    assert changed == ["schedule"]
    # Train rows and build numbers are data, so they do not change guidance hashes.
    fourth = extract(markdown.replace("10.0.2645.136", "10.0.2645.999"))
    assert [s["text_sha256"] for s in fourth["sections"]] == [
        s["text_sha256"] for s in first["sections"]
    ]


def test_article_without_title_is_rejected() -> None:
    with pytest.raises(ParserError, match="no title"):
        extract_article("Just text.", key="x", file_path="articles/x.md", article_url=BASE + "x")


def test_learn_document_validates_against_schema() -> None:
    articles = []
    for key in ARTICLES:
        article = _article(key)
        articles.append(
            {
                **article,
                "file_path": "articles/x.md",
                "commit": "a" * 40,
                "sha256": "b" * 64,
                "markdown_date": "2026-09-21",
                "raw_url": "https://raw.githubusercontent.com/x",
            }
        )
    document = learn_document(
        articles,
        dataset="d365-finops-pqu",
        schema_version="1.1.0",
        generated_at="2026-09-28T03:00:00Z",
        source={"commit": "a" * 40},
    )
    validate_document(document, SCHEMA_DIR / "learn.schema.json")
    assert document["license"]["url"] == "https://creativecommons.org/licenses/by/4.0/"
