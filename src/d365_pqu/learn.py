"""Structured, sanitized Microsoft Learn article content for ``learn.json``.

Articles become sections (one per heading) holding blocks built only from parsed Markdown:
paragraphs, lists, callouts (``[!NOTE]`` and friends), quotes, tables, and dataset placeholders
that stand in for tables this project already publishes as data. Raw HTML, images, DocFX
includes, and ``:::`` directives are dropped; links are resolved to https URLs or removed.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from d365_pqu import mdtext
from d365_pqu.errors import ParserError
from d365_pqu.parser import REGION_HEADERS, STATION_HEADERS, TRAIN_HEADERS

Block = dict[str, Any]

MAX_SECTIONS = 200
MAX_SECTION_CHARS = 20_000
MAX_ARTICLE_CHARS = 200_000
INTRO_ID = "intro"

LICENSE = {
    "name": "Creative Commons Attribution 4.0 International",
    "url": "https://creativecommons.org/licenses/by/4.0/",
    "attribution": (
        "Text from Microsoft Learn documentation by Microsoft, published in "
        "MicrosoftDocs/dynamics-365-unified-operations-public."
    ),
    "changes": (
        "Converted to structured text; images, includes, embedded HTML, and tables that are "
        "published as datasets were removed; links were resolved to Microsoft Learn URLs."
    ),
}


@dataclass(frozen=True)
class HeadingGroup:
    """Merge every heading matching ``pattern`` into one stable section."""

    pattern: re.Pattern[str]
    id: str
    anchor: str | None
    title: str
    level: int


@dataclass(frozen=True)
class ArticleRules:
    dataset_tables: Mapping[tuple[str, ...], str] = field(default_factory=dict)
    groups: tuple[HeadingGroup, ...] = ()
    drop_paragraphs: tuple[re.Pattern[str], ...] = ()


SCHEDULE_RULES = ArticleRules(
    dataset_tables={
        REGION_HEADERS: "regions",
        TRAIN_HEADERS: "trains",
        STATION_HEADERS: "stations",
    },
    groups=(
        HeadingGroup(
            pattern=re.compile(r"proactive quality update upcoming", re.IGNORECASE),
            id="schedule",
            anchor="schedule",
            title="Detailed station schedules",
            level=3,
        ),
    ),
    drop_paragraphs=(
        re.compile(
            r"^(App version|Platform version|Unified Environment Provisioning Application Version)\s*:",
            re.IGNORECASE,
        ),
    ),
)


@dataclass
class _Section:
    id: str
    anchor: str | None
    title: str
    level: int
    aliases: list[str] = field(default_factory=list)
    nodes: list[mdtext.Node] = field(default_factory=list)


def _header_key(header: Sequence[str]) -> tuple[str, ...]:
    return mdtext.header_key(header)


class _Converter:
    def __init__(self, resolve: mdtext.Resolver, rules: ArticleRules) -> None:
        self.resolve = resolve
        self.rules = rules
        self.datasets = {_header_key(header): name for header, name in rules.dataset_tables.items()}

    def blocks(self, nodes: Sequence[mdtext.Node]) -> list[Block]:
        result: list[Block] = []
        for node in nodes:
            block = self.block(node)
            if block is not None:
                result.append(block)
        return result

    def block(self, node: mdtext.Node) -> Block | None:
        if node.kind == "paragraph":
            return self.paragraph(node)
        if node.kind == "heading":
            runs = mdtext.inline_runs(node.inline, self.resolve)
            if not runs:
                return None
            return {"type": "paragraph", "runs": [{**run, "strong": True} for run in runs]}
        if node.kind == "list":
            return self.list_block(node)
        if node.kind == "blockquote":
            return self.quote(node)
        if node.kind == "table":
            return self.table(node)
        return None

    def paragraph(self, node: mdtext.Node) -> Block | None:
        text = mdtext.inline_text(node.inline)
        if not text or text.startswith((":::", "[!")):
            return None
        if any(pattern.search(text) for pattern in self.rules.drop_paragraphs):
            return None
        runs = mdtext.inline_runs(node.inline, self.resolve)
        return {"type": "paragraph", "runs": runs} if runs else None

    def list_block(self, node: mdtext.Node) -> Block | None:
        items = [self.blocks(item.children) for item in node.children if item.kind == "item"]
        items = [item for item in items if item]
        if not items:
            return None
        block: Block = {"type": "list", "ordered": node.ordered, "items": items}
        if node.ordered and node.start != 1:
            block["start"] = node.start
        return block

    def quote(self, node: mdtext.Node) -> Block | None:
        children = list(node.children)
        kind: str | None = None
        lead: list[Block] = []
        if children and children[0].kind == "paragraph":
            runs = mdtext.inline_runs(children[0].inline, self.resolve)
            kind, rest = mdtext.split_callout(runs)
            if kind:
                children = children[1:]
                if rest and not mdtext.runs_text(rest).startswith((":::", "[!")):
                    lead = [{"type": "paragraph", "runs": rest}]
        blocks = lead + self.blocks(children)
        if not blocks:
            return None
        if kind:
            return {"type": "callout", "kind": kind, "blocks": blocks}
        return {"type": "quote", "blocks": blocks}

    def table(self, node: mdtext.Node) -> Block | None:
        if not node.rows:
            return None
        header = [mdtext.inline_text(cell) for cell in node.rows[0]]
        dataset = self.datasets.get(_header_key(header))
        if dataset:
            return {"type": "dataset", "name": dataset}
        rows = [
            [mdtext.inline_runs(cell, self.resolve) for cell in row]
            for row in node.rows[1:]
            if any(mdtext.inline_text(cell) for cell in row)
        ]
        return {
            "type": "table",
            "header": [mdtext.inline_runs(cell, self.resolve) for cell in node.rows[0]],
            "rows": rows,
        }


def _dedupe_datasets(blocks: list[Block]) -> list[Block]:
    seen: set[str] = set()
    result: list[Block] = []
    for block in blocks:
        if block["type"] == "dataset":
            if block["name"] in seen:
                continue
            seen.add(block["name"])
        result.append(block)
    return result


def _is_navigation(blocks: Sequence[Block]) -> bool:
    """True when a section is only lists of links (for example "Additional resources")."""
    if not blocks:
        return False
    for block in blocks:
        if block["type"] != "list":
            return False
        for item in block["items"]:
            if len(item) != 1 or item[0]["type"] != "paragraph":
                return False
            visible = [run for run in item[0]["runs"] if run["text"].strip()]
            if not visible or not all(run.get("href") for run in visible):
                return False
    return True


def block_text(blocks: Sequence[Block]) -> str:
    """Plain text of blocks, for search, size limits, and tests."""
    parts: list[str] = []
    for block in blocks:
        kind = block["type"]
        if kind == "paragraph":
            parts.append(mdtext.runs_text(block["runs"]))
        elif kind == "list":
            parts.extend(block_text(item) for item in block["items"])
        elif kind in ("callout", "quote"):
            parts.append(block_text(block["blocks"]))
        elif kind == "table":
            for row in [block["header"], *block["rows"]]:
                parts.append(" ".join(mdtext.runs_text(cell) for cell in row))
    return " ".join(part for part in parts if part)


def section_hash(title: str, blocks: Sequence[Block]) -> str:
    payload = json.dumps(
        {"title": title, "blocks": list(blocks)},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def extract_article(
    markdown: str,
    *,
    key: str,
    file_path: str,
    article_url: str,
    rules: ArticleRules | None = None,
) -> dict[str, Any]:
    """Split an article into sections of sanitized blocks."""
    active = rules or ArticleRules()
    nodes = mdtext.block_tree(mdtext.parse_tokens(markdown))
    converter = _Converter(mdtext.link_resolver(file_path, article_url), active)
    slugs = mdtext.SlugRegistry()
    slugs.reserve(INTRO_ID)
    for rule in active.groups:
        slugs.reserve(rule.id)
    intro = _Section(id=INTRO_ID, anchor=None, title="", level=1)
    sections = [intro]
    grouped: dict[str, _Section] = {}
    current = intro
    title: str | None = None
    for node in nodes:
        if node.kind != "heading":
            current.nodes.append(node)
            continue
        text = mdtext.inline_text(node.inline)
        slug = slugs.unique(mdtext.heading_text_raw(node.inline))
        if node.level == 1 and title is None:
            title = text
            intro.title = text
            continue
        group = next((item for item in active.groups if item.pattern.search(text)), None)
        if group is not None:
            if group.id not in grouped:
                grouped[group.id] = _Section(
                    id=group.id, anchor=group.anchor, title=group.title, level=group.level
                )
                sections.append(grouped[group.id])
            current = grouped[group.id]
            continue
        current = _Section(
            id=slug,
            anchor=slug,
            title=text,
            level=node.level,
            aliases=[name for name in mdtext.explicit_anchors(node.inline) if name != slug],
        )
        sections.append(current)
    if not title:
        raise ParserError(f"{key}: article has no title heading")

    converted: list[tuple[_Section, list[Block]]] = []
    for section in sections:
        blocks = _dedupe_datasets(converter.blocks(section.nodes))
        if _is_navigation(blocks):
            continue
        converted.append((section, blocks))
    kept: list[dict[str, Any]] = []
    total = 0
    for index, (section, blocks) in enumerate(converted):
        following = converted[index + 1][0] if index + 1 < len(converted) else None
        has_children = following is not None and following.level > section.level
        if not blocks and not has_children:
            continue
        size = len(block_text(blocks))
        if size > MAX_SECTION_CHARS:
            raise ParserError(
                f"{key}: section {section.id!r} exceeds {MAX_SECTION_CHARS} characters"
            )
        total += size
        kept.append(
            {
                "id": section.id,
                "anchor": section.anchor,
                "aliases": section.aliases,
                "title": section.title,
                "level": section.level,
                "url": f"{article_url}#{section.anchor}" if section.anchor else article_url,
                "text_sha256": section_hash(section.title, blocks),
                "blocks": blocks,
            }
        )
    if len(kept) > MAX_SECTIONS:
        raise ParserError(f"{key}: article has more than {MAX_SECTIONS} sections")
    if total > MAX_ARTICLE_CHARS:
        raise ParserError(f"{key}: article exceeds {MAX_ARTICLE_CHARS} characters")
    return {"key": key, "title": title, "url": article_url, "sections": kept}


def learn_document(
    articles: Sequence[Mapping[str, Any]],
    *,
    dataset: str,
    schema_version: str,
    generated_at: str,
    source: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "dataset": dataset,
        "schema_version": schema_version,
        "generated_at": generated_at,
        "source": dict(source),
        "license": dict(LICENSE),
        "count": len(articles),
        "articles": [dict(article) for article in articles],
    }
