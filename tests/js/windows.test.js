"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const windows = require("../../src/d365_pqu/static/js/core/windows.js");

// Microsoft's planned maintenance windows (live snapshot).
const TABLE = [
  ["Australia", "13:00", ["Friday", "Saturday"]],
  ["Asia", "16:00", ["Friday", "Saturday"]],
  ["Brazil", "04:00", ["Saturday", "Sunday"]],
  ["Canada", "04:00", ["Saturday", "Sunday"]],
  ["China", "16:00", ["Friday", "Saturday"]],
  ["Europe", "22:00", ["Friday", "Saturday"]],
  ["France", "22:00", ["Friday", "Saturday"]],
  ["India", "18:30", ["Friday", "Saturday"]],
  ["Japan", "16:00", ["Friday", "Saturday"]],
  ["Norway", "22:00", ["Friday", "Saturday"]],
  ["South Africa", "22:00", ["Friday", "Saturday"]],
  ["Switzerland", "22:00", ["Friday", "Saturday"]],
  ["United Arab Emirates", "18:00", ["Friday", "Saturday"]],
  ["United Kingdom", "22:00", ["Friday", "Saturday"]],
  ["United States", "04:00", ["Saturday", "Sunday"]]
].map(([geo, start, days]) => ({
  geo,
  start_time_utc: start,
  days,
  duration_hours: 6,
  duration_text: "Six hours"
}));
const byGeo = Object.fromEntries(TABLE.map((row) => [row.geo, row]));
const EUROPE = byGeo.Europe;
const AUSTRALIA = byGeo.Australia;

test("occurrences follow the UTC weekdays and start time", () => {
  const list = windows.occurrences(EUROPE, "2026-10-02", "2026-10-04");
  assert.deepEqual(
    list.map((item) => [item.utcDate, item.weekday, new Date(item.start).toISOString()]),
    [
      ["2026-10-02", "Friday", "2026-10-02T22:00:00.000Z"],
      ["2026-10-03", "Saturday", "2026-10-03T22:00:00.000Z"]
    ]
  );
  assert.equal(list[0].end - list[0].start, 6 * 3600000);
  assert.deepEqual(windows.occurrences(EUROPE, "2026-10-04", "2026-10-02"), []);
  assert.deepEqual(windows.occurrences(null, "2026-10-02", "2026-10-04"), []);
  assert.deepEqual(windows.occurrences({ ...EUROPE, start_time_utc: "late" }, "2026-10-02", "2026-10-04"), []);
});

test("every geography pairs exactly two windows with a Saturday-Sunday production weekend", () => {
  for (const window of TABLE) {
    const pair = windows.forRange(window, "2026-10-03", "2026-10-04");
    assert.equal(pair.windows.length, 2, window.geo);
    assert.equal(pair.paired, true, window.geo);
  }
  const us = windows.forRange(byGeo["United States"], "2026-10-03", "2026-10-04");
  assert.deepEqual(
    us.windows.map((item) => new Date(item.start).toISOString()),
    ["2026-10-03T04:00:00.000Z", "2026-10-04T04:00:00.000Z"]
  );
});

test("ranges that do not isolate one or two windows fall back to the rule", () => {
  const week = windows.forRange(EUROPE, "2026-10-01", "2026-10-11");
  assert.equal(week.paired, false);
  assert.ok(week.windows.length > 2);
  const none = windows.forRange(EUROPE, "2026-10-06", "2026-10-07");
  assert.equal(none.paired, false);
  assert.equal(none.windows.length, 0);
  assert.equal(windows.forRange(EUROPE, null, null).paired, false);
  assert.equal(windows.ruleText(EUROPE), "Friday and Saturday · 22:00 UTC · Six hours");
});

test("describe converts each window to the chosen zone", () => {
  const [friday, saturday] = windows.forRange(EUROPE, "2026-10-03", "2026-10-04").windows;
  assert.equal(
    windows.describe(friday, "Asia/Kolkata", "en-IN").text,
    "Fri 2 Oct 22:00 UTC = Sat 3 Oct 03:30 IST · until 09:30 IST"
  );
  assert.equal(
    windows.describe(saturday, "Asia/Kolkata", "en-IN").text,
    "Sat 3 Oct 22:00 UTC = Sun 4 Oct 03:30 IST · until 09:30 IST"
  );
  const utc = windows.describe(friday, "UTC", "en-GB");
  assert.equal(utc.local, null);
  assert.equal(utc.text, "Fri 2 Oct 22:00 UTC · until Sat 3 Oct 04:00 UTC");
  const noLength = windows.occurrences({ ...EUROPE, duration_hours: null }, "2026-10-02", "2026-10-02")[0];
  assert.equal(noLength.end, null);
  assert.equal(windows.describe(noLength, "Asia/Kolkata", "en-IN").text, "Fri 2 Oct 22:00 UTC = Sat 3 Oct 03:30 IST");
});

