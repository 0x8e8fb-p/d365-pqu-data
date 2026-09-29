/* Service update lifecycle for a calendar day, from Microsoft's published milestone dates. */
(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.lifecycle = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  function load(name, file) {
    return typeof module === "object" && module.exports ? require(file) : root.PQU[name];
  }
  const dates = load("dates", "./dates.js");
  const versions = load("versions", "./versions.js");

  /* In lifecycle order. `state` is the phase that begins on that date. */
  const MILESTONES = [
    { field: "preview_date", label: "Preview", state: "preview" },
    { field: "preview_latest_update_date", label: "Latest preview update", state: null },
    { field: "general_availability_date", label: "General availability", state: "available" },
    { field: "first_autoupdate_date", label: "First autoupdate", state: "autoupdate" },
    { field: "second_autoupdate_date", label: "Second autoupdate", state: "supported" },
    { field: "end_of_service_date", label: "End of service", state: "end-of-service" }
  ];
  const STATE_LABELS = {
    upcoming: "Upcoming",
    preview: "Preview",
    available: "Generally available",
    autoupdate: "Autoupdate period",
    supported: "Supported",
    "end-of-service": "End of service",
    unknown: "Dates not published"
  };
  /* Phases in which the version is generally available and still serviced. */
  const SERVICED_STATES = ["available", "autoupdate", "supported"];

  function milestones(record) {
    return MILESTONES.filter((item) => record && dates.isIsoDate(record[item.field])).map((item) => ({
      ...item,
      date: record[item.field]
    }));
  }

  function whenText(iso, todayIso) {
    const sameYear = iso.slice(0, 4) === String(todayIso).slice(0, 4);
    return dates.formatDate(iso, { weekday: true, year: !sameYear });
  }

  /* Where todayIso falls in a service update's lifecycle. */
  function assess(record, todayIso) {
    const list = milestones(record);
    const result = {
      state: "unknown",
      label: STATE_LABELS.unknown,
      reached: null,
      next: null,
      daysToNext: null,
      serviced: false,
      summary: STATE_LABELS.unknown,
      milestones: list
    };
    if (!list.length || !dates.isIsoDate(todayIso)) {
      return result;
    }
    const reached = list.filter((item) => item.state && item.date <= todayIso).pop() || null;
    const next = list.find((item) => item.date > todayIso) || null;
    const state = reached ? reached.state : "upcoming";
    result.state = state;
    result.label = STATE_LABELS[state];
    result.reached = reached;
    result.next = next;
    result.serviced = SERVICED_STATES.includes(state);
    if (next) {
      result.daysToNext = dates.diffDays(todayIso, next.date);
    }
    if (state === "end-of-service") {
      result.summary = `End of service · ${dates.daysPhrase(dates.diffDays(todayIso, reached.date))}`;
    } else if (next) {
      result.summary = `${next.label} ${dates.daysPhrase(result.daysToNext)} · ${whenText(next.date, todayIso)}`;
    } else {
      result.summary = result.label;
    }
    return result;
  }

  /* Quarter starts (1 Jan, 1 Apr, 1 Jul, 1 Oct) within [start, end]; January and the first tick
   * carry the year. */
  function quarterTicks(start, end, position) {
    const first = dates.parseIsoDate(start);
    let year = first.year;
    let month = Math.floor((first.month - 1) / 3) * 3 + 1;
    if (first.day !== 1 || month !== first.month) {
      month += 3;
    }
    const ticks = [];
    for (;;) {
      if (month > 12) {
        month -= 12;
        year += 1;
      }
      const iso = `${year}-${dates.pad2(month)}-01`;
      if (iso > end) {
        break;
      }
      ticks.push({
        iso,
        left: position(iso),
        label: month === 1 || ticks.length === 0 ? `${dates.monthName(month)} ${year}` : dates.monthName(month)
      });
      month += 3;
    }
    return ticks;
  }

  /*
   * Every service update on one shared calendar axis, from the earliest published milestone to
   * the latest. Each row has a preview segment (preview to general availability), a service
   * segment (general availability to end of service), marks at the autoupdate dates, and its
   * lifecycle state today. Positions are percentages of the axis; null when there is no axis.
   */
  function chart(records, todayIso) {
    const listed = (records || []).filter((record) => milestones(record).length);
    const all = listed.flatMap((record) => milestones(record).map((item) => item.date)).sort();
    if (!all.length || all[0] === all[all.length - 1]) {
      return null;
    }
    const start = all[0];
    const end = all[all.length - 1];
    const span = dates.diffDays(start, end);
    const position = (iso) => (dates.diffDays(start, iso) / span) * 100;
    const segment = (kind, from, to) => {
      if (!dates.isIsoDate(from) || !dates.isIsoDate(to) || to <= from) {
        return null;
      }
      const left = position(from);
      return { kind, start: from, end: to, left, width: position(to) - left };
    };
    const rows = listed.map((record) => ({
      version: record.version,
      state: assess(record, todayIso).state,
      segments: [
        segment("preview", record.preview_date, record.general_availability_date),
        segment("service", record.general_availability_date, record.end_of_service_date)
      ].filter(Boolean),
      marks: ["first_autoupdate_date", "second_autoupdate_date"]
        .filter((field) => dates.isIsoDate(record[field]))
        .map((field) => ({ field, date: record[field], left: position(record[field]) }))
    }));
    const today = dates.isIsoDate(todayIso) && todayIso >= start && todayIso <= end ? position(todayIso) : null;
    return { start, end, today, ticks: quarterTicks(start, end, position), rows };
  }

  /* One entry per application version from the lifecycle table and/or the train schedule. */
  function mergeVersions(serviceUpdates, trains) {
    const byVersion = new Map();
    for (const record of serviceUpdates || []) {
      byVersion.set(record.version, { version: record.version, lifecycle: record, trains: [] });
    }
    for (const train of trains || []) {
      const version = train.application_version;
      if (!byVersion.has(version)) {
        byVersion.set(version, { version, lifecycle: null, trains: [] });
      }
      byVersion.get(version).trains.push(train);
    }
    return [...byVersion.values()].sort((a, b) => versions.compareVersions(b.version, a.version));
  }

  /* Train counts by Microsoft status and the newest published build for one version. */
  function trainSummary(trains) {
    const counts = {};
    let latest = null;
    for (const train of trains || []) {
      counts[train.status] = (counts[train.status] || 0) + 1;
      if (
        versions.isBuild(train.application_build) &&
        (!latest || versions.compareVersions(train.application_build, latest.application_build) > 0)
      ) {
        latest = train;
      }
    }
    return { total: (trains || []).length, counts, latest };
  }

  return {
    MILESTONES,
    SERVICED_STATES,
    STATE_LABELS,
    assess,
    chart,
    mergeVersions,
    milestones,
    trainSummary
  };
});
