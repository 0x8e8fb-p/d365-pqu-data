/* Agenda of key dates around a calendar day, from the published events. */
(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.agenda = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  function load(name, file) {
    return typeof module === "object" && module.exports ? require(file) : root.PQU[name];
  }
  const dates = load("dates", "./dates.js");

  const DEFAULT_DAYS = 14;

  function inStation(event, station) {
    return station === null || station === undefined || event.category !== "station" || event.station === station;
  }

  /*
   * Events that begin within [today, today + days - 1], plus multi-day windows that are already
   * open today. `station` (optional) keeps only that station's windows; train and service update
   * dates always apply. `ongoingKinds` (optional) limits which open windows are included.
   */
  function upcoming(events, todayIso, options = {}) {
    const days = options.days || DEFAULT_DAYS;
    const lastIso = dates.addDays(todayIso, days - 1);
    const kinds = options.kinds ? new Set(options.kinds) : null;
    const ongoingKinds = options.ongoingKinds ? new Set(options.ongoingKinds) : null;
    const result = [];
    for (const event of events || []) {
      if (kinds && !kinds.has(event.kind)) {
        continue;
      }
      if (!inStation(event, options.station)) {
        continue;
      }
      const end = event.end_date || event.start_date;
      const startsInRange = event.start_date >= todayIso && event.start_date <= lastIso;
      const openToday =
        event.start_date < todayIso &&
        end >= todayIso &&
        event.start_date !== end &&
        (!ongoingKinds || ongoingKinds.has(event.kind));
      if (startsInRange || openToday) {
        result.push({ ...event, ongoing: openToday });
      }
    }
    return result;
  }

  /* Group agenda events by calendar day; windows open today are grouped under today. */
  function byDay(events, todayIso) {
    const groups = new Map();
    for (const event of events) {
      const day = event.ongoing ? todayIso : event.start_date;
      if (!groups.has(day)) {
        groups.set(day, []);
      }
      groups.get(day).push(event);
    }
    return [...groups.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([day, list]) => ({ day, events: list }));
  }

  /* The next events of the given kinds on or after today, earliest date first. */
  function nextOf(events, todayIso, kinds, count = 3) {
    const wanted = new Set(kinds);
    const found = (events || []).filter((event) => wanted.has(event.kind) && event.start_date >= todayIso);
    return found.slice(0, count);
  }

  /* Phrase for when an event happens relative to today. */
  function whenText(event, todayIso) {
    if (event.ongoing) {
      const left = dates.diffDays(todayIso, event.end_date);
      return left === 0 ? "ends today" : `until ${dates.formatDate(event.end_date, { weekday: true, year: false })}`;
    }
    return dates.daysPhrase(dates.diffDays(todayIso, event.start_date));
  }

  return { DEFAULT_DAYS, byDay, nextOf, upcoming, whenText };
});
