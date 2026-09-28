/* Station windows and dark-hours maintenance windows for a calendar day and time zone.
 *
 * Microsoft publishes production windows as calendar dates per station and, separately, the
 * dark-hours window of each geography as UTC weekdays and a UTC start time. Pairing the two is
 * a calculation made here; Microsoft does not publish which window a given update uses. */
(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.windows = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  function load(name, file) {
    return typeof module === "object" && module.exports ? require(file) : root.PQU[name];
  }
  const dates = load("dates", "./dates.js");
  const text = load("text", "./text.js");

  const HOUR_MS = 3600000;
  const MAX_SPAN_DAYS = 400;

  function durationMs(window) {
    const hours = window && window.duration_hours;
    return typeof hours === "number" && hours > 0 ? hours * HOUR_MS : null;
  }

  /* Every start of `window` on its UTC weekdays between two calendar dates (inclusive). */
  function occurrences(window, fromIso, toIso) {
    if (!window || !dates.isIsoDate(fromIso) || !dates.isIsoDate(toIso) || fromIso > toIso) {
      return [];
    }
    const days = new Set(window.days || []);
    const length = durationMs(window);
    const result = [];
    let iso = fromIso;
    for (let step = 0; iso <= toIso && step <= MAX_SPAN_DAYS; step += 1) {
      const weekday = dates.weekdayName(dates.weekdayOf(iso), true);
      if (days.has(weekday)) {
        const start = dates.utcInstant(iso, window.start_time_utc);
        if (start !== null) {
          result.push({
            geo: window.geo,
            utcDate: iso,
            weekday,
            start,
            end: length === null ? null : start + length
          });
        }
      }
      iso = dates.addDays(iso, 1);
    }
    return result;
  }

  /*
   * Dark-hours windows around a published production range. Windows starting on the UTC day
   * before the first date are included because they already fall on the first date in zones
   * east of UTC. `paired` is false when the range does not isolate one or two windows (then the
   * weekly rule is shown instead of specific times).
   */
  function forRange(window, startIso, endIso) {
    if (!window || !dates.isIsoDate(startIso)) {
      return { windows: [], paired: false };
    }
    const end = dates.isIsoDate(endIso) ? endIso : startIso;
    const list = occurrences(window, dates.addDays(startIso, -1), end);
    return { windows: list, paired: list.length >= 1 && list.length <= 2 };
  }

  /* The next `count` windows that have not ended by `nowMs` (a window in progress counts). */
  function nextOccurrences(window, nowMs, count = 2) {
    if (!window) {
      return [];
    }
    const today = dates.isoFromTime(nowMs);
    return occurrences(window, dates.addDays(today, -1), dates.addDays(today, 14))
      .filter((item) => (item.end === null ? item.start : item.end) > nowMs)
      .slice(0, count);
  }

  function occurrenceState(occurrence, nowMs) {
    if (occurrence.end !== null && nowMs >= occurrence.end) {
      return "done";
    }
    if (nowMs >= occurrence.start) {
      return occurrence.end === null ? "started" : "now";
    }
    return "upcoming";
  }

  /* The next instant after `nowMs` at which a window of `window` starts or ends, or null.
   * Views that show whether a window is running use it to know when to redraw. */
  function nextBoundary(window, nowMs) {
    if (!window) {
      return null;
    }
    const today = dates.isoFromTime(nowMs);
    let next = null;
    for (const item of occurrences(window, dates.addDays(today, -1), dates.addDays(today, 8))) {
      for (const instant of [item.start, item.end]) {
        if (instant !== null && instant > nowMs && (next === null || instant < next)) {
          next = instant;
        }
      }
    }
    return next;
  }

  function isUtcZone(zone) {
    return !zone || zone === "UTC" || zone === "Etc/UTC" || zone === "Etc/GMT";
  }

  function stamp(ms, zone, locale) {
    return dates.formatDateTime(ms, zone, { weekday: true, year: false, separator: " ", locale });
  }

  /* "Fri 2 Oct 22:00 UTC = Sat 3 Oct 03:30 IST · until 09:30 IST" */
  function describe(occurrence, zone, locale) {
    const utc = stamp(occurrence.start, "UTC", locale);
    const local = isUtcZone(zone) ? null : stamp(occurrence.start, zone, locale);
    const shownZone = isUtcZone(zone) ? "UTC" : zone;
    let until = null;
    if (occurrence.end !== null) {
      const sameDay =
        dates.zonedParts(occurrence.start, shownZone).iso ===
        dates.zonedParts(occurrence.end, shownZone).iso;
      until = sameDay
        ? `${dates.formatTime(occurrence.end, shownZone)} ${dates.zoneLabel(shownZone, occurrence.end, locale)}`
        : stamp(occurrence.end, shownZone, locale);
    }
    const head = local ? `${utc} = ${local}` : utc;
    return { utc, local, until, text: until ? `${head} · until ${until}` : head };
  }

  /* Microsoft's weekly rule as published: "Friday and Saturday · 22:00 UTC · Six hours". */
  function ruleText(window) {
    if (!window) {
      return "";
    }
    const parts = [text.joinList(window.days || []), `${window.start_time_utc} UTC`];
    if (window.duration_text) {
      parts.push(window.duration_text);
    }
    return parts.filter(Boolean).join(" · ");
  }

  /* One window in one zone: "Sat 3 Oct 03:30 – 09:30 IST" (dates and zone names only repeat
   * when the window crosses midnight or a daylight-saving change). */
  function rangeText(occurrence, zone, locale) {
    const shown = isUtcZone(zone) ? "UTC" : zone;
    const startParts = dates.zonedParts(occurrence.start, shown);
    const startDay = dates.formatDate(startParts.iso, { weekday: true, year: false });
    const startTime = dates.formatTime(occurrence.start, shown);
    const startLabel = dates.zoneLabel(shown, occurrence.start, locale);
    if (occurrence.end === null) {
      return `${startDay} ${startTime} ${startLabel}`;
    }
    const endParts = dates.zonedParts(occurrence.end, shown);
    const endTime = dates.formatTime(occurrence.end, shown);
    const endLabel = dates.zoneLabel(shown, occurrence.end, locale);
    const sameDay = endParts.iso === startParts.iso;
    if (sameDay && startLabel === endLabel) {
      return `${startDay} ${startTime} – ${endTime} ${endLabel}`;
    }
    const endDay = sameDay ? "" : `${dates.formatDate(endParts.iso, { weekday: true, year: false })} `;
    return `${startDay} ${startTime} ${startLabel} – ${endDay}${endTime} ${endLabel}`;
  }

  /* Where today falls relative to a published date range. */
  function rangeState(startIso, endIso, todayIso) {
    if (!dates.isIsoDate(startIso) || !dates.isIsoDate(todayIso)) {
      return null;
    }
    const end = dates.isIsoDate(endIso) && endIso >= startIso ? endIso : startIso;
    if (todayIso < startIso) {
      const days = dates.diffDays(todayIso, startIso);
      return { state: "upcoming", days, text: `Starts ${dates.daysPhrase(days)}` };
    }
    if (todayIso <= end) {
      const day = dates.diffDays(startIso, todayIso) + 1;
      const length = dates.diffDays(startIso, end) + 1;
      return {
        state: "current",
        day,
        length,
        text: length === 1 ? "Today" : `In progress · day ${day} of ${length}`
      };
    }
    const days = dates.diffDays(end, todayIso);
    return { state: "done", days, text: `Ended ${dates.daysPhrase(-days)}` };
  }

  /* One entry per published station row, split into current/upcoming and past. */
  function stationSchedule(rows, todayIso) {
    const active = [];
    const past = [];
    for (const row of rows || []) {
      const sandbox = rangeState(row.sandbox_start_date, row.sandbox_end_date, todayIso);
      const production = rangeState(row.production_start_date, row.production_end_date, todayIso);
      const parts = [sandbox, production].filter(Boolean);
      if (!parts.length) {
        continue;
      }
      const open = [
        sandbox && sandbox.state !== "done" ? row.sandbox_start_date : null,
        production && production.state !== "done" ? row.production_start_date : null
      ].filter(Boolean);
      const lastEnd = [row.production_end_date, row.sandbox_end_date]
        .filter((value) => dates.isIsoDate(value))
        .sort()
        .pop();
      const item = { row, sandbox, production, sortDate: open.length ? open.sort()[0] : lastEnd };
      (open.length ? active : past).push(item);
    }
    active.sort(
      (a, b) => a.sortDate.localeCompare(b.sortDate) || a.row.pqu_id.localeCompare(b.row.pqu_id)
    );
    past.sort(
      (a, b) => b.sortDate.localeCompare(a.sortDate) || a.row.pqu_id.localeCompare(b.row.pqu_id)
    );
    return { active, past };
  }

  return {
    describe,
    forRange,
    nextBoundary,
    nextOccurrences,
    occurrenceState,
    occurrences,
    rangeState,
    rangeText,
    ruleText,
    stationSchedule
  };
});
