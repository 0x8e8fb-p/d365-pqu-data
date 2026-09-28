"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const builds = require("../../src/d365_pqu/static/js/core/builds.js");

function train(version, number, app, platform, status = "Completed") {
  return {
    pqu_id: `${version}-PQU-${number}`,
    application_version: version,
    release_number: number,
    status,
    application_build: app,
    platform_build: platform
  };
}

// A subset of the builds in the live snapshot (PQU-4 to PQU-7 omitted; 10.0.47 PQU-2 was
// canceled without a build).
const TRAINS = [
  train("10.0.47", 1, "10.0.2527.78", "7.0.7858.54"),
  train("10.0.47", 2, null, null, "Canceled"),
  train("10.0.47", 3, "10.0.2527.109", "7.0.7858.96"),
  train("10.0.47", 8, "10.0.2527.160", "7.0.7858.134"),
  train("10.0.47", 9, "10.0.2527.174", "7.0.7858.145"),
  train("10.0.47", 10, "10.0.2527.187", "7.0.7858.152"),
  train("10.0.47", 11, "10.0.2527.197", "7.0.7858.163"),
  train("10.0.47", 12, "10.0.2527.208", "7.0.7858.166", "In-Progress"),
  train("10.0.47", 13, "10.0.2527.215", "7.0.7858.174", "In-Progress"),
  train("10.0.47", 14, null, null, "Not Started"),
  train("10.0.48", 6, "10.0.2645.136", "7.0.7996.119", "In-Progress")
];

test("an exact application build names its train and counts newer builds", () => {
  const result = builds.locate(TRAINS, "10.0.2527.160");
  assert.equal(result.kind, "exact");
  assert.equal(result.field, "application_build");
  assert.equal(result.version, "10.0.47");
  assert.equal(result.match.pqu_id, "10.0.47-PQU-8");
  assert.equal(result.newerCount, 5);
  assert.equal(result.latest.pqu_id, "10.0.47-PQU-13");
  assert.equal(builds.locate(TRAINS, "10.0.2527.215").newerCount, 0);
});

test("a build between published builds names both neighbours", () => {
  const result = builds.locate(TRAINS, "10.0.2527.170");
  assert.equal(result.kind, "between");
  assert.equal(result.older.pqu_id, "10.0.47-PQU-8");
  assert.equal(result.newer.pqu_id, "10.0.47-PQU-9");
  assert.equal(result.newerCount, 5);
});

test("builds older than the first or newer than the latest", () => {
  const older = builds.locate(TRAINS, "10.0.2527.50");
  assert.equal(older.kind, "before");
  assert.equal(older.newer.pqu_id, "10.0.47-PQU-1");
  assert.equal(older.newerCount, 8);
  const newer = builds.locate(TRAINS, "10.0.2527.300");
  assert.equal(newer.kind, "after");
  assert.equal(newer.older.pqu_id, "10.0.47-PQU-13");
  assert.equal(newer.newerCount, 0);
});

test("platform builds, other versions, and numeric ordering", () => {
  const platform = builds.locate(TRAINS, "7.0.7858.134");
  assert.equal(platform.kind, "exact");
  assert.equal(platform.field, "platform_build");
  assert.equal(platform.match.pqu_id, "10.0.47-PQU-8");
  // Revision 99 is older than 109 numerically (a text comparison would say newer).
  const numeric = builds.locate(TRAINS, "10.0.2527.99");
  assert.equal(numeric.kind, "between");
  assert.equal(numeric.older.pqu_id, "10.0.47-PQU-1");
  assert.equal(numeric.newer.pqu_id, "10.0.47-PQU-3");
  const other = builds.locate(TRAINS, "10.0.2645.136");
  assert.equal(other.version, "10.0.48");
  assert.equal(other.match.pqu_id, "10.0.48-PQU-6");
});

test("unknown lines and invalid input", () => {
  assert.equal(builds.locate(TRAINS, "10.0.1999.5").kind, "unknown");
  assert.equal(builds.locate(TRAINS, "10.0.2527").kind, "invalid");
  assert.equal(builds.locate(TRAINS, "hello").kind, "invalid");
  assert.equal(builds.locate(TRAINS, "").kind, "invalid");
  assert.equal(builds.locate(TRAINS, "  v10.0.2527.160 ").kind, "exact");
  assert.equal(builds.lineOf("10.0.2527.160"), "10.0.2527");
});
