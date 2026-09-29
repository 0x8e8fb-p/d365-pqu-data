/* Pure date and time helpers. Date-only values (YYYY-MM-DD) are calendar dates and are never
 * converted between time zones; instants (ISO timestamps) are formatted in an explicit zone. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.dates = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const MONTHS_LONG = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December"
  ];
  const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
  const WEEKDAYS_LONG = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const DAY_MS = 86400000;
  const partFormatters = new Map();

  function pad2(value) {
    return String(value).padStart(2, "0");
  }

  function parseIsoDate(value) {
    if (value === null || value === undefined) {
      return null;
    }
    const match = ISO_DATE.exec(String(value).trim());
    if (!match) {
      return null;
    }
    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    const time = Date.UTC(year, month - 1, day);
    const check = new Date(time);
    if (
      check.getUTCFullYear() !== year ||
      check.getUTCMonth() !== month - 1 ||
      check.getUTCDate() !== day
    ) {
      return null;
    }
    return { year, month, day, time };
  }

  function isIsoDate(value) {
    return parseIsoDate(value) !== null;
  }

  function isoFromTime(time) {
    return new Date(time).toISOString().slice(0, 10);
  }

  function addDays(iso, days) {
    const parsed = parseIsoDate(iso);
    if (!parsed) {
      return null;
    }
    return isoFromTime(parsed.time + days * DAY_MS);
  }

  /* Whole days from `fromIso` to `toIso` (positive when `toIso` is later). */
  function diffDays(fromIso, toIso) {
    const from = parseIsoDate(fromIso);
    const to = parseIsoDate(toIso);
    if (!from || !to) {
      return null;
    }
    return Math.round((to.time - from.time) / DAY_MS);
  }

  function weekdayOf(iso) {
    const parsed = parseIsoDate(iso);
    return parsed ? new Date(parsed.time).getUTCDay() : null;
  }

  function weekdayName(index, long = false) {
    return (long ? WEEKDAYS_LONG : WEEKDAYS)[((index % 7) + 7) % 7];
  }

  function monthName(month, long = false) {
    return (long ? MONTHS_LONG : MONTHS)[month - 1];
  }

  function formatDate(iso, options = {}) {
    const parsed = parseIsoDate(iso);
    if (!parsed) {
      return iso === null || iso === undefined || iso === "" ? "—" : String(iso);
    }
    const parts = [];
    if (options.weekday) {
      parts.push((options.long ? WEEKDAYS_LONG : WEEKDAYS)[new Date(parsed.time).getUTCDay()]);
    }
    parts.push(String(parsed.day));
    parts.push((options.long ? MONTHS_LONG : MONTHS)[parsed.month - 1]);
    if (options.year !== false) {
      parts.push(String(parsed.year));
    }
    return parts.join(" ");
  }

  function formatDateRange(startIso, endIso, options = {}) {
    const start = parseIsoDate(startIso);
    const end = parseIsoDate(endIso);
    if (!start && !end) {
      return "—";
    }
    if (!start || !end) {
      return formatDate(start ? startIso : endIso, options);
    }
    if (start.time === end.time) {
      return formatDate(startIso, options);
    }
    const showYear = options.year !== false;
    if (!options.weekday && start.year === end.year && start.month === end.month) {
      return `${start.day}–${end.day} ${MONTHS[end.month - 1]}${showYear ? ` ${end.year}` : ""}`;
    }
    if (start.year === end.year) {
      return `${formatDate(startIso, { ...options, year: false })} – ${formatDate(endIso, options)}`;
    }
    return `${formatDate(startIso, { ...options, year: true })} – ${formatDate(endIso, {
      ...options,
      year: true
    })}`;
  }

  function isValidZone(zone) {
    if (!zone || typeof zone !== "string") {
      return false;
    }
    try {
      new Intl.DateTimeFormat("en-US", { timeZone: zone });
      return true;
    } catch (error) {
      return false;
    }
  }

  /* ICU keeps some pre-rename identifiers as canonical; show the current IANA names instead. */
  const LEGACY_ZONE_NAMES = {
    "Africa/Asmera": "Africa/Asmara",
    "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
    "America/Catamarca": "America/Argentina/Catamarca",
    "America/Coral_Harbour": "America/Atikokan",
    "America/Cordoba": "America/Argentina/Cordoba",
    "America/Godthab": "America/Nuuk",
    "America/Indianapolis": "America/Indiana/Indianapolis",
    "America/Jujuy": "America/Argentina/Jujuy",
    "America/Louisville": "America/Kentucky/Louisville",
    "America/Mendoza": "America/Argentina/Mendoza",
    "Asia/Calcutta": "Asia/Kolkata",
    "Asia/Katmandu": "Asia/Kathmandu",
    "Asia/Rangoon": "Asia/Yangon",
    "Asia/Saigon": "Asia/Ho_Chi_Minh",
    "Atlantic/Faeroe": "Atlantic/Faroe",
    "Europe/Kiev": "Europe/Kyiv",
    "Pacific/Enderbury": "Pacific/Kanton",
    "Pacific/Ponape": "Pacific/Pohnpei",
    "Pacific/Truk": "Pacific/Chuuk"
  };

  function displayZone(zone) {
    const name = LEGACY_ZONE_NAMES[zone] || zone || "UTC";
    return name.replace(/_/g, " ");
  }

  function detectZone() {
    try {
      const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      return isValidZone(zone) ? zone : "UTC";
    } catch (error) {
      return "UTC";
    }
  }

  function supportedZones() {
    try {
      if (typeof Intl.supportedValuesOf === "function") {
        return Intl.supportedValuesOf("timeZone").slice();
      }
    } catch (error) {
      /* Older engines: only Auto and UTC are offered. */
    }
    return [];
  }

  function partsFormatter(zone) {
    let formatter = partFormatters.get(zone);
    if (!formatter) {
      formatter = new Intl.DateTimeFormat("en-US", {
        timeZone: zone,
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23"
      });
      partFormatters.set(zone, formatter);
    }
    return formatter;
  }

  function toDate(value) {
    if (value instanceof Date) {
      return value;
    }
    if (value === null || value === undefined || value === "") {
      return null;
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  /* Calendar fields of an instant as observed in `zone`. */
  function zonedParts(value, zone) {
    const date = toDate(value);
    if (!date) {
      return null;
    }
    const values = {};
    for (const part of partsFormatter(zone).formatToParts(date)) {
      values[part.type] = part.value;
    }
    const hour = values.hour === "24" ? 0 : Number(values.hour);
    const iso = `${values.year}-${values.month}-${values.day}`;
    return {
      year: Number(values.year),
      month: Number(values.month),
      day: Number(values.day),
      hour,
      minute: Number(values.minute),
      second: Number(values.second),
      iso,
      weekday: weekdayOf(iso)
    };
  }

  function todayIn(zone, now = Date.now()) {
    const parts = zonedParts(new Date(now), zone);
    return parts ? parts.iso : isoFromTime(now);
  }

  function zoneLabel(zone, value = Date.now(), locale) {
    if (!zone || zone === "UTC" || zone === "Etc/UTC") {
      return "UTC";
    }
    try {
      const parts = new Intl.DateTimeFormat(locale, {
        timeZone: zone,
        timeZoneName: "short"
      }).formatToParts(toDate(value) || new Date());
      const name = parts.find((part) => part.type === "timeZoneName");
      return name ? name.value : zone;
    } catch (error) {
      return zone;
    }
  }

  function formatTime(value, zone) {
    const parts = zonedParts(value, zone);
    return parts ? `${pad2(parts.hour)}:${pad2(parts.minute)}` : "—";
  }

  /* "25 Sep 2026 · 10:32 IST" (separator and parts configurable). */
  function formatDateTime(value, zone, options = {}) {
    const date = toDate(value);
    if (!date) {
      return "—";
    }
    const parts = zonedParts(date, zone);
    const dateText = formatDate(parts.iso, { weekday: options.weekday, year: options.year });
    const seconds = options.seconds ? `:${pad2(parts.second)}` : "";
    const time = `${pad2(parts.hour)}:${pad2(parts.minute)}${seconds}`;
    const label = options.zoneName === false ? "" : ` ${zoneLabel(zone, date, options.locale)}`;
    const separator = options.separator === undefined ? " · " : options.separator;
    return `${dateText}${separator}${time}${label}`;
  }

  /* UTC instant (milliseconds) for a calendar date and an "HH:MM" UTC time. */
  function utcInstant(iso, time) {
    const parsed = parseIsoDate(iso);
    const match = /^(\d{1,2}):(\d{2})$/.exec(String(time || "").trim());
    if (!parsed || !match) {
      return null;
    }
    return parsed.time + (Number(match[1]) * 60 + Number(match[2])) * 60000;
  }

  function relativeTime(value, now = Date.now()) {
    const date = toDate(value);
    if (!date) {
      return "—";
    }
    const seconds = Math.round((now - date.getTime()) / 1000);
    const future = seconds < 0;
    const abs = Math.abs(seconds);
    if (abs < 45) {
      return "just now";
    }
    let text;
    if (abs < 3600) {
      text = `${Math.max(1, Math.round(abs / 60))} min`;
    } else if (abs < 86400) {
      text = `${Math.round(abs / 3600)} h`;
    } else {
      const days = Math.round(abs / 86400);
      text = `${days} ${days === 1 ? "day" : "days"}`;
    }
    return future ? `in ${text}` : `${text} ago`;
  }

  function daysPhrase(days) {
    if (days === null || days === undefined || Number.isNaN(days)) {
      return "";
    }
    if (days === 0) {
      return "today";
    }
    if (days === 1) {
      return "tomorrow";
    }
    if (days === -1) {
      return "yesterday";
    }
    return days > 0 ? `in ${days} days` : `${-days} days ago`;
  }

  return {
    DAY_MS,
    addDays,
    daysPhrase,
    detectZone,
    diffDays,
    displayZone,
    formatDate,
    formatDateRange,
    formatDateTime,
    formatTime,
    isIsoDate,
    isValidZone,
    isoFromTime,
    monthName,
    pad2,
    parseIsoDate,
    relativeTime,
    supportedZones,
    toDate,
    todayIn,
    utcInstant,
    weekdayName,
    weekdayOf,
    zoneLabel,
    zonedParts
  };
});
