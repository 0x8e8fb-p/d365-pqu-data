"""Atom feed of the change history (``feed.xml``).

One entry per recorded change, newest first, capped at ``FEED_LIMIT``. Entry identifiers come
from the change identifiers, so a feed reader never shows the same change twice and a rebuild
produces the same feed. The plain-language wording mirrors ``static/js/core/changes.js`` (the
dashboard); ``tests/test_feed.py`` runs both on the same changes and compares the results.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import Any
from urllib.parse import quote
from xml.etree import ElementTree

from d365_pqu.config import PAGES_BASE_URL

ATOM_NAMESPACE = "http://www.w3.org/2005/Atom"
FEED_FILE = "feed.xml"
FEED_ID = "urn:d365-pqu:feed:changes"
ENTRY_ID_PREFIX = "urn:d365-pqu:change:"
FEED_LIMIT = 100
FEED_TITLE = "D365 PQU changes \u00b7 Finance & Operations"
FEED_SUBTITLE = (
    "Changes detected in Microsoft's published proactive quality update schedule and the "
    "related Microsoft Learn articles."
)
FEED_RIGHTS = (
    "Values come from Microsoft Learn documentation published under CC BY 4.0; see NOTICE.md "
    "in the source repository. Not affiliated with or endorsed by Microsoft."
)

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
TRAIN_ID = re.compile(r"^(\d+\.\d+\.\d+)-(PQU-\d+)$")
STATION_FIELD = re.compile(r"^station\.(\d+)(?:\.([a-z_]+))?$")
COMMIT = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)
REPOSITORY = re.compile(r"^[\w.-]+/[\w.-]+$")
# Characters XML 1.0 cannot carry; removed from text before serialising.
XML_INVALID = re.compile("[^\t\n\r\u0020-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")

PQU_FIELDS = {
    "application_version": "Application version",
    "pqu_train": "Train",
    "release_number": "Release number",
    "change_cutoff_date": "Change cutoff",
    "train_start_date": "Train start",
    "train_end_date": "Train end",
    "status": "Status",
    "application_build": "Application build",
    "platform_build": "Platform build",
    "uep_version": "UEP version",
    "station_schedule_available": "Station schedule",
    "status_note": "Microsoft's status note",
}
STATION_FIELDS = {
    "sandbox_start_date": "sandbox start",
    "sandbox_end_date": "sandbox end",
    "production_start_date": "production start",
    "production_end_date": "production end",
}
SERVICE_UPDATE_FIELDS = {
    "release_label": "release label",
    "is_major": "major release",
    "preview_date": "preview",
    "preview_latest_update_date": "latest preview update",
    "general_availability_date": "general availability",
    "first_autoupdate_date": "first autoupdate",
    "second_autoupdate_date": "second autoupdate",
    "end_of_service_date": "end of service",
}
MAINTENANCE_FIELDS = {
    "start_time_utc": "start time (UTC)",
    "days": "days",
    "duration_hours": "duration (hours)",
    "duration_text": "duration",
}
ENTITY_LABELS = {
    "pqu": "Trains",
    "station": "Station schedules",
    "region": "Regions",
    "guidance": "Microsoft guidance",
    "service_update": "Service updates",
    "maintenance_window": "Maintenance windows",
}
TYPE_LABELS = {"added": "Added", "removed": "Removed", "modified": "Changed"}

SourceLabel = Callable[[str], str | None]
_MISSING = object()


# ---- Formatting (mirrors core/dates.js and core/text.js) ----


def _parse_date(value: Any) -> tuple[int, int, int] | None:
    if not isinstance(value, str):
        return None
    match = ISO_DATE.match(value.strip())
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    try:
        date(year, month, day)
    except ValueError:
        return None
    return year, month, day


def format_date(value: Any) -> str:
    """``"2026-10-05"`` -> ``"5 Oct 2026"``."""
    parsed = _parse_date(value)
    if parsed is None:
        return "\u2014" if value is None or value == "" else _js_string(value)
    year, month, day = parsed
    return f"{day} {MONTHS[month - 1]} {year}"


def format_date_range(start: Any, end: Any) -> str:
    first = _parse_date(start)
    last = _parse_date(end)
    if first is None and last is None:
        return "\u2014"
    if first is None or last is None:
        return format_date(start if first is not None else end)
    if first == last:
        return format_date(start)
    if first[0] == last[0] and first[1] == last[1]:
        return f"{first[2]}\u2013{last[2]} {MONTHS[last[1] - 1]} {last[0]}"
    if first[0] == last[0]:
        return f"{first[2]} {MONTHS[first[1] - 1]} \u2013 {format_date(end)}"
    return f"{format_date(start)} \u2013 {format_date(end)}"


def join_list(items: Sequence[str]) -> str:
    values = [item for item in items if item is not None and item != ""]
    if len(values) <= 1:
        return "".join(values)
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])} and {values[-1]}"


def train_label(pqu_id: Any) -> str:
    """``"10.0.48-PQU-6"`` -> ``"10.0.48 PQU-6"``."""
    text = "" if pqu_id is None else str(pqu_id)
    match = TRAIN_ID.match(text)
    return f"{match.group(1)} {match.group(2)}" if match else text


def _capitalize(text: str) -> str:
    return text[:1].upper() + text[1:]


def _js_string(value: Any) -> str:
    """``String(value)`` in JavaScript, for the JSON values a change can hold."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, dict):
        return "[object Object]"
    if isinstance(value, list):
        return ",".join("" if item is None else _js_string(item) for item in value)
    return str(value)


