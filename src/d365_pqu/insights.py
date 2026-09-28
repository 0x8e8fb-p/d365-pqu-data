"""Figures calculated from Microsoft's published dates. Microsoft does not publish them.

Each figure records its statistic, sample size, what was left out and why, and the source
articles it is calculated from. Nothing here depends on the current date, so the figures only
change when Microsoft's published data changes.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from itertools import pairwise
from statistics import median
from typing import Any

Row = Mapping[str, Any]
Describe = Callable[[str, int | float, int, int, int], str]

STATUS_ORDER = ("In-Progress", "Not Started", "Completed", "Canceled")
ALL = "all"

CATEGORIES: tuple[dict[str, str], ...] = (
    {"id": "trains", "title": "Train rhythm", "group_label": "Version"},
    {"id": "stations", "title": "Station rollout", "group_label": "Station"},
    {"id": "service-updates", "title": "Service update rhythm", "group_label": "Service updates"},
)

# Warnings about a train's published dates, and the date fields each one makes unreliable.
DATE_FLAG_FIELDS: dict[str, tuple[str, ...]] = {
    "cutoff-start-year-mismatch": ("change_cutoff_date", "train_start_date"),
    "invalid-train-duration": ("train_start_date", "train_end_date"),
    "end-before-start": ("train_start_date", "train_end_date"),
    "invalid-cutoff-date": ("change_cutoff_date",),
}

METRICS: tuple[dict[str, Any], ...] = (
    {
        "id": "train-cadence",
        "category": "trains",
        "title": "Days between train starts",
        "unit": "days",
        "statistic": "median",
        "sample_unit": "intervals",
        "sources": ["schedule"],
        "method": (
            "The trains of each application version are put in train-number order. For each "
            "pair of consecutive train numbers, the days between their published start dates "
            "are counted, and the figure is the median. A train whose start date has a source "
            "warning is left out, together with the intervals next to it."
        ),
    },
    {
        "id": "cutoff-to-start",
        "category": "trains",
        "title": "Change cutoff to train start",
        "unit": "days",
        "statistic": "median",
        "sample_unit": "trains",
        "sources": ["schedule"],
        "method": (
            "For each train, the days from its published change cutoff date to its published "
            "start date. The figure is the median per application version. Trains with a "
            "source warning on either date are left out."
        ),
    },
    {
        "id": "train-length",
        "category": "trains",
        "title": "Train length",
        "unit": "days",
        "statistic": "median",
        "sample_unit": "trains",
        "sources": ["schedule"],
        "method": (
            "Calendar days from each train's published start date to its published end date, "
            "counting both dates (the same count as “Day X of Y” on the Trains tab). The figure "
            "is the median per application version. Trains with a source warning on either "
            "date are left out."
        ),
    },
    {
        "id": "trains-by-status",
        "category": "trains",
        "title": "Trains in the schedule",
        "unit": "trains",
        "statistic": "count",
        "sample_unit": None,
        "sources": ["schedule"],
        "method": (
            "The number of trains Microsoft lists for each application version, broken down by "
            "the status Microsoft publishes."
        ),
    },
    {
        "id": "station-offset",
        "category": "stations",
        "title": "Sandbox start after Station 1",
        "unit": "days",
        "statistic": "median",
        "sample_unit": "trains",
        "sources": ["schedule"],
        "method": (
            "For each train with a detailed station schedule, the days from Station 1's sandbox "
            "start to each other station's sandbox start. The figure is the median per station. "
            "Microsoft's article only lists the most recent detailed schedules, so the sample "
            "is small."
        ),
    },
    {
        "id": "sandbox-to-production",
        "category": "stations",
        "title": "Production start after sandbox start",
        "unit": "days",
        "statistic": "median",
        "sample_unit": "trains",
        "sources": ["schedule"],
        "method": (
            "For each station window with both a sandbox and a production range, the days from "
            "the sandbox start to the production start. The figure is the median per station "
            "and across all stations. Station 1 has no production range."
        ),
    },
    {
        "id": "regions-per-station",
        "category": "stations",
        "title": "Azure regions",
        "unit": "regions",
        "statistic": "count",
        "sample_unit": None,
        "sources": ["schedule"],
        "method": "The number of Azure regions Microsoft maps to each station.",
    },
    {
        "id": "service-update-interval",
        "category": "service-updates",
        "title": "Days between general availability dates",
        "unit": "days",
        "statistic": "median",
        "sample_unit": "intervals",
        "sources": ["service_updates"],
        "method": (
            "Service updates are put in version order. For each pair of consecutive versions, "
            "the days between their general availability dates are counted, and the figure is "
            "the median."
        ),
    },
    {
        "id": "preview-to-ga",
        "category": "service-updates",
        "title": "Preview to general availability",
        "unit": "days",
        "statistic": "median",
        "sample_unit": "service updates",
        "sources": ["service_updates"],
        "method": (
            "For each service update, the days from preview availability to general "
            "availability. The figure is the median."
        ),
    },
    {
        "id": "ga-to-first-autoupdate",
        "category": "service-updates",
        "title": "General availability to first autoupdate",
        "unit": "days",
        "statistic": "median",
        "sample_unit": "service updates",
        "sources": ["service_updates"],
        "method": (
            "For each service update, the days from general availability to the first "
            "production autoupdate start date. The figure is the median."
        ),
    },
    {
        "id": "first-to-second-autoupdate",
        "category": "service-updates",
        "title": "First to second autoupdate",
        "unit": "days",
        "statistic": "median",
        "sample_unit": "service updates",
        "sources": ["service_updates"],
        "method": (
            "For each service update, the days from the first to the second production "
            "autoupdate start date. The figure is the median."
        ),
    },
    {
        "id": "ga-to-end-of-service",
        "category": "service-updates",
        "title": "General availability to end of service",
        "unit": "days",
        "statistic": "median",
        "sample_unit": "service updates",
        "sources": ["service_updates"],
        "method": (
            "For each service update, the days from general availability to end of service. "
            "The figure is the median."
        ),
    },
)
METRICS_BY_ID = {metric["id"]: metric for metric in METRICS}


@dataclass
class _Sample:
    values: list[int] = field(default_factory=list)
    excluded: list[dict[str, str]] = field(default_factory=list)
    breakdown: dict[str, int] = field(default_factory=dict)

    def leave_out(self, item: str, reason: str) -> None:
        entry = {"item": item, "reason": reason}
        if entry not in self.excluded:
            self.excluded.append(entry)


def _day(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _number(value: float) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else round(number, 1)


def _fmt(value: int | float) -> str:
    return str(value) if isinstance(value, int) else f"{value:.1f}"


def _version_key(version: Any) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(version).split("."))
    except ValueError:
        return (0,)


def _days(value: int | float, *, trailing: bool = False) -> str:
    """ "14 days" or "14 days, or 2 weeks"; ``trailing`` closes the aside mid-sentence."""
    text = f"{_fmt(value)} day" if value == 1 else f"{_fmt(value)} days"
    if isinstance(value, int) and value >= 14 and value % 7 == 0:
        text += f", or {value // 7} weeks" + ("," if trailing else "")
    return text


def _basis(size: int, unit: str, low: int, high: int) -> str:
    """Sample wording: "median of 16 intervals; range 14 to 21 days", or "1 train"."""
    singular = unit[:-1] if unit.endswith("s") else unit
    if size == 1:
        return f"1 {singular}"
    text = f"median of {size} {unit}"
    if low != high:
        text += f"; range {_fmt(low)}\u2013{_fmt(high)} days"
    return text


def _flags(quality: Sequence[Row]) -> dict[tuple[str, str], str]:
    """(pqu_id, date field) -> reason, for warnings about a train's published dates."""
    flags: dict[tuple[str, str], str] = {}
    for item in quality:
        pqu_id = item.get("pqu_id")
        if item.get("severity") != "warning" or not pqu_id:
            continue
        fallback = (item["field"],) if item.get("field") else ()
        for date_field in DATE_FLAG_FIELDS.get(str(item.get("code")), fallback):
            flags.setdefault((str(pqu_id), date_field), f"Source warning: {item.get('message')}")
    return flags