test("Europe/London across the end of summer time (25 Oct 2026)", () => {
  const [friday, saturday] = windows.forRange(EUROPE, "2026-10-24", "2026-10-25").windows;
  assert.equal(
    windows.describe(friday, "Europe/London", "en-GB").text,
    "Fri 23 Oct 22:00 UTC = Fri 23 Oct 23:00 BST · until Sat 24 Oct 05:00 BST"
  );
  assert.equal(
    windows.describe(saturday, "Europe/London", "en-GB").text,
    "Sat 24 Oct 22:00 UTC = Sat 24 Oct 23:00 BST · until Sun 25 Oct 04:00 GMT"
  );
  const [next] = windows.forRange(EUROPE, "2026-10-31", "2026-11-01").windows;
  assert.equal(
    windows.describe(next, "Europe/London", "en-GB").text,
    "Fri 30 Oct 22:00 UTC = Fri 30 Oct 22:00 GMT · until Sat 31 Oct 04:00 GMT"
  );
});

test("Australia/Sydney across the start of daylight time (4 Oct 2026)", () => {
  const [friday, saturday] = windows.forRange(AUSTRALIA, "2026-10-03", "2026-10-04").windows;
  assert.equal(
    windows.describe(friday, "Australia/Sydney", "en-AU").text,
    "Fri 2 Oct 13:00 UTC = Fri 2 Oct 23:00 AEST · until Sat 3 Oct 05:00 AEST"
  );
  assert.equal(
    windows.describe(saturday, "Australia/Sydney", "en-AU").text,
    "Sat 3 Oct 13:00 UTC = Sat 3 Oct 23:00 AEST · until Sun 4 Oct 06:00 AEDT"
  );
  const [after] = windows.forRange(AUSTRALIA, "2026-10-10", "2026-10-11").windows;
  assert.equal(
    windows.describe(after, "Australia/Sydney", "en-AU").text,
    "Fri 9 Oct 13:00 UTC = Sat 10 Oct 00:00 AEDT · until 06:00 AEDT"
  );
});

test("occurrence state and the next windows from a moment", () => {
  const [friday] = windows.forRange(EUROPE, "2026-10-03", "2026-10-04").windows;
  assert.equal(windows.occurrenceState(friday, Date.UTC(2026, 9, 2, 21, 59)), "upcoming");
  assert.equal(windows.occurrenceState(friday, Date.UTC(2026, 9, 2, 22, 0)), "now");
  assert.equal(windows.occurrenceState(friday, Date.UTC(2026, 9, 3, 4, 0)), "done");
  assert.equal(windows.occurrenceState({ start: 10, end: null }, 20), "started");
  const next = windows.nextOccurrences(EUROPE, Date.UTC(2026, 9, 3, 1, 0), 2);
  assert.deepEqual(
    next.map((item) => new Date(item.start).toISOString()),
    ["2026-10-02T22:00:00.000Z", "2026-10-03T22:00:00.000Z"]
  );
  const later = windows.nextOccurrences(EUROPE, Date.UTC(2026, 8, 28, 4, 0), 1);
  assert.equal(new Date(later[0].start).toISOString(), "2026-10-02T22:00:00.000Z");
});

test("range state wording", () => {
  assert.deepEqual(windows.rangeState("2026-10-03", "2026-10-04", "2026-09-28"), {
    state: "upcoming",
    days: 5,
    text: "Starts in 5 days"
  });
  assert.equal(windows.rangeState("2026-09-29", "2026-10-02", "2026-09-28").text, "Starts tomorrow");
  assert.equal(
    windows.rangeState("2026-09-28", "2026-10-01", "2026-09-28").text,
    "In progress · day 1 of 4"
  );
  assert.equal(windows.rangeState("2026-09-28", "2026-09-28", "2026-09-28").text, "Today");
  assert.equal(windows.rangeState("2026-09-21", "2026-09-24", "2026-09-28").text, "Ended 4 days ago");
  assert.equal(windows.rangeState("2026-09-21", "2026-09-27", "2026-09-28").text, "Ended yesterday");
  assert.equal(windows.rangeState(null, null, "2026-09-28"), null);
});

