"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const timeline = require("../../src/d365_pqu/static/js/core/timeline.js");

function train(version, number, cutoff, start, end, status = "Not Started") {
  return {
    pqu_id: `${version}-PQU-${number}`,
    application_version: version,
    release_number: number,
    status,
    change_cutoff_date: cutoff,
    train_start_date: start,
    train_end_date: end
  };
}

function close(actual, expected) {
  assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} != ${expected}`);
}

// Dates from the live snapshot: 14-day cadence, 25-day trains; 10.0.46 cutoffs come earlier.
const TRAINS = [
  train("10.0.48", 5, "2026-09-02", "2026-09-02", "2026-09-26", "In-Progress"),
  train("10.0.48", 6, "2026-09-16", "2026-09-16", "2026-10-10", "In-Progress"),
  train("10.0.48", 7, "2026-09-30", "2026-09-30", "2026-10-24"),
  train("10.0.48", 8, "2026-10-14", "2026-10-14", "2026-11-07"),
  train("10.0.46", 7, "2026-07-22", "2026-07-27", "2026-08-29", "Completed"),
  train("10.0.46", 8, "2026-08-21", "2026-08-31", "2026-10-03", "In-Progress"),
  train("10.0.48", 1, "2026-07-08", "2026-07-08", "2026-08-01", "Completed")
];

test("fixed ranges keep today a third of the way in", () => {
  const three = timeline.range("3m", "2026-09-28", []);
  assert.deepEqual(three, { start: "2026-08-29", end: "2026-11-28", days: 92 });
  const six = timeline.range("6m", "2026-09-28", []);
  assert.deepEqual(six, { start: "2026-07-29", end: "2027-01-28", days: 184 });
  assert.equal(timeline.zoomOf("bogus").id, timeline.DEFAULT_ZOOM);
  assert.equal(timeline.range("3m", "not-a-date", []), null);
});

test("the full range spans the earliest cutoff to the latest end", () => {
  const result = timeline.layout(TRAINS, { zoom: "all", todayIso: "2026-09-28" });
  assert.equal(result.start, "2026-07-08");
  assert.equal(result.end, "2026-11-07");
  assert.equal(result.drawn, 7);
  assert.deepEqual(result.outside, []);
  assert.deepEqual(
    result.months.map((month) => [month.iso, month.label, month.year]),
    [
      ["2026-08-01", "Aug", "2026"],
      ["2026-09-01", "Sep", null],
      ["2026-10-01", "Oct", null],
      ["2026-11-01", "Nov", null]
    ]
  );
  // 6 months around 20 Dec starts on 20 Oct: the first line is 1 Nov; January shows its year.
  const across = timeline.layout(TRAINS, { zoom: "6m", todayIso: "2026-12-20" });
  assert.deepEqual(
    across.months.filter((month) => month.year).map((month) => [month.iso, month.year]),
    [
      ["2026-11-01", "2026"],
      ["2027-01-01", "2027"]
    ]
  );
  assert.equal(timeline.layout([], { zoom: "all", todayIso: "2026-09-28" }).start, null);
});

test("bars are proportional, clipped to the range, and packed into rows", () => {
  const result = timeline.layout(TRAINS, { zoom: "3m", todayIso: "2026-09-28" });
  assert.equal(result.start, "2026-08-29");
  assert.deepEqual(
    result.lanes.map((lane) => [lane.version, lane.rows, lane.bars.map((item) => item.pqu_id)]),
    [
      ["10.0.46", 2, ["10.0.46-PQU-7", "10.0.46-PQU-8"]],
      ["10.0.48", 2, ["10.0.48-PQU-5", "10.0.48-PQU-6", "10.0.48-PQU-7", "10.0.48-PQU-8"]]
    ]
  );
  assert.deepEqual(result.outside.map((record) => record.pqu_id), ["10.0.48-PQU-1"]);
  const [pqu5, pqu6, pqu7, pqu8] = result.lanes[1].bars;
  assert.deepEqual([pqu5.row, pqu6.row, pqu7.row, pqu8.row], [0, 1, 0, 1]);
  close(pqu6.left, (18 / 92) * 100);
  close(pqu6.width, (25 / 92) * 100);
  assert.equal(pqu6.clipStart, false);
  // 10.0.46 PQU-7 ends on the first visible day: clipped at the left edge.
  const [pqu467, pqu468] = result.lanes[0].bars;
  assert.equal(pqu467.clipStart, true);
  close(pqu467.left, 0);
  close(pqu467.width, (1 / 92) * 100);
  // 10.0.46 PQU-8 starts inside the range; its cutoff (21 Aug) is before it, so no tick.
  assert.equal(pqu468.clipStart, false);
  close(pqu468.left, (2 / 92) * 100);
  close(pqu468.width, (34 / 92) * 100);
  assert.equal(pqu468.cutoffLeft, null);
  close(pqu7.cutoffLeft, (32.5 / 92) * 100);
  assert.equal(pqu8.clipEnd, false);
  close(result.today, (30.5 / 92) * 100);
});

test("an early cutoff reserves its row space", () => {
  const list = [
    train("10.0.46", 1, "2026-01-05", "2026-01-05", "2026-01-20"),
    train("10.0.46", 2, "2026-01-18", "2026-01-23", "2026-02-10")
  ];
  const result = timeline.layout(list, { zoom: "all", todayIso: "2026-01-10" });
  assert.equal(result.lanes[0].rows, 2);
  const shifted = [list[0], { ...list[1], change_cutoff_date: "2026-01-21" }];
  assert.equal(timeline.layout(shifted, { zoom: "all", todayIso: "2026-01-10" }).lanes[0].rows, 1);
});

test("trains with missing or questioned dates are reported, not placed", () => {
  const list = [
    // 10.0.46 PQU-1 in the live snapshot: start 9 Feb 2025, cutoff 4 Feb 2026.
    train("10.0.46", 1, "2026-02-04", "2025-02-09", "2026-03-14", "Completed"),
    train("10.0.46", 2, "2026-03-04", "2026-03-09", "2026-04-11", "Completed"),
    train("10.0.49", 1, null, null, null),
    train("10.0.46", 3, "2026-13-40", "2026-04-06", "2026-03-01", "Completed")
  ];
  const unreliable = { "10.0.46-PQU-1": new Set(["change_cutoff_date", "train_start_date"]) };
  const result = timeline.layout(list, { zoom: "all", todayIso: "2026-09-28", unreliable });
  assert.deepEqual(
    result.unreliable.map((entry) => [entry.record.pqu_id, entry.fields]),
    [["10.0.46-PQU-1", ["train_start_date"]]]
  );
  assert.deepEqual(result.undated.map((record) => record.pqu_id), ["10.0.49-PQU-1"]);
  assert.equal(result.start, "2026-03-04");
  const [pqu2, pqu3] = result.lanes[0].bars;
  assert.equal(pqu2.pqu_id, "10.0.46-PQU-2");
  // An invalid cutoff has no tick; an end before the start draws a one-day bar.
  assert.equal(pqu3.cutoff, null);
  assert.equal(pqu3.end, "2026-04-06");
  assert.equal(result.today, null);
  const cutoffOnly = timeline.extent(list[1], new Set(["change_cutoff_date"]));
  assert.deepEqual(cutoffOnly, { start: "2026-03-09", end: "2026-04-11", cutoff: null });
});
