"""Optional source articles: processing, fail-soft fallback, and publication state.

Each optional article is processed as a unit. If it cannot be downloaded or parsed, everything
published from it keeps its previous values and provenance (state ``stale``) and a quality
warning explains why. If nothing was ever published for it, its outputs are empty (state
``unavailable``). Articles that were not requested at all (local runs that read only the
schedule) are ``not_configured`` and produce no warning.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from d365_pqu.config import SOURCE_REPO, SOURCE_SPECS, SourceSpec
from d365_pqu.errors import ParserError
from d365_pqu.learn import extract_article
from d365_pqu.lifecycle import SERVICE_UPDATE_RULES, parse_service_updates
from d365_pqu.maintenance import MAINTENANCE_RULES, parse_maintenance_windows
from d365_pqu.models import QualityItem, SourceBundle, SourceDocument, SourceProvenance

STATES = ("current", "stale", "unavailable", "not_configured")
PUBLISHED_STATES = ("current", "stale")

Records = list[dict[str, Any]]
Articles = list[dict[str, Any]]
Processor = Callable[
    [SourceDocument, SourceProvenance, list[QualityItem]], tuple[Records, Articles]
]


@dataclass
class SourceOutput:
    key: str
    state: str
    source: SourceProvenance | None
    records: Records = field(default_factory=list)
    articles: Articles = field(default_factory=list)
    message: str | None = None


def _iso(value: datetime) -> str:
    moment = value if value.tzinfo else value.replace(tzinfo=UTC)
    return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")


def provenance_for(document: SourceDocument) -> SourceProvenance:
    return SourceProvenance(
        publisher="Microsoft",
        repository=SOURCE_REPO,
        branch="main",
        file_path=document.file_path,
        commit=document.source_commit,
        article_url=document.article_url,
        raw_url=document.raw_url,
        markdown_date=document.markdown_date,
        sha256=document.sha256,
        retrieved_at=_iso(document.retrieved_at),
    )


def _as_provenance(value: Mapping[str, Any]) -> SourceProvenance:
    return SourceProvenance(
        publisher=value["publisher"],
        repository=value["repository"],
        branch=value["branch"],
        file_path=value["file_path"],
        commit=value["commit"],
        article_url=value["article_url"],
        raw_url=value["raw_url"],
        markdown_date=value.get("markdown_date"),
        sha256=value["sha256"],
        retrieved_at=value["retrieved_at"],
    )


def sticky_provenance(
    document: SourceDocument, previous_entry: Mapping[str, Any] | None
) -> SourceProvenance:
    """Keep the published provenance while the article bytes are unchanged.

    Provenance names the commit where these exact bytes were first retrieved, so a newer commit
    that leaves the article unchanged does not rewrite provenance across the dataset.
    """
    previous = previous_entry.get("source") if previous_entry else None
    if (
        isinstance(previous, dict)
        and previous_entry is not None
        and previous_entry.get("state") == "current"
        and previous.get("sha256") == document.sha256
        and previous.get("file_path") == document.file_path
    ):
        return _as_provenance(previous)
    return provenance_for(document)


def article_provenance(provenance: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "file_path": provenance["file_path"],
        "commit": provenance["commit"],
        "sha256": provenance["sha256"],
        "markdown_date": provenance.get("markdown_date"),
        "raw_url": provenance["raw_url"],
    }


def previous_article(previous_learn: Mapping[str, Any] | None, key: str) -> dict[str, Any] | None:
    articles = previous_learn.get("articles") if previous_learn else None
    if not isinstance(articles, list):
        return None
    for article in articles:
        if isinstance(article, dict) and article.get("key") == key:
            return article
    return None


def source_entry(spec: SourceSpec, state: str, source: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "label": spec.label,
        "required": spec.required,
        "article_url": spec.article_url,
        "file_path": spec.file_path,
        "state": state,
        "source": dict(source) if source else None,
    }


def source_identity(sources: Mapping[str, Mapping[str, Any]]) -> dict[str, tuple[Any, Any]]:
    """Content identity per source: (sha256 of the published article, publication state)."""
    identity: dict[str, tuple[Any, Any]] = {}
    for key, entry in sources.items():
        source = entry.get("source") if isinstance(entry, Mapping) else None
        sha = source.get("sha256") if isinstance(source, Mapping) else None
        identity[key] = (sha, entry.get("state") if isinstance(entry, Mapping) else None)
    return identity


def previous_sources(metadata: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Per-source state from published metadata (older metadata only knew the schedule)."""
    if not metadata:
        return {}
    sources = metadata.get("sources")
    if isinstance(sources, dict):
        return {key: value for key, value in sources.items() if isinstance(value, dict)}
    source = metadata.get("source")
    if isinstance(source, dict):
        return {"schedule": {"state": "current", "source": source}}
    return {}


