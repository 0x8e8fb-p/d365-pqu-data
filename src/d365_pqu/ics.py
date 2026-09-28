"""iCalendar subscriptions (RFC 5545 with the RFC 7986 calendar properties) built from the key
dates in ``events.json``.

``calendar/station-N.ics`` holds Station N's sandbox and production windows and
``calendar/milestones.ics`` every change cutoff and service update milestone. Events are all-day
(``VALUE=DATE``, exclusive end date) and marked free (``TRANSP:TRANSPARENT``). Each UID comes from
the event identifier, which names what an event is rather than when it happens, so when Microsoft
moves a date a subscribed calendar moves the event instead of adding a second one. The output is
deterministic for the same data: DTSTAMP is the dataset's ``generated_at``, not the build time.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any
from urllib.parse import quote, urlparse

from d365_pqu.config import (
    ALLOWED_STATIONS,
    CHECK_INTERVAL_MINUTES,
    DEFAULT_REPO_SLUG,
    PAGES_BASE_URL,
)
from d365_pqu.events import SERVICE_UPDATE_FIELDS

Row = Mapping[str, Any]

CALENDAR_DIR = "calendar"
MILESTONES_FILE = "milestones.ics"
LINE_LIMIT = 75
STATION_KINDS = ("sandbox_window", "production_window")
MILESTONE_KINDS = ("change_cutoff", *SERVICE_UPDATE_FIELDS)
CATEGORIES = {
    "sandbox_window": "Sandbox window",
    "production_window": "Production window",
    "change_cutoff": "Change cutoff",
    **dict.fromkeys(SERVICE_UPDATE_FIELDS, "Service update"),
}
PRODID = f"-//{DEFAULT_REPO_SLUG.split('/')[0]}//D365 PQU dataset//EN"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
TRAIN_ID = re.compile(r"^(\d+\.\d+\.\d+)-(PQU-\d+)$")
# CONTROL characters are not allowed in TEXT values (RFC 5545 section 3.3.11); HTAB is.
CONTROL = re.compile("[\x00-\x08\x0b-\x1f\x7f]")
ATTRIBUTION = "Values from Microsoft Learn (CC BY 4.0). Not affiliated with Microsoft."


def station_file(station: int) -> str:
    return f"station-{station}.ics"


def uid_domain(pages_url: str = PAGES_BASE_URL) -> str:
    return urlparse(pages_url).hostname or "localhost"


# ---- Content lines ----


def escape_text(value: Any) -> str:
    """A TEXT value: backslash, semicolon, comma and newline escaped; control characters dropped."""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = CONTROL.sub("", text)
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line: str) -> bytes:
    """Fold a content line into 75-octet lines without splitting a UTF-8 character."""
    data = line.encode("utf-8")
    parts: list[bytes] = []
    start = 0
    limit = LINE_LIMIT
    while True:
        end = min(start + limit, len(data))
        # Never end a line inside a multi-octet character (continuation bytes are 10xxxxxx).
        while end < len(data) and (data[end] & 0xC0) == 0x80:
            end -= 1
        parts.append(data[start:end])
        if end >= len(data):
            break
        start = end
        limit = LINE_LIMIT - 1  # A continuation line starts with one space.
    return b"\r\n ".join(parts)


def unfold(document: bytes) -> list[str]:
    """Content lines of an iCalendar document, unfolded (for tests and readers)."""
    text = document.decode("utf-8").replace("\r\n ", "").replace("\r\n\t", "")
    return [line for line in text.split("\r\n") if line]


def duration(minutes: int) -> str:
    """RFC 5545 duration: 60 -> ``PT1H``, 90 -> ``PT1H30M``, 1440 -> ``P1D``."""
    if minutes <= 0:
        raise ValueError("duration must be positive")
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    text = f"P{days}D" if days else "P"
    if rest:
        text += "T" + (f"{hours}H" if hours else "") + (f"{mins}M" if mins else "")
    return text


def interval_text(minutes: int) -> str:
    if minutes % 60 == 0:
        hours = minutes // 60
        return "every hour" if hours == 1 else f"every {hours} hours"
    return f"every {minutes} minutes"


def _stamp(value: Any) -> str:
    moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _ics_date(value: str, days: int = 0) -> str:
    return (date.fromisoformat(value) + timedelta(days=days)).strftime("%Y%m%d")


# ---- Wording ----


def _format_date(value: str) -> str:
    day = date.fromisoformat(value)
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def _format_range(start: str, end: str) -> str:
    first = date.fromisoformat(start)
    last = date.fromisoformat(end)
    if first == last:
        return _format_date(start)
    if (first.year, first.month) == (last.year, last.month):
        return f"{first.day}\u2013{last.day} {MONTHS[last.month - 1]} {last.year}"
    if first.year == last.year:
        return f"{first.day} {MONTHS[first.month - 1]} \u2013 {_format_date(end)}"
    return f"{_format_date(start)} \u2013 {_format_date(end)}"


def _train_label(pqu_id: Any) -> str:
    text = str(pqu_id or "")
    match = TRAIN_ID.match(text)
    return f"{match.group(1)} {match.group(2)}" if match else text


def _sentence(text: str) -> str:
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else f"{text}."


def _join(items: Sequence[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


class _Context:
    def __init__(
        self,
        events: Sequence[Row],
        *,
        quality: Sequence[Row],
        metadata: Row,
        pages_url: str,
    ) -> None:
        self.base = pages_url.rstrip("/")
        self.domain = uid_domain(pages_url)
        stamp = metadata.get("generated_at") or metadata.get("first_published_at")
        if not stamp:
            raise ValueError("metadata has no generated_at; cannot stamp the calendars")
        self.dtstamp = _stamp(stamp)
        interval = metadata.get("check_interval_minutes")
        self.interval = int(interval) if isinstance(interval, int) else CHECK_INTERVAL_MINUTES
        self.trains = {
            str(event.get("pqu_id")): event
            for event in events
            if event.get("kind") == "train_window"
        }
        self.messages: dict[tuple[str, str], str] = {}
        for item in quality:
            subject = item.get("pqu_id") or item.get("field")
            if item.get("severity") == "warning" and subject and item.get("message"):
                key = (str(subject), str(item.get("code")))
                self.messages.setdefault(key, str(item["message"]))

    def details_url(self, event: Row) -> str:
        if event.get("pqu_id"):
            return f"{self.base}/#/train/{quote(str(event['pqu_id']), safe='')}"
        return f"{self.base}/#/versions?version={quote(str(event.get('application_version')), safe='')}"

    def warning_lines(self, event: Row) -> list[str]:
        lines = []
        for code in event.get("warnings") or []:
            if event.get("pqu_id"):
                subject = str(event["pqu_id"])
            else:
                field = SERVICE_UPDATE_FIELDS.get(str(event.get("kind")), "")
                subject = f"{event.get('application_version')}#{field}"
            message = self.messages.get((subject, str(code)), str(code))
            lines.append(f"Source warning: {_sentence(message)}")
        return lines


def _description(event: Row, context: _Context) -> str:
    kind = str(event.get("kind"))
    label = _train_label(event.get("pqu_id"))
    status = event.get("status")
    lines = context.warning_lines(event)
    if kind in STATION_KINDS:
        window = "Sandbox" if kind == "sandbox_window" else "Production"
        lines.append(f"{window} window for Station {event.get('station')}, {label}.")
        if status:
            lines.append(f"Microsoft status of the train: {status}.")
        lines.append("Dates from Microsoft's detailed station schedule; Microsoft can change them.")
    elif kind == "change_cutoff":
        lines.append(
            f"Microsoft's change cutoff for {label}: the date after which new changes are no "
            "longer accepted."
        )
        train = context.trains.get(str(event.get("pqu_id")))
        if train:
            window = _format_range(train["start_date"], train["end_date"])
            # A questioned train date is reported as Microsoft's value, not stated as fact.
            if train.get("warnings"):
                lines.append(f"Microsoft lists the train as running {window}.")
            else:
                lines.append(f"The train runs {window}.")
        if status:
            lines.append(f"Microsoft status: {status}.")
    else:
        lines.append(
            "From Microsoft's targeted release schedule for service updates (dates subject to "
            "change)."
        )
    lines.append(f"Details: {context.details_url(event)}")
    if event.get("url"):
        lines.append(f"Source: {event['url']}")
    return "\n".join(lines)


def _summary(event: Row) -> str:
    summary = str(event.get("title"))
    if event.get("status") == "Canceled":
        summary += " (Canceled)"
    if event.get("warnings"):
        summary += " (source warning)"
    return summary


def _event_lines(event: Row, context: _Context) -> list[str]:
    kind = str(event.get("kind"))
    lines = [
        "BEGIN:VEVENT",
        f"UID:{escape_text(event['id'])}@{context.domain}",
        f"DTSTAMP:{context.dtstamp}",
        f"DTSTART;VALUE=DATE:{_ics_date(str(event['start_date']))}",
        # All-day events end on the day after the last day (the end is exclusive).
        f"DTEND;VALUE=DATE:{_ics_date(str(event['end_date']), days=1)}",
        f"SUMMARY:{escape_text(_summary(event))}",
        f"DESCRIPTION:{escape_text(_description(event, context))}",
        f"URL:{context.details_url(event)}",
        f"CATEGORIES:{escape_text(CATEGORIES.get(kind, kind))}",
        "TRANSP:TRANSPARENT",
    ]
    if event.get("status") == "Canceled":
        lines.append("STATUS:CANCELLED")
    lines.append("END:VEVENT")
    return lines


def calendar_document(
    events: Sequence[Row],
    *,
    name: str,
    description: str,
    file_name: str,
    page_route: str,
    context: _Context,
) -> bytes:
    """One VCALENDAR; ``events`` are ``events.json`` records in the order to publish them."""
    refresh = duration(context.interval)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"NAME:{escape_text(name)}",
        f"X-WR-CALNAME:{escape_text(name)}",
        f"DESCRIPTION:{escape_text(description)}",
        f"X-WR-CALDESC:{escape_text(description)}",
        f"URL:{context.base}/{page_route}",
        f"SOURCE;VALUE=URI:{context.base}/{CALENDAR_DIR}/{file_name}",
        f"REFRESH-INTERVAL;VALUE=DURATION:{refresh}",
        f"X-PUBLISHED-TTL:{refresh}",
    ]
    for event in events:
        lines.extend(_event_lines(event, context))
    lines.append("END:VCALENDAR")
    return b"\r\n".join(fold(line) for line in lines) + b"\r\n"


def _station_regions(regions: Sequence[Row], station: int) -> str:
    rows = [row for row in regions if row.get("station") == station]
    names = sorted(str(row["region"]) for row in rows if row.get("is_region"))
    notes = [str(row["region"]) for row in rows if not row.get("is_region") and row.get("region")]
    parts = []
    if names:
        parts.append(f"Regions on Station {station}: {_join(names)}.")
    parts.extend(f"Station {station}: {_sentence(note)}" for note in notes)
    return " ".join(parts)


def _tail(context: _Context, *, current: str) -> str:
    return (
        f"{current} Microsoft's articles are checked {interval_text(context.interval)}; calendar "
        f"apps refresh subscriptions on their own schedule. {ATTRIBUTION}"
    )


def calendar_files(
    events: Sequence[Row],
    *,
    regions: Sequence[Row],
    quality: Sequence[Row],
    metadata: Row,
    pages_url: str = PAGES_BASE_URL,
) -> dict[str, dict[str, Any]]:
    """File name -> {name, description, events (count), content (bytes)} for every calendar."""
    context = _Context(events, quality=quality, metadata=metadata, pages_url=pages_url)
    files: dict[str, dict[str, Any]] = {}
    for station in ALLOWED_STATIONS:
        chosen = [
            event
            for event in events
            if event.get("kind") in STATION_KINDS and event.get("station") == station
        ]
        name = f"PQU Station {station} windows"
        description = " ".join(
            part
            for part in (
                f"Sandbox and production windows for Station {station} from Microsoft's detailed "
                "station schedule for proactive quality updates.",
                _station_regions(regions, station),
                _tail(
                    context,
                    current=(
                        "This calendar lists the windows in Microsoft's current article; when "
                        "Microsoft removes a train's detailed schedule, its windows leave this "
                        "calendar."
                    ),
                ),
            )
            if part
        )
        files[station_file(station)] = {
            "name": name,
            "description": description,
            "events": len(chosen),
            "content": calendar_document(
                chosen,
                name=name,
                description=description,
                file_name=station_file(station),
                page_route="#/region",
                context=context,
            ),
        }
    chosen = [event for event in events if event.get("kind") in MILESTONE_KINDS]
    name = "PQU change cutoffs and service updates"
    description = (
        "Change cutoffs for every train in Microsoft's release schedule for proactive quality "
        "updates, and service update milestones (preview, general availability, autoupdates and "
        "end of service) from Microsoft's targeted release schedule. "
        + _tail(context, current="Microsoft can change these dates.")
    )
    files[MILESTONES_FILE] = {
        "name": name,
        "description": description,
        "events": len(chosen),
        "content": calendar_document(
            chosen,
            name=name,
            description=description,
            file_name=MILESTONES_FILE,
            page_route="#/",
            context=context,
        ),
    }
    return files
