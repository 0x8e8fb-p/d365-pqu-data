"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const agenda = require("../../src/d365_pqu/static/js/core/agenda.js");

function event(id, kind, start, end, extra = {}) {
  const category = kind.endsWith("_window") && kind !== "train_window" ? "station" : kind === "change_cutoff" || kind === "train_window" ? "train" : "service_update";
  return { id, kind, category, start_date: start, end_date: end || start, station: null, ...extra };
}

const EVENTS = [
  event("sandbox_window:10.0.48-PQU-5:station-5", "sandbox_window", "2026-09-21", "2026-09-24", { station: 5 }),
  event("sandbox_window:10.0.48-PQU-6:station-4", "sandbox_window", "2026-09-28", "2026-10-01", { station: 4 }),
  event("sandbox_window:10.0.47-PQU-13:station-2", "sandbox_window", "2026-09-28", "2026-10-01", { station: 2 }),
  event("train_window:10.0.48-PQU-6", "train_window", "2026-09-16", "2026-10-10"),
  event("change_cutoff:10.0.48-PQU-7", "change_cutoff", "2026-09-30"),
  event("train_window:10.0.48-PQU-7", "train_window", "2026-09-30", "2026-10-24"),
  event("autoupdate_first:10.0.49", "autoupdate_first", "2026-10-02"),
  event("production_window:10.0.48-PQU-6:station-4", "production_window", "2026-10-03", "2026-10-04", { station: 4 }),
  event("production_window:10.0.47-PQU-13:station-2", "production_window", "2026-10-03", "2026-10-04", { station: 2 }),
  event("change_cutoff:10.0.47-PQU-14", "change_cutoff", "2026-10-07"),
  event("production_window:10.0.48-PQU-6:station-5", "production_window", "2026-10-10", "2026-10-11", { station: 5 }),
  event("change_cutoff:10.0.48-PQU-8", "change_cutoff", "2026-10-14")
];

test("upcoming covers fourteen days and windows already open", () => {
  const list = agenda.upcoming(EVENTS, "2026-09-28");
  assert.deepEqual(
    list.map((item) => [item.id, item.ongoing]),
    [
      ["sandbox_window:10.0.48-PQU-6:station-4", false],
      ["sandbox_window:10.0.47-PQU-13:station-2", false],
      ["train_window:10.0.48-PQU-6", true],
      ["change_cutoff:10.0.48-PQU-7", false],
      ["train_window:10.0.48-PQU-7", false],
      ["autoupdate_first:10.0.49", false],
      ["production_window:10.0.48-PQU-6:station-4", false],
      ["production_window:10.0.47-PQU-13:station-2", false],
      ["change_cutoff:10.0.47-PQU-14", false],
      ["production_window:10.0.48-PQU-6:station-5", false]
    ]
  );
  // 14 Oct is day 17 counting from 28 Sep, outside a fourteen-day agenda.
  assert.equal(list.some((item) => item.id === "change_cutoff:10.0.48-PQU-8"), false);
  assert.equal(agenda.upcoming(EVENTS, "2026-09-28", { days: 17 }).at(-1).id, "change_cutoff:10.0.48-PQU-8");
});

test("a station filter keeps that station's windows and every train or release date", () => {
  const list = agenda.upcoming(EVENTS, "2026-09-28", { station: 4 });
  assert.deepEqual(
    list.map((item) => item.id),
    [
      "sandbox_window:10.0.48-PQU-6:station-4",
      "train_window:10.0.48-PQU-6",
      "change_cutoff:10.0.48-PQU-7",
      "train_window:10.0.48-PQU-7",
      "autoupdate_first:10.0.49",
      "production_window:10.0.48-PQU-6:station-4",
      "change_cutoff:10.0.47-PQU-14"
    ]
  );
  const kinds = agenda.upcoming(EVENTS, "2026-09-28", { kinds: ["change_cutoff"] });
  assert.deepEqual(kinds.map((item) => item.id), ["change_cutoff:10.0.48-PQU-7", "change_cutoff:10.0.47-PQU-14"]);
});

test("byDay groups open windows under today and sorts days", () => {
  const groups = agenda.byDay(agenda.upcoming(EVENTS, "2026-09-29"), "2026-09-29");
  assert.deepEqual(
    groups.map((group) => [group.day, group.events.length]),
    [
      ["2026-09-29", 3],
      ["2026-09-30", 2],
      ["2026-10-02", 1],
      ["2026-10-03", 2],
      ["2026-10-07", 1],
      ["2026-10-10", 1]
    ]
  );
  assert.equal(groups[0].events.every((item) => item.ongoing), true);
});

test("ongoingKinds limits which open windows are included", () => {
  const list = agenda.upcoming(EVENTS, "2026-09-29", {
    ongoingKinds: ["sandbox_window", "production_window"]
  });
  const ongoing = list.filter((item) => item.ongoing).map((item) => item.id);
  assert.deepEqual(ongoing, [
    "sandbox_window:10.0.48-PQU-6:station-4",
    "sandbox_window:10.0.47-PQU-13:station-2"
  ]);
  assert.equal(list.some((item) => item.id === "train_window:10.0.48-PQU-6"), false);
});

test("nextOf and whenText", () => {
  assert.deepEqual(
    agenda.nextOf(EVENTS, "2026-09-28", ["change_cutoff"], 2).map((item) => item.id),
    ["change_cutoff:10.0.48-PQU-7", "change_cutoff:10.0.47-PQU-14"]
  );
  assert.equal(agenda.nextOf(EVENTS, "2026-10-15", ["change_cutoff"]).length, 0);
  const [cutoff] = agenda.nextOf(EVENTS, "2026-09-28", ["change_cutoff"], 1);
  assert.equal(agenda.whenText(cutoff, "2026-09-28"), "in 2 days");
  assert.equal(agenda.whenText({ ...cutoff, start_date: "2026-09-28" }, "2026-09-28"), "today");
  const open = { ...EVENTS[3], ongoing: true };
  assert.equal(agenda.whenText(open, "2026-09-28"), "until Sat 10 Oct");
  assert.equal(agenda.whenText({ ...open, end_date: "2026-09-28" }, "2026-09-28"), "ends today");
  assert.deepEqual(agenda.upcoming([], "2026-09-28"), []);
});
