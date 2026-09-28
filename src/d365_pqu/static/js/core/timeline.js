/* Geometry for the trains timeline: one lane per application version, one bar per train from
 * its published start date to its end date, change cutoff ticks, month grid lines and today's
 * position. Positions are percentages of the visible range.
 *
 * Nothing is estimated. A train without a published start date, or whose start or end date is
 * questioned by a source warning, is reported as not drawn instead of being placed. */
(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.timeline = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  function load(name, file) {
    return typeof module === "object" && module.exports ? require(file) : root.PQU[name];
  }
  const dates = load("dates", "./dates.js");
  const versions = load("versions", "./versions.js");

  /* Fixed ranges keep today about a third of the way in: some recent history, more future. */
  const ZOOMS = [
    { id: "3m", label: "3 months", before: 30, after: 61 },
    { id: "6m", label: "6 months", before: 61, after: 122 },
    { id: "all", label: "All dates" }
  ];
  const DEFAULT_ZOOM = "3m";
  const BAR_FIELDS = ["train_start_date", "train_end_date"];

  function zoomOf(id) {
    return ZOOMS.find((zoom) => zoom.id === id) || ZOOMS.find((zoom) => zoom.id === DEFAULT_ZOOM);
  }

  /*
   * A train's drawable dates: {start, end, cutoff|null}, or {reason: "undated" | "unreliable",
   * fields} when it cannot be placed. `unreliable` is a Set of date fields a source warning
   * questions. A missing or earlier end date draws a one-day bar at the start.
   */
  function extent(record, unreliable) {
    const flagged = unreliable || new Set();
    const start = record.train_start_date;
    if (!dates.isIsoDate(start)) {
      return { reason: "undated", fields: [] };
    }
    const fields = BAR_FIELDS.filter((field) => flagged.has(field));
    if (fields.length) {
      return { reason: "unreliable", fields };
    }
    const endValue = record.train_end_date;
    const end = dates.isIsoDate(endValue) && endValue >= start ? endValue : start;
    const cutoffValue = record.change_cutoff_date;
    const cutoff = dates.isIsoDate(cutoffValue) && !flagged.has("change_cutoff_date") ? cutoffValue : null;
    return { start, end, cutoff };
  }

  function firstDay(item) {
    return item.cutoff && item.cutoff < item.start ? item.cutoff : item.start;
  }

  /* The visible range [start, end] (inclusive days), or null when nothing can be shown. */
  function range(zoomId, todayIso, extents) {
    const zoom = zoomOf(zoomId);
    if (zoom.id !== "all") {
      if (!dates.isIsoDate(todayIso)) {
        return null;
      }
      const start = dates.addDays(todayIso, -zoom.before);
      const end = dates.addDays(todayIso, zoom.after);
      return { start, end, days: dates.diffDays(start, end) + 1 };
    }
    let start = null;
    let end = null;
    for (const item of extents) {
      const first = firstDay(item);
      if (start === null || first < start) {
        start = first;
      }
      if (end === null || item.end > end) {
        end = item.end;
      }
    }
    return start === null ? null : { start, end, days: dates.diffDays(start, end) + 1 };
  }

  function position(iso, visible, middle = false) {
    return ((dates.diffDays(visible.start, iso) + (middle ? 0.5 : 0)) / visible.days) * 100;
  }

  /* Grid lines on the first of each month; the year is shown on the first label and in January. */
  function months(visible) {
    const parsed = dates.parseIsoDate(visible.start);
    let year = parsed.year;
    let month = parsed.month;
    if (parsed.day !== 1) {
      month += 1;
    }
    const list = [];
    for (;;) {
      if (month > 12) {
        month = 1;
        year += 1;
      }
      const iso = `${year}-${dates.pad2(month)}-01`;
      if (iso > visible.end) {
        break;
      }
      list.push({
        iso,
        left: position(iso, visible),
        label: dates.monthName(month),
        year: list.length === 0 || month === 1 ? String(year) : null
      });
      month += 1;
    }
    return list;
  }

  function bar(record, item, visible) {
    const from = item.start < visible.start ? visible.start : item.start;
    const to = item.end > visible.end ? visible.end : item.end;
    const left = position(from, visible);
    const right = ((dates.diffDays(visible.start, to) + 1) / visible.days) * 100;
    const cutoffShown = item.cutoff && item.cutoff >= visible.start && item.cutoff <= visible.end;
    return {
      pqu_id: record.pqu_id,
      record,
      start: item.start,
      end: item.end,
      cutoff: item.cutoff,
      left,
      width: right - left,
      clipStart: item.start < visible.start,
      clipEnd: item.end > visible.end,
      cutoffLeft: cutoffShown ? position(item.cutoff, visible, true) : null,
      row: 0
    };
  }

  /* Greedy packing: each bar takes the first row that is free from its cutoff to its end. */
  function pack(bars) {
    const rowEnds = [];
    for (const item of bars) {
      const first = firstDay(item);
      let row = rowEnds.findIndex((end) => end < first);
      if (row === -1) {
        row = rowEnds.length;
        rowEnds.push(item.end);
      } else {
        rowEnds[row] = item.end;
      }
      item.row = row;
    }
    return Math.max(1, rowEnds.length);
  }

  /*
   * records: the trains to show (already filtered). options: {zoom, todayIso, unreliable:
   * {pqu_id: Set(date fields)}}. Returns {zoom, start, end, days, today, months, lanes[{version,
   * rows, bars[]}], drawn, outside[], unreliable[{record, fields}], undated[]}.
   */
  function layout(records, options = {}) {
    const zoom = zoomOf(options.zoom);
    const flags = options.unreliable || {};
    const placed = [];
    const unreliable = [];
    const undated = [];
    for (const record of records || []) {
      const item = extent(record, flags[record.pqu_id]);
      if (item.reason === "undated") {
        undated.push(record);
      } else if (item.reason === "unreliable") {
        unreliable.push({ record, fields: item.fields });
      } else {
        placed.push({ record, item });
      }
    }
    const visible = range(
      zoom.id,
      options.todayIso,
      placed.map((entry) => entry.item)
    );
    const result = {
      zoom: zoom.id,
      start: visible ? visible.start : null,
      end: visible ? visible.end : null,
      days: visible ? visible.days : 0,
      today: null,
      months: visible ? months(visible) : [],
      lanes: [],
      drawn: 0,
      outside: [],
      unreliable,
      undated
    };
    if (!visible) {
      result.outside = placed.map((entry) => entry.record);
      return result;
    }
    if (dates.isIsoDate(options.todayIso) && options.todayIso >= visible.start && options.todayIso <= visible.end) {
      result.today = position(options.todayIso, visible, true);
    }
    const byVersion = new Map();
    for (const { record, item } of placed) {
      if (item.end < visible.start || firstDay(item) > visible.end) {
        result.outside.push(record);
        continue;
      }
      const version = record.application_version || "";
      if (!byVersion.has(version)) {
        byVersion.set(version, []);
      }
      byVersion.get(version).push(bar(record, item, visible));
    }
    result.lanes = [...byVersion.entries()]
      .sort((a, b) => versions.compareVersions(a[0], b[0]))
      .map(([version, bars]) => {
        bars.sort(
          (a, b) =>
            a.start.localeCompare(b.start) ||
            Number(a.record.release_number || 0) - Number(b.record.release_number || 0)
        );
        return { version, rows: pack(bars), bars };
      });
    result.drawn = result.lanes.reduce((sum, lane) => sum + lane.bars.length, 0);
    return result;
  }

  return { DEFAULT_ZOOM, ZOOMS, extent, layout, range, zoomOf };
});
