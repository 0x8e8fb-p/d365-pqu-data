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
  const BAR_SEGMENTS = [
    { state: "preview", from: "preview_date", to: "general_availability_date" },
    { state: "available", from: "general_availability_date", to: "first_autoupdate_date" },
    { state: "autoupdate", from: "first_autoupdate_date", to: "second_autoupdate_date" },
    { state: "supported", from: "second_autoupdate_date", to: "end_of_service_date" }
  ];

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

  /* Proportional segments between milestones, plus today's position (percent of the range). */
  function bar(record, todayIso) {
    const list = milestones(record);
    if (list.length < 2) {
      return null;
    }
    const sorted = list.map((item) => item.date).sort();
    const start = sorted[0];
    const end = sorted[sorted.length - 1];
    const span = dates.diffDays(start, end);
    if (!span || span <= 0) {
      return null;
    }
    const position = (iso) => Math.min(100, Math.max(0, (dates.diffDays(start, iso) / span) * 100));
    const segments = [];
    for (const segment of BAR_SEGMENTS) {
      const from = record[segment.from];
      const to = record[segment.to];
      if (dates.isIsoDate(from) && dates.isIsoDate(to) && to > from) {
        const left = position(from);
        segments.push({
          state: segment.state,
          label: STATE_LABELS[segment.state],
          startDate: from,
          endDate: to,
          left,
          width: Math.max(0, position(to) - left)
        });
      }
    }
    const today = dates.isIsoDate(todayIso) && todayIso >= start && todayIso <= end ? position(todayIso) : null;
    return { start, end, segments, today };
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
    bar,
    mergeVersions,
    milestones,
    trainSummary
  };
});