def _js_truthy(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, int | float) and not isinstance(value, bool):
        return value != 0
    if isinstance(value, str):
        return value != ""
    return True


def _first_truthy(*values: Any) -> Any:
    """``a || b || {}``."""
    for value in values:
        if _js_truthy(value):
            return value
    return {}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _stringify(value: Any) -> str | None:
    """``JSON.stringify`` for comparing values; a missing key is ``undefined``."""
    if value is _MISSING:
        return None
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _encode(value: str) -> str:
    """``encodeURIComponent``."""
    return quote(value, safe="!~*'()")


# ---- Descriptions (mirrors core/changes.js) ----


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value == "")


def _value(item: Any, field: str | None) -> str:
    if _blank(item):
        return "not published" if field == "station_schedule_available" else "none"
    if field == "station_schedule_available":
        return "published" if _js_truthy(item) else "not published"
    if isinstance(item, bool):
        return "yes" if item else "no"
    if isinstance(item, list):
        return join_list([_js_string(entry) for entry in item])
    if isinstance(item, str) and _parse_date(item) is not None:
        return format_date(item)
    return _js_string(item)


def _changed(label: str, change: Mapping[str, Any], field: str | None) -> str:
    old = change.get("old_value")
    new = change.get("new_value")
    if field != "station_schedule_available" and _blank(old) and not _blank(new):
        return f"{label} published: {_value(new, field)}"
    if field != "station_schedule_available" and not _blank(old) and _blank(new):
        return f"{label} removed (was {_value(old, field)})"
    return f"{label} changed from {_value(old, field)} to {_value(new, field)}"


def _windows_text(row: Any) -> str:
    if not isinstance(row, dict):
        return ""
    parts = []
    if _js_truthy(row.get("sandbox_start_date")):
        window = format_date_range(row.get("sandbox_start_date"), row.get("sandbox_end_date"))
        parts.append(f"sandbox {window}")
    if _js_truthy(row.get("production_start_date")):
        window = format_date_range(row.get("production_start_date"), row.get("production_end_date"))
        parts.append(f"production {window}")
    return ", ".join(parts)


def station_field(field: Any) -> tuple[int | None, str | None]:
    """``"station.4"`` or ``"station.4.sandbox_start_date"`` -> ``(4, field or None)``."""
    match = STATION_FIELD.match(str(field or ""))
    return (int(match.group(1)), match.group(2)) if match else (None, None)


def keyed_field(field: Any) -> tuple[str, str | None]:
    """``"10.0.49#general_availability_date"`` -> ``("10.0.49", "general_availability_date")``."""
    text = str(field or "")
    name, separator, rest = text.partition("#")
    return (name, rest) if separator else (text, None)


def _describe_pqu(change: Mapping[str, Any]) -> tuple[str, str]:
    subject = train_label(change.get("pqu_id"))
    kind = change.get("change_type")
    if kind == "added":
        status = _mapping(_first_truthy(change.get("new_value"))).get("status")
        text = f"Added to Microsoft's schedule as {status}" if _js_truthy(status) else None
        return subject, text or "Added to Microsoft's schedule"
    if kind == "removed":
        status = _mapping(_first_truthy(change.get("old_value"))).get("status")
        if _js_truthy(status):
            return subject, f"Removed from Microsoft's schedule (was {status})"
        return subject, "Removed from Microsoft's schedule"
    field = change.get("field")
    label = PQU_FIELDS.get(str(field)) or _js_string(field)
    return subject, _changed(label, change, field)