def _learn_article(
    document: SourceDocument, provenance: Mapping[str, Any], rules: Any = None
) -> dict[str, Any]:
    article = extract_article(
        document.markdown,
        key=document.key,
        file_path=document.file_path,
        article_url=document.article_url,
        rules=rules,
    )
    return {**article, **article_provenance(provenance)}


def _service_updates(
    document: SourceDocument, provenance: SourceProvenance, quality: list[QualityItem]
) -> tuple[Records, Articles]:
    records, findings = parse_service_updates(document.markdown)
    quality.extend(findings)
    return records, [_learn_article(document, provenance, SERVICE_UPDATE_RULES)]


def _maintenance(
    document: SourceDocument, provenance: SourceProvenance, quality: list[QualityItem]
) -> tuple[Records, Articles]:
    records, findings = parse_maintenance_windows(document.markdown)
    quality.extend(findings)
    return records, [_learn_article(document, provenance, MAINTENANCE_RULES)]


def _article_only(
    document: SourceDocument, provenance: SourceProvenance, quality: list[QualityItem]
) -> tuple[Records, Articles]:
    """Articles published only as Learn content (overview, FAQ): no dataset rows."""
    article = _learn_article(document, provenance)
    if not any(section["blocks"] for section in article["sections"]):
        raise ParserError("article contained no readable sections")
    return [], [article]


PROCESSORS: dict[str, Processor] = {
    "service_updates": _service_updates,
    "maintenance": _maintenance,
    "pqu_overview": _article_only,
    "pqu_faq": _article_only,
}


def _warning(code: str, message: str) -> QualityItem:
    return QualityItem(code=code, severity="warning", message=message, pqu_id=None, field=None)


def _describe_previous(source: Mapping[str, Any]) -> str:
    commit = str(source.get("commit") or "")[:12]
    retrieved = str(source.get("retrieved_at") or "")[:10]
    parts = [part for part in (f"commit {commit}" if commit else "", retrieved) if part]
    return ", ".join(parts)


def process_source(
    spec: SourceSpec,
    bundle: SourceBundle,
    *,
    previous_entry: Mapping[str, Any] | None,
    previous_records: Sequence[Mapping[str, Any]],
    previous_learn: Mapping[str, Any] | None,
    quality: list[QualityItem],
) -> SourceOutput:
    processor = PROCESSORS[spec.key]
    document = bundle.documents.get(spec.key)
    error = bundle.errors.get(spec.key)
    if document is None and error is None:
        return SourceOutput(spec.key, "not_configured", None)
    if document is not None:
        provenance = sticky_provenance(document, previous_entry)
        findings: list[QualityItem] = []
        try:
            records, articles = processor(document, provenance, findings)
        except ParserError as exc:
            error = f"could not be parsed: {exc}"
        else:
            quality.extend(_warning("source-warning", message) for message in document.warnings)
            quality.extend(findings)
            return SourceOutput(spec.key, "current", provenance, records, articles)
    reason = error or "unknown error"
    previous_source = previous_entry.get("source") if previous_entry else None
    if (
        previous_entry is not None
        and previous_entry.get("state") in PUBLISHED_STATES
        and isinstance(previous_source, dict)
    ):
        article = previous_article(previous_learn, spec.key)
        quality.append(
            _warning(
                "source-stale",
                (
                    f"{spec.label} could not be refreshed ({reason}); showing the last published "
                    f"copy ({_describe_previous(previous_source)})."
                ),
            )
        )
        return SourceOutput(
            spec.key,
            "stale",
            _as_provenance(previous_source),
            [dict(record) for record in previous_records],
            [article] if article else [],
            message=reason,
        )
    quality.append(
        _warning(
            "source-unavailable",
            f"{spec.label} could not be retrieved ({reason}); information from it is not shown.",
        )
    )
    return SourceOutput(spec.key, "unavailable", None, message=reason)


def process_optional_sources(
    bundle: SourceBundle,
    *,
    previous_metadata: Mapping[str, Any] | None,
    previous_records: Mapping[str, Sequence[Mapping[str, Any]]],
    previous_learn: Mapping[str, Any] | None,
    quality: list[QualityItem],
) -> dict[str, SourceOutput]:
    published = previous_sources(previous_metadata)
    outputs: dict[str, SourceOutput] = {}
    for spec in SOURCE_SPECS:
        if spec.required or spec.key not in PROCESSORS:
            continue
        outputs[spec.key] = process_source(
            spec,
            bundle,
            previous_entry=published.get(spec.key),
            previous_records=previous_records.get(spec.key, ()),
            previous_learn=previous_learn,
            quality=quality,
        )
    return outputs
