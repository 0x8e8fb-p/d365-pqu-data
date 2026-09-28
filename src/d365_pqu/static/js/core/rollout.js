/* Geometry for a train's station rollout chart: every sandbox and production window on one
 * shared calendar axis, with today's position. Positions are percentages of the axis. */
(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.rollout = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  function load(name, file) {
    return typeof module === "object" && module.exports ? require(file) : root.PQU[name];
  }
  const dates = load("dates", "./dates.js");

  const KINDS = ["sandbox", "production"];

  /* Day `iso` as the span [start of day, end of day] on an axis of whole days. */
  function span(startIso, endIso, axisStart, totalDays) {
    const from = dates.diffDays(axisStart, startIso);
    const days = dates.diffDays(startIso, endIso) + 1;
    return { left: (from / totalDays) * 100, width: (days / totalDays) * 100 };
  }

  /*
   * rows: station rows for one train. Returns null when no row has a dated window.
   * Otherwise { start, end, days, today|null, ticks[{iso,left}], rows[{station, bars[...]}] }.
   * The axis runs from the earliest window start to the latest window end, whole days.
   */
  function chart(rows, todayIso, options = {}) {
    const windows = [];
    for (const row of rows || []) {
      for (const kind of KINDS) {
        const startIso = row[`${kind}_start_date`];
        if (!dates.isIsoDate(startIso)) {
          continue;
        }
        const endIso = dates.isIsoDate(row[`${kind}_end_date`]) && row[`${kind}_end_date`] >= startIso ? row[`${kind}_end_date`] : startIso;
        windows.push({ station: row.station, kind, startIso, endIso });
      }
    }
    if (!windows.length) {
      return null;
    }
    const start = windows.reduce((min, item) => (item.startIso < min ? item.startIso : min), windows[0].startIso);
    const end = windows.reduce((max, item) => (item.endIso > max ? item.endIso : max), windows[0].endIso);
    const days = dates.diffDays(start, end) + 1;
    const stations = [...new Set((rows || []).map((row) => row.station))].sort((a, b) => a - b);
    const chartRows = stations.map((station) => ({
      station,
      bars: windows
        .filter((item) => item.station === station)
        .map((item) => ({
          kind: item.kind,
          start: item.startIso,
          end: item.endIso,
          ...span(item.startIso, item.endIso, start, days),
          state: dates.isIsoDate(todayIso)
            ? todayIso < item.startIso
              ? "upcoming"
              : todayIso > item.endIso
                ? "done"
                : "current"
            : "upcoming"
        }))
    }));
    let today = null;
    if (dates.isIsoDate(todayIso) && todayIso >= start && todayIso <= end) {
      // Middle of today's column, so the marker sits inside a one-day bar.
      today = ((dates.diffDays(start, todayIso) + 0.5) / days) * 100;
    }
    const ticks = [];
    const step = options.tickDays || (days > 42 ? 14 : 7);
    for (let offset = 0; offset < days; offset += step) {
      const iso = dates.addDays(start, offset);
      ticks.push({ iso, left: (offset / days) * 100 });
    }
    return { start, end, days, today, ticks, rows: chartRows };
  }

  return { chart };
});
