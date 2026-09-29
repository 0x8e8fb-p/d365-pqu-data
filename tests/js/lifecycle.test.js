"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const lifecycle = require("../../src/d365_pqu/static/js/core/lifecycle.js");

// Microsoft's targeted release schedule (live snapshot values).
const V46 = {
  version: "10.0.46",
  release_label: "CY26Q1",
  is_major: false,
  preview_date: "2025-10-24",
  preview_latest_update_date: "2025-11-17",
  general_availability_date: "2025-12-26",
  first_autoupdate_date: "2026-02-01",
  second_autoupdate_date: "2026-03-01",
  end_of_service_date: "2026-08-21"
};
const V47 = {
  ...V46,
  version: "10.0.47",
  preview_date: "2026-01-26",
  preview_latest_update_date: "2026-02-16",
  general_availability_date: "2026-03-13",
  first_autoupdate_date: "2026-04-03",
  second_autoupdate_date: "2026-05-01",
  end_of_service_date: "2026-11-20"
};
const V49 = {
  ...V46,
  version: "10.0.49",
  is_major: true,
  preview_date: "2026-07-27",
  preview_latest_update_date: "2026-08-17",
  general_availability_date: "2026-09-11",
  first_autoupdate_date: "2026-10-02",
  second_autoupdate_date: "2026-11-01",
  end_of_service_date: "2027-05-21"
};
const V50 = {
  ...V46,
  version: "10.0.50",
  preview_date: "2026-10-23",
  preview_latest_update_date: "2026-11-17",
  general_availability_date: "2026-12-22",
  first_autoupdate_date: "2027-01-31",
  second_autoupdate_date: "2027-02-28",
  end_of_service_date: "2027-08-20"
};
const TODAY = "2026-09-28";

test("end of service is reported with the days since", () => {
  const result = lifecycle.assess(V46, TODAY);
  assert.equal(result.state, "end-of-service");
  assert.equal(result.label, "End of service");
  assert.equal(result.summary, "End of service · 38 days ago");
  assert.equal(result.serviced, false);
  assert.equal(result.next, null);
  assert.equal(lifecycle.assess(V46, "2026-08-21").summary, "End of service · today");
});

test("serviced phases report the next milestone", () => {
  const v47 = lifecycle.assess(V47, TODAY);
  assert.equal(v47.state, "supported");
  assert.equal(v47.summary, "End of service in 53 days · Fri 20 Nov");
  assert.equal(v47.serviced, true);
  const v49 = lifecycle.assess(V49, TODAY);
  assert.equal(v49.state, "available");
  assert.equal(v49.label, "Generally available");
  assert.equal(v49.summary, "First autoupdate in 4 days · Fri 2 Oct");
  assert.equal(v49.daysToNext, 4);
  const autoupdate = lifecycle.assess(V49, "2026-10-02");
  assert.equal(autoupdate.state, "autoupdate");
  assert.equal(autoupdate.summary, "Second autoupdate in 30 days · Sun 1 Nov");
});

test("upcoming and preview phases", () => {
  const v50 = lifecycle.assess(V50, TODAY);
  assert.equal(v50.state, "upcoming");
  assert.equal(v50.summary, "Preview in 25 days · Fri 23 Oct");
  const preview = lifecycle.assess(V50, "2026-11-01");
  assert.equal(preview.state, "preview");
  assert.equal(preview.summary, "Latest preview update in 16 days · Tue 17 Nov");
  assert.equal(lifecycle.assess(V50, "2026-12-21").summary, "General availability tomorrow · Tue 22 Dec");
  assert.equal(
    lifecycle.assess(V50, "2026-12-22").summary,
    "First autoupdate in 40 days · Sun 31 Jan 2027"
  );
});

test("missing dates are skipped and no dates means unknown", () => {
  const partial = { version: "10.0.52", general_availability_date: "2027-05-01" };
  assert.equal(lifecycle.assess(partial, TODAY).state, "upcoming");
  assert.equal(lifecycle.assess(partial, TODAY).summary, "General availability in 215 days · Sat 1 May 2027");
  assert.equal(lifecycle.assess(partial, "2027-06-01").state, "available");
  assert.equal(lifecycle.assess(partial, "2027-06-01").summary, "Generally available");
  const empty = lifecycle.assess({ version: "10.0.99" }, TODAY);
  assert.equal(empty.state, "unknown");
  assert.equal(empty.summary, "Dates not published");
});