def _describe_station(change: Mapping[str, Any]) -> tuple[str, str]:
    subject = train_label(change.get("pqu_id"))
    number, field = station_field(change.get("field"))
    station = "A station" if number is None else f"Station {number}"
    kind = change.get("change_type")
    if kind == "added":
        windows = _windows_text(change.get("new_value"))
        return subject, f"{station} schedule published" + (f": {windows}" if windows else "")
    if kind == "removed":
        return subject, f"{station} schedule removed"
    label = STATION_FIELDS.get(str(field)) or field or "window"
    return subject, _changed(f"{station} {label}", change, field)


def _describe_region(change: Mapping[str, Any]) -> tuple[str, str]:
    name = re.sub(r"^region\.", "", str(change.get("field") or ""))
    row = _mapping(_first_truthy(change.get("new_value"), change.get("old_value")))
    station = "" if row.get("station") is None else f" Station {_js_string(row['station'])}"
    kind = change.get("change_type")
    if kind == "added":
        return name, f"Added to{station or ' the region list'}"
    if kind == "removed":
        return name, f"Removed from{station or ' the region list'}"
    old_row = _mapping(change.get("old_value"))
    new_row = _mapping(change.get("new_value"))
    parts = [
        f"{key.replace('_', ' ')} {_value(old_row[key], key)} \u2192 "
        f"{_value(new_row.get(key), key)}"
        for key in old_row
        if _stringify(old_row[key]) != _stringify(new_row.get(key, _MISSING))
    ]
    return name, "Region details changed" + (f": {'; '.join(parts)}" if parts else "")


def _describe_guidance(
    change: Mapping[str, Any], source_label: SourceLabel | None
) -> tuple[str, str]:
    name, _ = keyed_field(change.get("field"))
    article = source_label(name) if source_label else None
    title = _mapping(_first_truthy(change.get("new_value"), change.get("old_value"))).get("title")
    subject = article or "Microsoft guidance"
    kind = change.get("change_type")
    has_title = _js_truthy(title)
    if kind == "added":
        return subject, f"New section \u201c{title}\u201d" if has_title else "New section"
    if kind == "removed":
        return subject, f"Section \u201c{title}\u201d removed" if has_title else (
            "A section was removed"
        )
    if has_title:
        return subject, f"Microsoft updated the text of \u201c{title}\u201d"
    return subject, "Microsoft updated the text of a section"


def _describe_keyed(
    change: Mapping[str, Any], labels: Mapping[str, str], noun: str, listing: str
) -> tuple[str, str]:
    name, field = keyed_field(change.get("field"))
    kind = change.get("change_type")
    if kind == "added":
        return name, f"Added to {listing}"
    if kind == "removed":
        return name, f"Removed from {listing}"
    label = labels.get(str(field)) or _js_string(field)
    return name, _capitalize(_changed(f"{noun} {label}".strip(), change, field))


def describe_change(
    change: Mapping[str, Any], *, source_label: SourceLabel | None = None
) -> dict[str, str]:
    """``{subject, text, entity, type}`` for one change record."""
    entity = str(change.get("entity") or "")
    if entity == "pqu":
        subject, text = _describe_pqu(change)
    elif entity == "station":
        subject, text = _describe_station(change)
    elif entity == "region":
        subject, text = _describe_region(change)
    elif entity == "guidance":
        subject, text = _describe_guidance(change, source_label)
    elif entity == "service_update":
        subject, text = _describe_keyed(
            change, SERVICE_UPDATE_FIELDS, "", "Microsoft's service update schedule"
        )
    elif entity == "maintenance_window":
        subject, text = _describe_keyed(
            change, MAINTENANCE_FIELDS, "Maintenance window", "Microsoft's maintenance windows"
        )
    else:
        subject = str(change.get("pqu_id") or "")
        label = TYPE_LABELS.get(str(change.get("change_type"))) or "Changed"
        text = f"{label} {change.get('field') or ''}".strip()
    return {
        "subject": subject,
        "text": text,
        "entity": entity,
        "type": str(change.get("change_type") or ""),
    }


