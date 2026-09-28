"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const phase = require("../../src/d365_pqu/static/js/core/phase.js");

const PQU6 = {
  pqu_id: "10.0.48-PQU-6",
  status: "In-Progress",
  change_cutoff_date: "2026-09-16",
  train_start_date: "2026-09-16",
  train_end_date: "2026-10-10"
};

function station(number, sandbox, production) {
  return {
    station: number,
    sandbox_start_date: sandbox ? sandbox[0] : null,
    sandbox_end_date: sandbox ? sandbox[1] : null,
    production_start_date: production ? production[0] : null,
    production_end_date: production ? production[1] : null
  };
}

const PQU6_STATIONS = [
  station(1, ["2026-09-16", "2026-09-19"], null),
  station(2, ["2026-09-21", "2026-09-24"], ["2026-09-26", "2026-09-27"]),
  station(3, ["2026-09-21", "2026-09-24"], ["2026-09-26", "2026-09-27"]),
  station(4, ["2026-09-28", "2026-10-01"], ["2026-10-03", "2026-10-04"]),
  station(5, ["2026-10-05", "2026-10-08"], ["2026-10-10", "2026-10-11"]),
  station(6, ["2026-10-05", "2026-10-08"], ["2026-10-10", "2026-10-11"])
];

const PQU5 = {
  pqu_id: "10.0.48-PQU-5",
  status: "In-Progress",
  change_cutoff_date: "2026-09-02",
  train_start_date: "2026-09-02",
  train_end_date: "2026-09-26"
};
const PQU5_STATIONS = [
  station(1, ["2026-09-02", "2026-09-05"], null),
  station(2, ["2026-09-07", "2026-09-10"], ["2026-09-12", "2026-09-13"]),
  station(3, ["2026-09-07", "2026-09-10"], ["2026-09-12", "2026-09-13"]),
  station(4, ["2026-09-14", "2026-09-17"], ["2026-09-19", "2026-09-20"]),
  station(5, ["2026-09-21", "2026-09-24"], ["2026-09-26", "2026-09-27"]),
  station(6, ["2026-09-21", "2026-09-24"], ["2026-09-26", "2026-09-27"])
];

const OLD_STYLE = {
  pqu_id: "10.0.46-PQU-8",
  status: "Not Started",
  change_cutoff_date: "2026-08-21",
  train_start_date: "2026-08-31",
  train_end_date: "2026-10-03"
};

test("running train reports day number and the station window open today", () => {
  const result = phase.compute(PQU6, PQU6_STATIONS, "2026-09-28");
  assert.equal(result.kind, "running");
  assert.equal(result.text, "Day 13 of 25");
  assert.equal(result.detail, "Now: Station 4 sandbox (28 Sep – 1 Oct)");
  assert.equal(result.conflict, null);
});

test("running train groups stations that share a window", () => {
  const result = phase.compute(PQU6, PQU6_STATIONS, "2026-10-10");
  assert.equal(result.text, "Day 25 of 25");
  assert.equal(result.detail, "Now: Stations 5 and 6 production (10–11 Oct)");
});

test("distinct open windows are listed separately", () => {
  const stations = [
    station(5, ["2026-09-21", "2026-09-24"], null),
    station(6, ["2026-09-22", "2026-09-25"], null)
  ];
  const result = phase.compute(PQU6, stations, "2026-09-22");
  assert.equal(result.detail, "Now: Station 5 sandbox (21–24 Sep); Station 6 sandbox (22–25 Sep)");
});

test("between windows the next window is announced", () => {
  assert.equal(
    phase.compute(PQU6, PQU6_STATIONS, "2026-09-25").detail,
    "Next: Stations 2 and 3 production from 26 Sep (tomorrow)"
  );
  assert.equal(
    phase.compute(PQU6, PQU6_STATIONS, "2026-10-02").detail,
    "Next: Station 4 production from 3 Oct (tomorrow)"
  );
  const mixed = [
    station(2, null, ["2026-10-03", "2026-10-04"]),
    station(5, ["2026-10-03", "2026-10-06"], null)
  ];
  assert.equal(
    phase.compute(PQU6, mixed, "2026-09-28").detail,
    "Next: Station 5 sandbox and Station 2 production from 3 Oct (in 5 days)"
  );
});