test("chart puts every version on one axis with today's position", () => {
  const geometry = lifecycle.chart([V50, V49, V47, V46], TODAY);
  assert.equal(geometry.start, "2025-10-24");
  assert.equal(geometry.end, "2027-08-20");
  assert.deepEqual(
    geometry.rows.map((row) => [row.version, row.state]),
    [
      ["10.0.50", "upcoming"],
      ["10.0.49", "available"],
      ["10.0.47", "supported"],
      ["10.0.46", "end-of-service"]
    ]
  );
  const v46 = geometry.rows[3];
  assert.deepEqual(
    v46.segments.map((segment) => [segment.kind, segment.start, segment.end]),
    [
      ["preview", "2025-10-24", "2025-12-26"],
      ["service", "2025-12-26", "2026-08-21"]
    ]
  );
  assert.equal(v46.segments[0].left, 0);
  const v50 = geometry.rows[0].segments[1];
  assert.ok(Math.abs(v50.left + v50.width - 100) < 1e-9);
  assert.deepEqual(
    geometry.rows[1].marks.map((mark) => mark.date),
    ["2026-10-02", "2026-11-01"]
  );
  // 28 Sep 2026 is 339 of the axis's 665 days.
  assert.ok(Math.abs(geometry.today - (339 / 665) * 100) < 1e-9);
  assert.deepEqual(
    geometry.ticks.map((tick) => tick.label),
    ["Jan 2026", "Apr", "Jul", "Oct", "Jan 2027", "Apr", "Jul"]
  );
  assert.equal(geometry.ticks[0].iso, "2026-01-01");
});

test("chart handles missing dates and ranges without today", () => {
  const partial = { version: "10.0.52", general_availability_date: "2027-05-01" };
  const geometry = lifecycle.chart([V46, partial], "2030-01-01");
  assert.equal(geometry.today, null);
  assert.deepEqual(geometry.rows[1].segments, []);
  assert.deepEqual(geometry.rows[1].marks, []);
  assert.equal(lifecycle.chart([partial], TODAY), null);
  assert.equal(lifecycle.chart([{ version: "10.0.99" }], TODAY), null);
  assert.equal(lifecycle.chart([], TODAY), null);
  const quarterStart = lifecycle.chart([{ version: "x", preview_date: "2026-04-01", end_of_service_date: "2026-10-01" }], TODAY);
  assert.deepEqual(
    quarterStart.ticks.map((tick) => tick.iso),
    ["2026-04-01", "2026-07-01", "2026-10-01"]
  );
});

test("mergeVersions combines lifecycle rows and trains, newest first", () => {
  const trains = [
    { pqu_id: "10.0.47-PQU-8", application_version: "10.0.47", status: "Completed", application_build: "10.0.2527.160" },
    { pqu_id: "10.0.47-PQU-13", application_version: "10.0.47", status: "In-Progress", application_build: "10.0.2527.215" },
    { pqu_id: "10.0.47-PQU-14", application_version: "10.0.47", status: "Not Started", application_build: null },
    { pqu_id: "10.0.9-PQU-1", application_version: "10.0.9", status: "Completed", application_build: "10.0.9.1" }
  ];
  const merged = lifecycle.mergeVersions([V46, V47, V49], trains);
  assert.deepEqual(
    merged.map((entry) => [entry.version, entry.lifecycle ? "dates" : "none", entry.trains.length]),
    [
      ["10.0.49", "dates", 0],
      ["10.0.47", "dates", 3],
      ["10.0.46", "dates", 0],
      ["10.0.9", "none", 1]
    ]
  );
  const summary = lifecycle.trainSummary(merged[1].trains);
  assert.equal(summary.total, 3);
  assert.deepEqual(summary.counts, { Completed: 1, "In-Progress": 1, "Not Started": 1 });
  assert.equal(summary.latest.pqu_id, "10.0.47-PQU-13");
  assert.equal(lifecycle.trainSummary([]).latest, null);
});