def change_href(change: Mapping[str, Any]) -> str | None:
    """Where the dashboard shows the change: a hash route, a Learn section URL, or None."""
    entity = change.get("entity")
    if entity in ("pqu", "station"):
        return f"#/train/{_encode(_js_string(change.get('pqu_id')))}"
    if entity == "service_update":
        name, _ = keyed_field(change.get("field"))
        return f"#/versions?version={_encode(name)}" if name else "#/versions"
    if entity == "region":
        if change.get("change_type") == "removed":
            return None
        name = re.sub(r"^region\.", "", str(change.get("field") or ""))
        return f"#/region/{_encode(name)}" if name else "#/region"
    if entity == "maintenance_window":
        return "#/learn"
    if entity == "guidance":
        row = _mapping(_first_truthy(change.get("new_value"), change.get("old_value")))
        url = str(row.get("url") or "")
        return url if url.lower().startswith("https://") else None
    return None


# ---- Atom ----


def _clean(text: str) -> str:
    return XML_INVALID.sub("", text)


def _add(
    parent: ElementTree.Element, tag: str, text: str | None = None, **attributes: str
) -> ElementTree.Element:
    element = ElementTree.SubElement(parent, tag, attributes)
    if text is not None:
        element.text = _clean(text)
    return element


def _newest(changes: Sequence[Mapping[str, Any]], limit: int) -> list[Mapping[str, Any]]:
    # A stable sort keeps the recorded order for changes found in the same check.
    return sorted(changes, key=lambda change: str(change.get("changed_at") or ""), reverse=True)[
        :limit
    ]


def feed_document(
    changes: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
    *,
    pages_url: str = PAGES_BASE_URL,
    limit: int = FEED_LIMIT,
) -> bytes:
    """The Atom feed for ``changes`` (``changes.json`` records), deterministic for the same data."""
    base = pages_url.rstrip("/")
    sources = _mapping(metadata.get("sources"))
    labels = {
        key: str(entry["label"])
        for key, entry in sources.items()
        if isinstance(entry, dict) and entry.get("label")
    }
    repository = str(_mapping(metadata.get("source")).get("repository") or "")
    if not REPOSITORY.match(repository):
        repository = ""
    entries = _newest(changes, limit)
    updated = (
        str(entries[0].get("changed_at"))
        if entries
        else str(metadata.get("first_published_at") or metadata.get("generated_at") or "")
    )

    feed = ElementTree.Element("feed", {"xmlns": ATOM_NAMESPACE})
    _add(feed, "id", FEED_ID)
    _add(feed, "title", FEED_TITLE)
    _add(feed, "subtitle", FEED_SUBTITLE)
    _add(feed, "updated", updated)
    _add(feed, "link", rel="self", type="application/atom+xml", href=f"{base}/{FEED_FILE}")
    _add(feed, "link", rel="alternate", type="text/html", href=f"{base}/#/changes")
    author = _add(feed, "author")
    _add(author, "name", "D365 PQU dataset")
    repository_link = str(_mapping(metadata.get("links")).get("repository") or "")
    if repository_link.startswith("https://"):
        _add(author, "uri", repository_link)
    _add(feed, "rights", FEED_RIGHTS)
    _add(feed, "generator", "d365-pqu")

    for change in entries:
        described = describe_change(change, source_label=labels.get)
        entity = described["entity"]
        entry = _add(feed, "entry")
        _add(entry, "id", f"{ENTRY_ID_PREFIX}{change.get('change_id')}")
        title = described["text"]
        if described["subject"]:
            title = f"{described['subject']}: {title}"
        _add(entry, "title", title)
        _add(entry, "updated", str(change.get("changed_at")))
        href = change_href(change) or "#/changes"
        link = href if href.startswith("https://") else f"{base}/{href}"
        _add(entry, "link", rel="alternate", type="text/html", href=link)
        commit = str(change.get("source_commit") or "")
        content = f"{described['text']}."
        if repository and COMMIT.match(commit):
            commit_url = f"https://github.com/{repository}/commit/{commit}"
            _add(
                entry,
                "link",
                rel="related",
                type="text/html",
                href=commit_url,
                title=f"Microsoft commit {commit[:7]}",
            )
            content += f" Found in Microsoft commit {commit[:7]} of {repository}."
        _add(entry, "category", term=entity, label=ENTITY_LABELS.get(entity, entity))
        _add(entry, "content", content, type="text")

    ElementTree.indent(feed, space="  ")
    return ElementTree.tostring(feed, encoding="utf-8", xml_declaration=True) + b"\n"