test("running train without a detailed station schedule says so", () => {
  const result = phase.compute(PQU6, [], "2026-09-28");
  assert.equal(result.detail, "No detailed station schedule in the current article");
  const passed = phase.compute(PQU6, [station(1, ["2026-09-16", "2026-09-19"], null)], "2026-09-28");
  assert.equal(passed.detail, "All published station windows have passed");
});

test("ended In-Progress train is flagged when no window remains", () => {
  const result = phase.compute(PQU5, PQU5_STATIONS, "2026-09-28", { markdownDate: "2026-09-21" });
  assert.equal(result.kind, "ended");
  assert.equal(result.text, "Scheduled end passed 2 days ago");
  assert.equal(result.detail, null);
  assert.equal(
    result.conflict,
    "Microsoft still lists this train as In-Progress (article updated 21 Sep 2026)."
  );
});

test("production window after the train end keeps In-Progress consistent", () => {
  const result = phase.compute(PQU5, PQU5_STATIONS, "2026-09-27", { markdownDate: "2026-09-21" });
  assert.equal(result.text, "Scheduled end passed 1 day ago");
  assert.equal(result.detail, "Now: Stations 5 and 6 production (26–27 Sep)");
  assert.equal(result.conflict, null);
});

test("before the change cutoff and before the start", () => {
  assert.equal(phase.compute(OLD_STYLE, [], "2026-08-19").text, "Change cutoff in 2 days · Fri 21 Aug");
  assert.equal(phase.compute(OLD_STYLE, [], "2026-08-19").kind, "before-cutoff");
  assert.equal(phase.compute(OLD_STYLE, [], "2026-08-21").text, "Change cutoff today · starts in 10 days");
  assert.equal(phase.compute(OLD_STYLE, [], "2026-08-25").text, "Starts in 6 days · Mon 31 Aug");
  assert.equal(phase.compute(OLD_STYLE, [], "2026-08-30").text, "Starts tomorrow · Mon 31 Aug");
  const same = { ...PQU6, status: "Not Started", change_cutoff_date: "2026-09-30", train_start_date: "2026-09-30", train_end_date: "2026-10-24" };
  assert.equal(phase.compute(same, [], "2026-09-28").text, "Cutoff and start in 2 days · Wed 30 Sep");
  const noCutoff = { ...same, change_cutoff_date: null };
  assert.equal(phase.compute(noCutoff, [], "2026-09-28").text, "Starts in 2 days · Wed 30 Sep");
});

test("Not Started after its start date is flagged", () => {
  const result = phase.compute(OLD_STYLE, [], "2026-09-02", { markdownDate: "2026-08-28" });
  assert.equal(result.text, "Day 3 of 34");
  assert.equal(
    result.conflict,
    "Microsoft still lists this train as Not Started (article updated 28 Aug 2026)."
  );
  const ended = phase.compute(OLD_STYLE, [], "2026-10-05");
  assert.equal(ended.text, "Scheduled end passed 2 days ago");
  assert.equal(ended.conflict, "Microsoft still lists this train as Not Started.");
});

test("month and year rollover", () => {
  const record = { ...PQU6, train_start_date: "2026-12-23", train_end_date: "2027-01-16" };
  const result = phase.compute(record, [], "2027-01-01");
  assert.equal(result.text, "Day 10 of 25");
});

test("Completed, Canceled, and undated trains get no calculated line", () => {
  assert.deepEqual(
    [
      phase.compute({ ...PQU5, status: "Completed" }, PQU5_STATIONS, "2026-09-28"),
      phase.compute({ ...PQU5, status: "Completed" }, PQU5_STATIONS, "2026-09-20")
    ].map((result) => [result.kind, result.text, result.conflict]),
    [
      ["completed", null, null],
      ["completed", null, null]
    ]
  );
  const canceled = phase.compute({ ...PQU6, status: "Canceled" }, [], "2026-09-28");
  assert.equal(canceled.kind, "canceled");
  assert.equal(canceled.text, null);
  const undated = phase.compute({ ...PQU6, train_start_date: null }, [], "2026-09-28");
  assert.equal(undated.kind, "unknown");
  assert.equal(phase.compute(PQU6, [], "not-a-date").kind, "unknown");
});

test("searchText joins every calculated sentence", () => {
  const result = phase.compute(PQU5, PQU5_STATIONS, "2026-09-28", { markdownDate: "2026-09-21" });
  assert.match(phase.searchText(result), /Scheduled end passed 2 days ago Microsoft still lists/);
  assert.equal(phase.searchText(null), "");
});