def _median_record(
    metric_id: str, group: str, label: str, sample: _Sample, describe: Describe
) -> dict[str, Any] | None:
    if not sample.values:
        return None
    metric = METRICS_BY_ID[metric_id]
    value = _number(median(sample.values))
    low, high = min(sample.values), max(sample.values)
    size = len(sample.values)
    return {
        "id": f"{metric_id}:{group}",
        "metric": metric_id,
        "group": group,
        "label": label,
        "value": value,
        "unit": metric["unit"],
        "statistic": "median",
        "sample_size": size,
        "min": low,
        "max": high,
        "breakdown": dict(sample.breakdown) or None,
        "excluded": list(sample.excluded),
        "summary": describe(label, value, size, low, high),
    }


def _count_record(
    metric_id: str,
    group: str,
    label: str,
    value: int,
    breakdown: dict[str, int] | None,
    summary: str,
) -> dict[str, Any]:
    metric = METRICS_BY_ID[metric_id]
    return {
        "id": f"{metric_id}:{group}",
        "metric": metric_id,
        "group": group,
        "label": label,
        "value": value,
        "unit": metric["unit"],
        "statistic": "count",
        "sample_size": value,
        "min": None,
        "max": None,
        "breakdown": breakdown,
        "excluded": [],
        "summary": summary,
    }


