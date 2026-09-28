"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const dates = require("../../src/d365_pqu/static/js/core/dates.js");

test("formatDate renders calendar dates without shifting by zone", () => {
  assert.equal(dates.formatDate("2026-09-28"), "28 Sep 2026");
  assert.equal(dates.formatDate("2026-09-28", { weekday: true }), "Mon 28 Sep 2026");
  assert.equal(dates.formatDate("2026-09-30", { weekday: true, year: false }), "Wed 30 Sep");
  assert.equal(dates.formatDate("2027-01-01"), "1 Jan 2027");
  assert.equal(dates.formatDate(null), "—");
  assert.equal(dates.formatDate("not a date"), "not a date");
  assert.equal(dates.formatDate("2026-02-30"), "2026-02-30");
});

test("formatDate is identical regardless of the host time zone", () => {
  // The test runner executes this file under several TZ values; output must not change.
  const zone = process.env.TZ || "(default)";
  assert.equal(dates.formatDate("2026-10-01"), "1 Oct 2026", `host TZ ${zone}`);
  assert.equal(dates.formatDate("2026-03-29"), "29 Mar 2026", `host TZ ${zone}`);
});

test("formatDateRange collapses shared month and year", () => {
  assert.equal(dates.formatDateRange("2026-09-28", "2026-10-01"), "28 Sep – 1 Oct 2026");
  assert.equal(dates.formatDateRange("2026-10-03", "2026-10-04"), "3–4 Oct 2026");
  assert.equal(dates.formatDateRange("2026-12-28", "2027-01-03"), "28 Dec 2026 – 3 Jan 2027");
  assert.equal(dates.formatDateRange("2026-10-03", "2026-10-03"), "3 Oct 2026");
  assert.equal(dates.formatDateRange("2026-10-03", null), "3 Oct 2026");
  assert.equal(dates.formatDateRange(null, null), "—");
});

test("date arithmetic crosses months and years", () => {
  assert.equal(dates.addDays("2026-09-28", 7), "2026-10-05");
  assert.equal(dates.addDays("2026-12-31", 1), "2027-01-01");
  assert.equal(dates.diffDays("2026-08-21", "2026-09-28"), 38);
  assert.equal(dates.diffDays("2026-09-28", "2026-09-26"), -2);
  assert.equal(dates.diffDays("2026-03-28", "2026-03-30"), 2);
  assert.equal(dates.weekdayOf("2026-09-28"), 1);
  assert.equal(dates.diffDays("bad", "2026-01-01"), null);
});

test("todayIn uses the calendar date of the chosen zone", () => {
  const instant = Date.UTC(2026, 8, 28, 3, 0); // 28 Sep 03:00 UTC
  assert.equal(dates.todayIn("UTC", instant), "2026-09-28");
  assert.equal(dates.todayIn("Asia/Kolkata", instant), "2026-09-28");
  assert.equal(dates.todayIn("America/Los_Angeles", instant), "2026-09-27");
  assert.equal(dates.todayIn("Pacific/Kiritimati", Date.UTC(2026, 8, 27, 11, 0)), "2026-09-28");
});

test("formatDateTime shows the instant in the chosen zone", () => {
  const instant = "2026-09-25T05:02:58.124992Z";
  assert.equal(
    dates.formatDateTime(instant, "Asia/Kolkata", { seconds: true, locale: "en-IN" }),
    "25 Sep 2026 · 10:32:58 IST"
  );
  assert.equal(dates.formatDateTime(instant, "UTC"), "25 Sep 2026 · 05:02 UTC");
  assert.equal(
    dates.formatDateTime(Date.UTC(2026, 9, 2, 22, 0), "Asia/Kolkata", {
      weekday: true,
      year: false,
      separator: " ",
      locale: "en-IN"
    }),
    "Sat 3 Oct 03:30 IST"
  );
  assert.equal(dates.formatDateTime(null, "UTC"), "—");
});

test("utcInstant combines a calendar date with a UTC clock time", () => {
  assert.equal(dates.utcInstant("2026-10-02", "22:00"), Date.UTC(2026, 9, 2, 22, 0));
  assert.equal(dates.utcInstant("2026-10-02", "18:30"), Date.UTC(2026, 9, 2, 18, 30));
  assert.equal(dates.utcInstant("2026-10-02", "bad"), null);
});

test("relative wording for timestamps and day offsets", () => {
  const now = Date.UTC(2026, 8, 28, 12, 0);
  assert.equal(dates.relativeTime(now - 10 * 1000, now), "just now");
  assert.equal(dates.relativeTime(now - 12 * 60 * 1000, now), "12 min ago");
  assert.equal(dates.relativeTime(now - 5 * 3600 * 1000, now), "5 h ago");
  assert.equal(dates.relativeTime(now - 2 * 86400 * 1000, now), "2 days ago");
  assert.equal(dates.relativeTime(now + 3 * 3600 * 1000, now), "in 3 h");
  assert.equal(dates.daysPhrase(0), "today");
  assert.equal(dates.daysPhrase(1), "tomorrow");
  assert.equal(dates.daysPhrase(-1), "yesterday");
  assert.equal(dates.daysPhrase(4), "in 4 days");
  assert.equal(dates.daysPhrase(-38), "38 days ago");
});

test("zone helpers validate and label zones", () => {
  assert.equal(dates.isValidZone("Asia/Kolkata"), true);
  assert.equal(dates.isValidZone("Mars/Olympus"), false);
  assert.equal(dates.zoneLabel("UTC"), "UTC");
  assert.equal(dates.zoneLabel("Asia/Kolkata", Date.UTC(2026, 8, 28), "en-IN"), "IST");
  assert.ok(dates.supportedZones().includes("Europe/London"));
  assert.equal(dates.displayZone("Asia/Calcutta"), "Asia/Kolkata");
  assert.equal(dates.displayZone("Europe/Kiev"), "Europe/Kyiv");
  assert.equal(dates.displayZone("America/Los_Angeles"), "America/Los Angeles");
  assert.equal(dates.displayZone(null), "UTC");
});
