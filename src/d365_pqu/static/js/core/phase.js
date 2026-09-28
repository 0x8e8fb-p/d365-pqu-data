/* Calculated train phase for a given calendar day. Microsoft's published status is never
 * replaced; this only describes where "today" falls relative to the published dates. */
(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.phase = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  function load(name, file) {
    return typeof module === "object" && module.exports ? require(file) : root.PQU[name];
  }
  const dates = load("dates", "./dates.js");
  const text = load("text", "./text.js");

  const KIND_ORDER = { sandbox: 0, production: 1 };

  function shortDate(iso) {
    return dates.formatDate(iso, { weekday: true, year: false });
  }

  function dayCount(days) {
    return days === 1 ? "1 day" : `${days} days`;
  }

  /* Every published sandbox/production window for the train's stations. */
  function stationWindows(stations) {
    const windows = [];
    for (const row of stations || []) {
      for (const kind of ["sandbox", "production"]) {
        const start = row[`${kind}_start_date`];
        const end = row[`${kind}_end_date`];
        if (dates.isIsoDate(start) && dates.isIsoDate(end)) {
          windows.push({ station: row.station, kind, start, end });
        }
      }
    }
    return windows;
  }

  /* Merge stations that share the same kind and date range. */
  function groupWindows(windows) {
    const groups = new Map();
    for (const window of windows) {
      const key = `${window.kind}|${window.start}|${window.end}`;
      if (!groups.has(key)) {
        groups.set(key, { kind: window.kind, start: window.start, end: window.end, stations: [] });
      }
      groups.get(key).stations.push(window.station);
    }
    return [...groups.values()]
      .map((group) => ({ ...group, stations: group.stations.sort((a, b) => a - b) }))
      .sort(
        (a, b) =>
          a.start.localeCompare(b.start) ||
          KIND_ORDER[a.kind] - KIND_ORDER[b.kind] ||
          a.stations[0] - b.stations[0]
      );
  }

  function stationActivity(stations, todayIso) {
    const windows = stationWindows(stations);
    if (windows.length === 0) {
      return { state: "none", active: [], next: [], windows };
    }
    const active = groupWindows(windows.filter((w) => w.start <= todayIso && todayIso <= w.end));
    const upcoming = windows.filter((w) => w.start > todayIso);
    let next = [];
    if (upcoming.length) {
      const earliest = upcoming.reduce((min, w) => (w.start < min ? w.start : min), upcoming[0].start);
      next = groupWindows(upcoming.filter((w) => w.start === earliest));
    }
    const state = active.length ? "active" : next.length ? "upcoming" : "done";
    return { state, active, next, windows };
  }

  function groupLabel(group) {
    return `${text.stationList(group.stations)} ${group.kind}`;
  }

  function activityText(activity, todayIso) {
    if (activity.state === "active") {
      return `Now: ${activity.active
        .map((group) => `${groupLabel(group)} (${dates.formatDateRange(group.start, group.end, { year: false })})`)
        .join("; ")}`;
    }
    if (activity.state === "upcoming") {
      const start = activity.next[0].start;
      const labels = text.joinList(activity.next.map(groupLabel));
      return `Next: ${labels} from ${dates.formatDate(start, { year: false })} (${dates.daysPhrase(
        dates.diffDays(todayIso, start)
      )})`;
    }
    if (activity.state === "done") {
      return "All published station windows have passed";
    }
    return null;
  }

  /*
   * Returns { kind, text, detail, conflict, activity, dayNumber, dayCount }.
   * kind: canceled | completed | unknown | before-cutoff | cutoff-today | before-start | running |
   * ended. Completed and Canceled trains get no calculated line: Microsoft's status is final.
   */
  function compute(record, stations, todayIso, options = {}) {
    const result = {
      kind: "unknown",
      text: null,
      detail: null,
      conflict: null,
      activity: null,
      dayNumber: null,
      dayCount: null
    };
    if (!record || !dates.isIsoDate(todayIso)) {
      return result;
    }
    const status = record.status;
    const cutoff = record.change_cutoff_date;
    const start = record.train_start_date;
    const end = record.train_end_date;
    if (status === "Canceled") {
      return { ...result, kind: "canceled" };
    }
    if (status === "Completed") {
      return { ...result, kind: "completed" };
    }
    if (!dates.isIsoDate(start) || !dates.isIsoDate(end)) {
      return result;
    }
    const activity = stationActivity(stations, todayIso);
    result.activity = activity;

    if (todayIso < start) {
      const cutoffDays = dates.isIsoDate(cutoff) ? dates.diffDays(todayIso, cutoff) : null;
      const startDays = dates.diffDays(todayIso, start);
      if (cutoffDays !== null && cutoffDays > 0) {
        result.kind = "before-cutoff";
        result.text =
          cutoff === start
            ? `Cutoff and start ${dates.daysPhrase(cutoffDays)} · ${shortDate(cutoff)}`
            : `Change cutoff ${dates.daysPhrase(cutoffDays)} · ${shortDate(cutoff)}`;
      } else if (cutoffDays === 0) {
        result.kind = "cutoff-today";
        result.text = `Change cutoff today · starts ${dates.daysPhrase(startDays)}`;
      } else {
        result.kind = "before-start";
        result.text = `Starts ${dates.daysPhrase(startDays)} · ${shortDate(start)}`;
      }
    } else if (todayIso <= end) {
      result.kind = "running";
      result.dayNumber = dates.diffDays(start, todayIso) + 1;
      result.dayCount = dates.diffDays(start, end) + 1;
      result.text = `Day ${result.dayNumber} of ${result.dayCount}`;
      result.detail =
        activity.state === "none"
          ? "No detailed station schedule in the current article"
          : activityText(activity, todayIso);
    } else {
      result.kind = "ended";
      result.text = `Scheduled end passed ${dayCount(dates.diffDays(end, todayIso))} ago`;
      if (activity.state === "active" || activity.state === "upcoming") {
        result.detail = activityText(activity, todayIso);
      }
    }

    const updated = dates.isIsoDate(options.markdownDate)
      ? ` (article updated ${dates.formatDate(options.markdownDate)})`
      : "";
    const windowsOpen = activity.state === "active" || activity.state === "upcoming";
    if (status === "Not Started" && todayIso >= start) {
      result.conflict = `Microsoft still lists this train as Not Started${updated}.`;
    } else if (status === "In-Progress" && todayIso > end && !windowsOpen) {
      result.conflict = `Microsoft still lists this train as In-Progress${updated}.`;
    }
    return result;
  }

  function searchText(phase) {
    return phase ? [phase.text, phase.detail, phase.conflict].filter(Boolean).join(" ") : "";
  }

  return { activityText, compute, groupWindows, searchText, stationActivity, stationWindows };
});
