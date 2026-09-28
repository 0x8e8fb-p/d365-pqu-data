"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const rollout = require("../../src/d365_pqu/static/js/core/rollout.js");

function row(station, sandbox, production) {
  return {
    station,
    sandbox_start_date: sandbox ? sandbox[0] : null,
    sandbox_end_date: sandbox ? sandbox[1] : null,
    production_start_date: production ? production[0] : null,
    production_end_date: production ? production[1] : null
  };
}

// 10.0.48 PQU-6 station schedule (live snapshot).
const PQU6 = [
  row(1, ["2026-09-16", "2026-09-19"], null),
  row(2, ["2026-09-21", "2026-09-24"], ["2026-09-26", "2026-09-27"]),
  row(3, ["2026-09-21", "2026-09-24"], ["2026-09-26", "2026-09-27"]),
  row(4, ["2026-09-28", "2026-10-01"], ["2026-10-03", "2026-10-04"]),
  row(5, ["2026-10-05", "2026-10-08"], ["2026-10-10", "2026-10-11"]),
  row(6, ["2026-10-05", "2026-10-08"], ["2026-10-10", "2026-10-11"])
];

function close(actual, expected) {
  assert.ok(Math.abs(actual - expected) < 1e-9, `${actual} != ${expected}`);
}

test("axis spans the first to the last window day", () => {
  const chart = rollout.chart(PQU6, "2026-09-28");
  assert.equal(chart.start, "2026-09-16");
  assert.equal(chart.end, "2026-10-11");
  assert.equal(chart.days, 26);
  assert.deepEqual(chart.rows.map((item) => item.station), [1, 2, 3, 4, 5, 6]);
  assert.deepEqual(chart.ticks.map((tick) => tick.iso), ["2026-09-16", "2026-09-23", "2026-09-30", "2026-10-07"]);
});

test("bars are proportional and carry today's state", () => {
  const chart = rollout.chart(PQU6, "2026-09-28");
  const [sandbox1] = chart.rows[0].bars;
  assert.equal(chart.rows[0].bars.length, 1);
  close(sandbox1.left, 0);
  close(sandbox1.width, (4 / 26) * 100);
  assert.equal(sandbox1.state, "done");
  const [sandbox4, production4] = chart.rows[3].bars;
  close(sandbox4.left, (12 / 26) * 100);
  assert.equal(sandbox4.state, "current");
  assert.equal(production4.state, "upcoming");
  close(production4.left + production4.width, (19 / 26) * 100);
  const last = chart.rows[5].bars[1];
  close(last.left + last.width, 100);
  close(chart.today, (12.5 / 26) * 100);
});

test("today outside the axis and trains without windows", () => {
  assert.equal(rollout.chart(PQU6, "2026-12-01").today, null);
  assert.equal(rollout.chart(PQU6, "2026-12-01").rows[3].bars[1].state, "done");
  assert.equal(rollout.chart([row(1, null, null)], "2026-09-28"), null);
  assert.equal(rollout.chart([], "2026-09-28"), null);
  const single = rollout.chart([row(1, ["2026-09-16", "2026-09-16"], null)], "2026-09-16");
  assert.equal(single.days, 1);
  close(single.rows[0].bars[0].width, 100);
  close(single.today, 50);
});