class _Collector:
    """Records and metric-level exclusions for one build."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self.metric_excluded: dict[str, list[dict[str, str]]] = {m["id"]: [] for m in METRICS}

    def add_samples(
        self, metric_id: str, samples: dict[str, tuple[str, _Sample]], describe: Describe
    ) -> None:
        for group, (label, sample) in samples.items():
            record = _median_record(metric_id, group, label, sample, describe)
            if record is not None:
                self.records.append(record)
                continue
            # A group without a figure: keep the reasons its items were left out, if any.
            for entry in sample.excluded:
                if entry not in self.metric_excluded[metric_id]:
                    self.metric_excluded[metric_id].append(entry)


def _by_version(records: Sequence[Row]) -> list[tuple[str, list[Row]]]:
    groups: dict[str, list[Row]] = {}
    for record in records:
        groups.setdefault(str(record["application_version"]), []).append(record)
    return [
        (version, sorted(groups[version], key=lambda row: int(row["release_number"])))
        for version in sorted(groups, key=_version_key)
    ]


def _train_metrics(
    out: _Collector, records: Sequence[Row], flags: dict[tuple[str, str], str]
) -> None:
    cadence: dict[str, tuple[str, _Sample]] = {}
    lead: dict[str, tuple[str, _Sample]] = {}
    length: dict[str, tuple[str, _Sample]] = {}
    for version, trains in _by_version(records):
        sample = cadence.setdefault(version, (version, _Sample()))[1]
        if len(trains) < 2:
            sample.leave_out(version, "Only one train is listed")
        for first, second in pairwise(trains):
            flagged = [
                row for row in (first, second) if (row["pqu_id"], "train_start_date") in flags
            ]
            if flagged:
                for row in flagged:
                    sample.leave_out(row["pqu_id"], flags[(row["pqu_id"], "train_start_date")])
                continue
            left, right = _day(first.get("train_start_date")), _day(second.get("train_start_date"))
            if left is None or right is None:
                for row, day in ((first, left), (second, right)):
                    if day is None:
                        sample.leave_out(row["pqu_id"], "No published start date")
                continue
            if int(second["release_number"]) != int(first["release_number"]) + 1:
                sample.leave_out(
                    f"{first['pqu_id']} to {second['pqu_id']}", "Train numbers are not consecutive"
                )
                continue
            days = (right - left).days
            if days <= 0:
                sample.leave_out(
                    second["pqu_id"], f"Starts on or before the start of {first['pqu_id']}"
                )
                continue
            sample.values.append(days)

        lead_sample = lead.setdefault(version, (version, _Sample()))[1]
        length_sample = length.setdefault(version, (version, _Sample()))[1]
        for row in trains:
            pqu_id = str(row["pqu_id"])
            cutoff = _day(row.get("change_cutoff_date"))
            start = _day(row.get("train_start_date"))
            end = _day(row.get("train_end_date"))
            flag = flags.get((pqu_id, "change_cutoff_date")) or flags.get(
                (pqu_id, "train_start_date")
            )
            if flag:
                lead_sample.leave_out(pqu_id, flag)
            elif cutoff is None or start is None:
                lead_sample.leave_out(pqu_id, "No published change cutoff or start date")
            else:
                lead_sample.values.append((start - cutoff).days)
            flag = flags.get((pqu_id, "train_start_date")) or flags.get((pqu_id, "train_end_date"))
            if flag:
                length_sample.leave_out(pqu_id, flag)
            elif start is None or end is None:
                length_sample.leave_out(pqu_id, "No published start or end date")
            else:
                length_sample.values.append((end - start).days + 1)

    out.add_samples(
        "train-cadence",
        cadence,
        lambda label, value, size, low, high: (
            f"{label}: a new train starts every {_days(value)} "
            f"({_basis(size, 'intervals', low, high)})."
        ),
    )

    def describe_lead(label: str, value: int | float, size: int, low: int, high: int) -> str:
        basis = _basis(size, "trains", low, high)
        if value == 0:
            return f"{label}: the change cutoff falls on the train's start date ({basis})."
        when = "before" if value > 0 else "after"
        return (
            f"{label}: the change cutoff is {_days(abs(value), trailing=True)} {when} the train "
            f"starts ({basis})."
        )

    out.add_samples("cutoff-to-start", lead, describe_lead)
    out.add_samples(
        "train-length",
        length,
        lambda label, value, size, low, high: (
            f"{label}: a train spans {_days(value, trailing=True)} from its start date to its "
            f"end date, both included ({_basis(size, 'trains', low, high)})."
        ),
    )

    for version, trains in _by_version(records):
        counts: dict[str, int] = {}
        for row in trains:
            counts[str(row["status"])] = counts.get(str(row["status"]), 0) + 1
        ordered = {status: counts[status] for status in STATUS_ORDER if status in counts}
        ordered.update(
            {status: count for status, count in sorted(counts.items()) if status not in ordered}
        )
        parts = ", ".join(f"{count} {status}" for status, count in ordered.items())
        total = len(trains)
        noun = "train" if total == 1 else "trains"
        out.records.append(
            _count_record(
                "trains-by-status",
                version,
                version,
                total,
                ordered,
                f"{version}: {total} {noun}: {parts}.",
            )
        )


def _station_metrics(out: _Collector, stations: Sequence[Row], regions: Sequence[Row]) -> None:
    by_train: dict[str, dict[int, Row]] = {}
    for row in stations:
        by_train.setdefault(str(row["pqu_id"]), {})[int(row["station"])] = row
    numbers = sorted(
        {int(row["station"]) for row in stations} | {int(row["station"]) for row in regions}
    )

    def label(station: int) -> str:
        return f"Station {station}"

    offsets = {f"station-{n}": (label(n), _Sample()) for n in numbers if n != 1}
    for pqu_id in sorted(by_train):
        rows = by_train[pqu_id]
        base_row = rows.get(1)
        base = _day(base_row.get("sandbox_start_date")) if base_row else None
        for station, row in sorted(rows.items()):
            if station == 1:
                continue
            sample = offsets.setdefault(f"station-{station}", (label(station), _Sample()))[1]
            start = _day(row.get("sandbox_start_date"))
            if base is None:
                sample.leave_out(pqu_id, "No Station 1 sandbox date")
            elif start is None:
                sample.leave_out(pqu_id, f"No {label(station)} sandbox date")
            else:
                sample.values.append((start - base).days)
    out.add_samples(
        "station-offset",
        offsets,
        lambda name, value, size, low, high: (
            f"{name}: sandbox updates start {_days(value, trailing=True)} after Station 1 "
            f"({_basis(size, 'trains', low, high)})."
        ),
    )

    gaps: dict[str, tuple[str, _Sample]] = {}
    combined = _Sample()
    for row in sorted(stations, key=lambda item: (int(item["station"]), str(item["pqu_id"]))):
        production = _day(row.get("production_start_date"))
        if production is None:
            continue
        station = int(row["station"])
        sample = gaps.setdefault(f"station-{station}", (label(station), _Sample()))[1]
        sandbox = _day(row.get("sandbox_start_date"))
        if sandbox is None:
            sample.leave_out(str(row["pqu_id"]), f"No {label(station)} sandbox date")
            combined.leave_out(str(row["pqu_id"]), f"No {label(station)} sandbox date")
            continue
        days = (production - sandbox).days
        sample.values.append(days)
        combined.values.append(days)
    out.add_samples(
        "sandbox-to-production",
        gaps,
        lambda name, value, size, low, high: (
            f"{name}: production updates start {_days(value, trailing=True)} after sandbox "
            f"updates ({_basis(size, 'trains', low, high)})."
        ),
    )
    out.add_samples(
        "sandbox-to-production",
        {ALL: ("All stations", combined)},
        lambda _name, value, size, low, high: (
            f"Production updates start a median of {_days(value, trailing=True)} after sandbox "
            f"updates ({size} station windows"
            + (f"; range {_fmt(low)}\u2013{_fmt(high)} days" if low != high else "")
            + ")."
        ),
    )

    for station in sorted({int(row["station"]) for row in regions}):
        station_rows = [row for row in regions if int(row["station"]) == station]
        names = [row for row in station_rows if row.get("is_region")]
        if not names:
            reason = "; ".join(str(row["region"]) for row in station_rows) or "No regions listed"
            out.metric_excluded["regions-per-station"].append(
                {"item": label(station), "reason": reason}
            )
            continue
        count = len(names)
        noun = "Azure region" if count == 1 else "Azure regions"
        out.records.append(
            _count_record(
                "regions-per-station",
                f"station-{station}",
                label(station),
                count,
                None,
                f"{label(station)}: {count} {noun}.",
            )
        )


def _consecutive(first: str, second: str) -> bool:
    left, right = _version_key(first), _version_key(second)
    return len(left) == len(right) and left[:-1] == right[:-1] and right[-1] == left[-1] + 1


def _service_update_metrics(out: _Collector, service_updates: Sequence[Row]) -> None:
    updates = sorted(service_updates, key=lambda row: _version_key(row["version"]))
    if not updates:
        return
    interval = _Sample()
    for first, second in pairwise(updates):
        pair = f"{first['version']} to {second['version']}"
        left = _day(first.get("general_availability_date"))
        right = _day(second.get("general_availability_date"))
        if not _consecutive(str(first["version"]), str(second["version"])):
            interval.leave_out(pair, "Version numbers are not consecutive")
        elif left is None or right is None:
            interval.leave_out(pair, "No published general availability date")
        else:
            days = (right - left).days
            interval.values.append(days)
            interval.breakdown[pair] = days
    out.add_samples(
        "service-update-interval",
        {ALL: ("All service updates", interval)},
        lambda _label, value, size, low, high: (
            f"A new service update becomes generally available every {_days(value)} "
            f"({_basis(size, 'intervals', low, high)})."
        ),
    )

    spans: tuple[tuple[str, str, str, str], ...] = (
        (
            "preview-to-ga",
            "preview_date",
            "general_availability_date",
            "General availability comes {days} after preview availability",
        ),
        (
            "ga-to-first-autoupdate",
            "general_availability_date",
            "first_autoupdate_date",
            "The first production autoupdate comes {days} after general availability",
        ),
        (
            "first-to-second-autoupdate",
            "first_autoupdate_date",
            "second_autoupdate_date",
            "The second autoupdate window comes {days} after the first",
        ),
        (
            "ga-to-end-of-service",
            "general_availability_date",
            "end_of_service_date",
            "End of service comes {days} after general availability",
        ),
    )
    for metric_id, start_field, end_field, sentence in spans:
        sample = _Sample()
        for row in updates:
            start, end = _day(row.get(start_field)), _day(row.get(end_field))
            if start is None or end is None:
                sample.leave_out(str(row["version"]), "Date not published")
                continue
            days = (end - start).days
            sample.values.append(days)
            sample.breakdown[str(row["version"])] = days
        out.add_samples(metric_id, {ALL: ("All service updates", sample)}, _span_sentence(sentence))


def _span_sentence(sentence: str) -> Describe:
    def describe(_label: str, value: int | float, size: int, low: int, high: int) -> str:
        return (
            sentence.format(days=_days(value, trailing=True))
            + f" ({_basis(size, 'service updates', low, high)})."
        )

    return describe


def _highlights(records: Sequence[Row]) -> list[str]:
    """The figures shown first: newest train cadence, rollout gap, and service update rhythm."""
    ids = {str(record["id"]) for record in records}
    picks: list[str] = []
    cadence = [record for record in records if record["metric"] == "train-cadence"]
    solid = [record for record in cadence if int(record["sample_size"]) >= 3] or cadence
    if solid:
        picks.append(str(max(solid, key=lambda record: _version_key(record["group"]))["id"]))
    for record_id in (f"sandbox-to-production:{ALL}", f"service-update-interval:{ALL}"):
        if record_id in ids:
            picks.append(record_id)
    return picks


def build_insights(
    *,
    records: Sequence[Row],
    stations: Sequence[Row],
    regions: Sequence[Row],
    service_updates: Sequence[Row],
    quality: Sequence[Row],
) -> dict[str, Any]:
    out = _Collector()
    _train_metrics(out, records, _flags(quality))
    _station_metrics(out, stations, regions)
    _service_update_metrics(out, service_updates)
    metrics = [{**metric, "excluded": out.metric_excluded[metric["id"]]} for metric in METRICS]
    order = {metric["id"]: index for index, metric in enumerate(METRICS)}
    ordered = sorted(enumerate(out.records), key=lambda item: (order[item[1]["metric"]], item[0]))
    records_out = [record for _, record in ordered]
    return {
        "categories": [dict(category) for category in CATEGORIES],
        "metrics": metrics,
        "records": records_out,
        "highlights": _highlights(records_out),
    }
