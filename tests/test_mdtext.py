from __future__ import annotations

import pytest

from d365_pqu import mdtext

SCHEDULE_PATH = "articles/fin-ops-core/dev-itpro/get-started/quality-updates-schedule.md"
SCHEDULE_URL = (
    "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/"
    "quality-updates-schedule"
)


def _inline(markdown: str):
    tokens = mdtext.parse_tokens(markdown)
    return next(token for token in tokens if token.type == "inline")


@pytest.mark.parametrize(
    ("heading", "slug"),
    [
        ("High-level PQU train schedule", "high-level-pqu-train-schedule"),
        (
            "Targeted release schedule (dates subject to change)",
            "targeted-release-schedule-dates-subject-to-change",
        ),
        (
            "What does near-zero-downtime maintenance mean?",
            "what-does-near-zero-downtime-maintenance-mean",
        ),
        (
            "What investments is Microsoft making to enable safe deployments of PQUs?",
            "what-investments-is-microsoft-making-to-enable-safe-deployments-of-pqus",
        ),
        (
            "Retry for any error or batch server restart",
            "retry-for-any-error-or-batch-server-restart",
        ),
        (
            "Things to consider about production updates",
            "things-to-consider-about-production-updates",
        ),
        (
            "What's the minimum timeline between sandbox and production?",
            "whats-the-minimum-timeline-between-sandbox-and-production",
        ),
        ("Proactive quality updates (PQU) - FAQ", "proactive-quality-updates-pqu---faq"),
        ("Station-to-region mapping", "station-to-region-mapping"),
    ],
)
def test_slugify_matches_learn_anchors(heading: str, slug: str) -> None:
    assert mdtext.slugify(heading) == slug


def test_slug_registry_suffixes_duplicates_like_markdig() -> None:
    registry = mdtext.SlugRegistry()
    registry.reserve("intro")
    assert registry.unique("Batch service") == "batch-service"
    assert registry.unique("Batch service") == "batch-service-1"
    assert registry.unique("Batch service") == "batch-service-2"
    assert registry.unique("Intro") == "intro-1"
    assert registry.unique("???") == "section"


@pytest.mark.parametrize(
    ("href", "expected"),
    [
        (
            "../deployment/plannedmaintenance-selfservice.md#windows",
            "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/deployment/"
            "plannedmaintenance-selfservice#windows",
        ),
        (
            "quality-updates-faq.md",
            "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/"
            "quality-updates-faq",
        ),
        (
            "../../fin-ops/get-started/quality-updates-schedule.md",
            "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/fin-ops/get-started/"
            "quality-updates-schedule",
        ),
        ("#high-level-pqu-train-schedule", f"{SCHEDULE_URL}#high-level-pqu-train-schedule"),
        (
            "/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates-schedule#high-level-pqu-train-schedule",
            f"{SCHEDULE_URL}#high-level-pqu-train-schedule",
        ),
        (
            "/admin/manage/message-center",
            "https://learn.microsoft.com/en-us/admin/manage/message-center",
        ),
        (
            "/en-us/azure/compliance/offerings/offering-gxp",
            "https://learn.microsoft.com/en-us/azure/compliance/offerings/offering-gxp",
        ),
        ("https://aka.ms/FirstReleaseFnO", "https://aka.ms/FirstReleaseFnO"),
        ("http://example.com/page", None),
        ("mailto:someone@example.com", None),
        ("javascript:alert(1)", None),
        ("//evil.example/x", None),
        ("../../../../../outside.md", None),
        ("../media/maintenance-settings-selection.png", None),
        ("", None),
    ],
)
def test_link_resolver_maps_repository_links_to_learn(href: str, expected: str | None) -> None:
    resolve = mdtext.link_resolver(SCHEDULE_PATH, SCHEDULE_URL)
    assert resolve(href) == expected


def test_inline_text_handles_escapes_entities_code_and_html() -> None:
    token = _inline("Canceled\\* &amp; `code` <!--TO HERE--> [link](x.md) **bold** ![img](a.png)")
    assert mdtext.inline_text(token) == "Canceled* & code link bold"


def test_inline_lines_split_at_source_line_breaks() -> None:
    token = _inline("[!Note]\nAny new environment.\nCanceled* - PQU will occur only on Station-1.")
    assert mdtext.inline_lines(token) == [
        "[!Note]",
        "Any new environment.",
        "Canceled* - PQU will occur only on Station-1.",
    ]


def test_inline_runs_keep_formatting_links_and_spacing() -> None:
    resolve = mdtext.link_resolver(SCHEDULE_PATH, SCHEDULE_URL)
    token = _inline(
        "Select **Settings**, then *read* [the FAQ](quality-updates-faq.md) or `code`.\n"
        "Next  line [bad](http://x.test)."
    )
    assert mdtext.inline_runs(token, resolve) == [
        {"text": "Select "},
        {"text": "Settings", "strong": True},
        {"text": ", then "},
        {"text": "read", "em": True},
        {"text": " "},
        {
            "text": "the FAQ",
            "href": (
                "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/"
                "get-started/quality-updates-faq"
            ),
        },
        {"text": " or "},
        {"text": "code", "code": True},
        {"text": ". Next line bad."},
    ]


def test_split_callout_detects_markers_case_insensitively() -> None:
    resolve = mdtext.link_resolver(SCHEDULE_PATH, SCHEDULE_URL)
    kind, rest = mdtext.split_callout(mdtext.inline_runs(_inline("[!Note]\nText here."), resolve))
    assert kind == "note"
    assert rest == [{"text": "Text here."}]
    kind, rest = mdtext.split_callout(mdtext.inline_runs(_inline("[!IMPORTANT]"), resolve))
    assert (kind, rest) == ("important", [])
    kind, rest = mdtext.split_callout(mdtext.inline_runs(_inline("[!div class=x]"), resolve))
    assert kind is None


def test_explicit_anchors_and_heading_text() -> None:
    tokens = mdtext.parse_tokens(
        '## <a name="windows"></a>What are the planned maintenance windows?'
    )
    inline = tokens[1]
    assert mdtext.explicit_anchors(inline) == ["windows"]
    assert mdtext.inline_text(inline) == "What are the planned maintenance windows?"


def test_front_matter_is_not_parsed_as_content() -> None:
    tokens = mdtext.parse_tokens("---\ntitle: X\nms.date: 09/21/2026\n---\n\n# Title\n")
    headings = [token for token in tokens if token.type == "heading_open"]
    assert [token.tag for token in headings] == ["h1"]


def test_block_tree_nests_lists_quotes_and_tables() -> None:
    markdown = (
        "1. Step one\n\n   > [!NOTE]\n   > Nested note.\n\n1. Step two\n    - child\n\n"
        "| A | B |\n|---|---|\n| 1 | |\n"
    )
    nodes = mdtext.block_tree(mdtext.parse_tokens(markdown))
    assert [node.kind for node in nodes] == ["list", "table"]
    first_item = nodes[0].children[0]
    assert [child.kind for child in first_item.children] == ["paragraph", "blockquote"]
    assert nodes[0].ordered is True
    assert [mdtext.inline_text(cell) for cell in nodes[1].rows[1]] == ["1", ""]