test("station schedule splits current and past windows in date order", () => {
  const rows = [
    {
      pqu_id: "10.0.48-PQU-5",
      station: 4,
      sandbox_start_date: "2026-09-14",
      sandbox_end_date: "2026-09-17",
      production_start_date: "2026-09-19",
      production_end_date: "2026-09-20"
    },
    {
      pqu_id: "10.0.48-PQU-6",
      station: 4,
      sandbox_start_date: "2026-09-28",
      sandbox_end_date: "2026-10-01",
      production_start_date: "2026-10-03",
      production_end_date: "2026-10-04"
    },
    {
      pqu_id: "10.0.47-PQU-13",
      station: 4,
      sandbox_start_date: "2026-10-05",
      sandbox_end_date: "2026-10-08",
      production_start_date: "2026-10-10",
      production_end_date: "2026-10-11"
    },
    {
      pqu_id: "10.0.46-PQU-8",
      station: 4,
      sandbox_start_date: "2026-09-14",
      sandbox_end_date: "2026-09-17",
      production_start_date: "2026-09-26",
      production_end_date: "2026-09-27"
    }
  ];
  const plan = windows.stationSchedule(rows, "2026-09-28");
  assert.deepEqual(plan.active.map((item) => item.row.pqu_id), ["10.0.48-PQU-6", "10.0.47-PQU-13"]);
  assert.deepEqual(plan.past.map((item) => item.row.pqu_id), ["10.0.46-PQU-8", "10.0.48-PQU-5"]);
  assert.equal(plan.active[0].sandbox.state, "current");
  assert.equal(plan.active[0].production.text, "Starts in 5 days");
  const sandboxOnly = windows.stationSchedule(
    [{ pqu_id: "x", station: 1, sandbox_start_date: "2026-09-16", sandbox_end_date: "2026-09-19" }],
    "2026-09-28"
  );
  assert.equal(sandboxOnly.past[0].production, null);
});

test("rangeText gives one compact line per window in the chosen zone", () => {
  const [friday] = windows.forRange(EUROPE, "2026-10-03", "2026-10-04").windows;
  assert.equal(windows.rangeText(friday, "Asia/Kolkata", "en-IN"), "Sat 3 Oct 03:30 – 09:30 IST");
  assert.equal(windows.rangeText(friday, "UTC", "en-GB"), "Fri 2 Oct 22:00 UTC – Sat 3 Oct 04:00 UTC");
  assert.equal(windows.rangeText(friday, "America/Los_Angeles", "en-US"), "Fri 2 Oct 15:00 – 21:00 PDT");
  const [india] = windows.forRange(byGeo.India, "2026-10-03", "2026-10-04").windows;
  assert.equal(windows.rangeText(india, "Asia/Kolkata", "en-IN"), "Sat 3 Oct 00:00 – 06:00 IST");
  const [, saturday] = windows.forRange(EUROPE, "2026-10-24", "2026-10-25").windows;
  assert.equal(
    windows.rangeText(saturday, "Europe/London", "en-GB"),
    "Sat 24 Oct 23:00 BST – Sun 25 Oct 04:00 GMT"
  );
  const open = windows.occurrences({ ...EUROPE, duration_hours: null }, "2026-10-02", "2026-10-02")[0];
  assert.equal(windows.rangeText(open, "Asia/Kolkata", "en-IN"), "Sat 3 Oct 03:30 IST");
});

test("nextBoundary is the next start or end of a window", () => {
  const at = (iso) => Date.parse(iso);
  const iso = (ms) => new Date(ms).toISOString();
  // Monday: the next change is Friday's start.
  assert.equal(iso(windows.nextBoundary(EUROPE, at("2026-09-28T04:00:00Z"))), "2026-10-02T22:00:00.000Z");
  // During Friday's window, and exactly at its start, the next change is its end.
  assert.equal(iso(windows.nextBoundary(EUROPE, at("2026-10-02T23:00:00Z"))), "2026-10-03T04:00:00.000Z");
  assert.equal(iso(windows.nextBoundary(EUROPE, at("2026-10-02T22:00:00Z"))), "2026-10-03T04:00:00.000Z");
  // After Saturday's window ends, the next change is the following Friday.
  assert.equal(iso(windows.nextBoundary(EUROPE, at("2026-10-04T04:00:00Z"))), "2026-10-09T22:00:00.000Z");
  // India starts on the half hour; windows without a length only have starts.
  assert.equal(iso(windows.nextBoundary(byGeo.India, at("2026-10-02T18:00:00Z"))), "2026-10-02T18:30:00.000Z");
  const open = { ...EUROPE, duration_hours: null };
  assert.equal(iso(windows.nextBoundary(open, at("2026-10-02T23:00:00Z"))), "2026-10-03T22:00:00.000Z");
  assert.equal(windows.nextBoundary({ ...EUROPE, days: [] }, at("2026-10-02T23:00:00Z")), null);
  assert.equal(windows.nextBoundary(null, at("2026-10-02T23:00:00Z")), null);
});
