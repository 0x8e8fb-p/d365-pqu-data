"""Planned maintenance windows by geography, and the match from Azure region names to them.

Microsoft publishes the station-to-region mapping (schedule article) and the maintenance window
per geography (maintenance article) separately and does not publish the join between them. The
join here is derived from the names only: a region maps to a geography when every word of the
geography name appears, in order, in the region name (``North Europe`` -> ``Europe``). Regions
that cannot be matched are reported instead of guessed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from d365_pqu import mdtext
from d365_pqu.errors import ParserError
from d365_pqu.learn import ArticleRules
from d365_pqu.models import QualityItem, RegionRecord

MAINTENANCE_HEADERS = ("Geo", "Start time", "Days", "Maintenance window")
MAINTENANCE_RULES = ArticleRules(dataset_tables={MAINTENANCE_HEADERS: "maintenance_windows"})
MAINTENANCE_WINDOW_FIELDS = ("start_time_utc", "days", "duration_hours", "duration_text")
WEEKDAYS = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
_WEEKDAY_NAMES = {
    **{name.casefold(): name for name in WEEKDAYS},
    **{name[:3].casefold(): name for name in WEEKDAYS},
    "tues": "Tuesday",
    "weds": "Wednesday",
    "thur": "Thursday",
    "thurs": "Thursday",
}
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "twenty-four": 24,
}
_START_TIME = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})(?:\s*(?:UTC|GMT))?$", re.IGNORECASE)
_DURATION = re.compile(
    r"^(?P<amount>\d+(?:\.\d+)?|[a-z]+(?:-[a-z]+)?)\s*(?P<unit>hours?|hrs?|h|minutes?|mins?)$",
    re.IGNORECASE,
)
_DAY_SEPARATORS = re.compile(r"\s*(?:,|;|/|&|\band\b)\s*", re.IGNORECASE)
_TOKEN = re.compile(r"[a-z0-9]+")
# Region and geography names use these abbreviations interchangeably with the full names.
ALIASES = {
    "uk": ("united", "kingdom"),
    "uae": ("united", "arab", "emirates"),
    "us": ("united", "states"),
    "usa": ("united", "states"),
    "gov": ("government",),
}
# Words that mark government and defense clouds. Such a region only matches a geography whose
# own name carries the same word; it is never assigned a commercial geography's window.
SOVEREIGN_TOKENS = frozenset({"dod", "gov", "government", "gcc"})


def _warning(code: str, message: str, field: str | None = None) -> QualityItem:
    return QualityItem(code=code, severity="warning", message=message, pqu_id=None, field=field)


def parse_start_time(value: str) -> str | None:
    match = _START_TIME.match(mdtext.collapse(value))
    if not match:
        return None
    hour, minute = int(match.group("hour")), int(match.group("minute"))
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def parse_days(value: str) -> list[str] | None:
    parts = [part for part in _DAY_SEPARATORS.split(mdtext.collapse(value)) if part]
    days: list[str] = []
    for part in parts:
        name = _WEEKDAY_NAMES.get(part.casefold().rstrip("."))
        if name is None:
            return None
        if name not in days:
            days.append(name)
    return days or None


def parse_duration_hours(value: str) -> int | float | None:
    match = _DURATION.match(mdtext.collapse(value))
    if not match:
        return None
    amount_text = match.group("amount").casefold()
    if amount_text[0].isdigit():
        amount = float(amount_text)
    elif amount_text in _NUMBER_WORDS:
        amount = float(_NUMBER_WORDS[amount_text])
    else:
        return None
    hours = amount / 60 if match.group("unit").casefold().startswith("m") else amount
    if not 0 < hours <= 24:
        return None
    return int(hours) if hours.is_integer() else round(hours, 4)


def parse_maintenance_windows(markdown: str) -> tuple[list[dict[str, Any]], list[QualityItem]]:
    """Maintenance windows in Microsoft's order, plus non-fatal findings.

    Rows without a readable start time or day list cannot describe a window and are reported as
    warnings; an unreadable duration keeps the row with ``duration_hours`` set to ``None``.
    """
    rows = mdtext.find_table(markdown, MAINTENANCE_HEADERS)
    if rows is None:
        raise ParserError("Planned maintenance window table was not found or its headers changed")
    records: list[dict[str, Any]] = []
    quality: list[QualityItem] = []
    seen: set[str] = set()
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        geo = mdtext.collapse(row[0]) if row else ""
        if len(row) != len(MAINTENANCE_HEADERS) or not geo:
            quality.append(
                _warning("maintenance-window-row-invalid", f"Unexpected maintenance row: {row!r}")
            )
            continue
        if geo.casefold() in seen:
            quality.append(
                _warning("maintenance-window-duplicate", f"Geography {geo} is listed twice", geo)
            )
            continue
        start = parse_start_time(row[1])
        days = parse_days(row[2])
        if start is None or days is None:
            problem = "start time" if start is None else "days"
            value = row[1] if start is None else row[2]
            quality.append(
                _warning(
                    "maintenance-window-row-invalid",
                    f"Maintenance window for {geo}: could not read {problem} {value!r}",
                    geo,
                )
            )
            continue
        duration_text = mdtext.collapse(row[3])
        duration = parse_duration_hours(duration_text)
        if duration is None:
            quality.append(
                _warning(
                    "maintenance-window-duration-invalid",
                    f"Maintenance window for {geo}: could not read duration {duration_text!r}",
                    f"{geo}#duration_hours",
                )
            )
        seen.add(geo.casefold())
        records.append(
            {
                "geo": geo,
                "start_time_utc": start,
                "days": days,
                "duration_hours": duration,
                "duration_text": duration_text,
            }
        )
    if not records:
        raise ParserError("Planned maintenance window table contained no readable rows")
    return records, quality


def name_tokens(text: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for token in _TOKEN.findall(text.casefold()):
        tokens.extend(ALIASES.get(token, (token,)))
    return tuple(tokens)


def _contains(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    size = len(needle)
    return size > 0 and any(
        haystack[index : index + size] == needle for index in range(len(haystack) - size + 1)
    )


@dataclass(frozen=True)
class GeoMatch:
    geo: str | None
    reason: str  # matched | sovereign | unmatched | ambiguous
    candidates: tuple[str, ...] = ()


def match_region(region: str, geos: Sequence[str]) -> GeoMatch:
    tokens = name_tokens(region)
    sovereign = SOVEREIGN_TOKENS & set(tokens)
    candidates: list[tuple[int, str]] = []
    for geo in geos:
        geo_tokens = name_tokens(geo)
        if sovereign and not sovereign & set(geo_tokens):
            continue
        if _contains(tokens, geo_tokens):
            candidates.append((len(geo_tokens), geo))
    if not candidates:
        return GeoMatch(None, "sovereign" if sovereign else "unmatched")
    longest = max(length for length, _ in candidates)
    best = sorted(geo for length, geo in candidates if length == longest)
    if len(best) > 1:
        return GeoMatch(None, "ambiguous", tuple(best))
    return GeoMatch(best[0], "matched")


def assign_maintenance_geos(
    regions: list[RegionRecord], windows: Sequence[Mapping[str, Any]]
) -> list[QualityItem]:
    """Set ``maintenance_geo`` on every region record and report regions without one."""
    geos = [str(window["geo"]) for window in windows]
    quality: list[QualityItem] = []
    for region in regions:
        region["maintenance_geo"] = None
        if not region["is_region"]:
            continue
        name = region["region"]
        match = match_region(name, geos)
        region["maintenance_geo"] = match.geo
        field = f"region.{name}"
        if match.reason == "sovereign":
            quality.append(
                QualityItem(
                    code="maintenance-geo-unmapped",
                    severity="info",
                    message=(
                        f"Microsoft's planned maintenance window table does not list a geography "
                        f"for {name}, so no maintenance window is shown for it."
                    ),
                    pqu_id=None,
                    field=field,
                )
            )
        elif match.reason == "unmatched":
            quality.append(
                _warning(
                    "maintenance-geo-unmatched",
                    (
                        f"Region {name} does not match any geography in Microsoft's planned "
                        "maintenance window table."
                    ),
                    field,
                )
            )
        elif match.reason == "ambiguous":
            quality.append(
                _warning(
                    "maintenance-geo-ambiguous",
                    (
                        f"Region {name} matches more than one geography "
                        f"({', '.join(match.candidates)}) in Microsoft's planned maintenance "
                        "window table."
                    ),
                    field,
                )
            )
    return quality
