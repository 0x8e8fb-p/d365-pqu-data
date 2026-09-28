"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const health = require("../../src/d365_pqu/static/js/core/health.js");
const router = require("../../src/d365_pqu/static/js/core/router.js");

const NOW = Date.UTC(2026, 8, 28, 4, 0);
const HOUR = 3600 * 1000;

function doc(overrides = {}) {
  return {
    health: {
      status: "healthy",
      checked_at: new Date(NOW - HOUR).toISOString(),
      check_interval_minutes: 360,
      warning_count: 0,
      ...(overrides.health || {})
    },
    metadata: { generated_at: new Date(NOW - HOUR).toISOString(), check_interval_minutes: 360 },
    quality: { records: overrides.qualityRecords || [] },
    errors: overrides.errors || {},
    now: overrides.now || NOW
  };
}

const WARNING = {
  code: "cutoff-start-year-mismatch",
  severity: "warning",
  message: "Change cutoff 2026-02-04 and train start 2025-02-09 are in different years",
  pqu_id: "10.0.46-PQU-1",
  field: "change_cutoff_date"
};

test("healthy when checked recently with no warnings", () => {
  const result = health.assess(doc());
  assert.equal(result.state, "healthy");
  assert.equal(result.label, "Up to date");
  assert.equal(result.ageMinutes, 60);
});

test("warnings count only warning severity items", () => {
  const info = { ...WARNING, severity: "info", code: "maintenance-geo-unmapped" };
  const result = health.assess(doc({ qualityRecords: [WARNING, info] }));
  assert.equal(result.state, "warnings");
  assert.equal(result.label, "1 source warning");
  assert.equal(result.warnings.length, 1);
  const two = health.assess(doc({ qualityRecords: [WARNING, { ...WARNING, pqu_id: "x" }] }));
  assert.equal(two.label, "2 source warnings");
});

test("falls back to the health warning count when quality details are missing", () => {
  const input = doc({ health: { warning_count: 3 } });
  input.quality = undefined;
  const result = health.assess(input);
  assert.equal(result.state, "warnings");
  assert.equal(result.warningCount, 3);
  assert.equal(result.warningDetailsAvailable, false);
});

test("stale after three check intervals without a successful check", () => {
  const justInside = health.assess(doc({ now: NOW - HOUR + 18 * HOUR }));
  assert.equal(justInside.state, "healthy");
  const stale = health.assess(doc({ now: NOW - HOUR + 18 * HOUR + 60 * 1000, qualityRecords: [WARNING] }));
  assert.equal(stale.state, "stale");
  assert.equal(stale.staleAfterMinutes, 1080);
});

test("failed and unavailable take precedence", () => {
  const failed = health.assess(
    doc({
      health: {
        status: "failed",
        last_successful_check_at: new Date(NOW - 3 * HOUR).toISOString(),
        error: "ParserError: headers changed"
      }
    })
  );
  assert.equal(failed.state, "failed");
  assert.equal(failed.error, "ParserError: headers changed");
  assert.equal(failed.lastSuccessAt, new Date(NOW - 3 * HOUR).toISOString());
  const unavailable = health.assess(doc({ errors: { pqu: new Error("404") } }));
  assert.equal(unavailable.state, "unavailable");
  assert.deepEqual(unavailable.missing, ["pqu"]);
  const optional = health.assess(doc({ errors: { stations: new Error("404") } }));
  assert.equal(optional.state, "healthy");
  assert.deepEqual(optional.missing, ["stations"]);
});

test("uses metadata when health is missing", () => {
  const input = doc();
  input.health = undefined;
  const result = health.assess(input);
  assert.equal(result.checkedAt, input.metadata.generated_at);
  assert.equal(result.intervalMinutes, 360);
});

test("describe explains a year mismatch with published values", () => {
  const records = {
    "10.0.46-PQU-1": { train_start_date: "2025-02-09", change_cutoff_date: "2026-02-04" }
  };
  assert.equal(
    health.describe(WARNING, records),
    "Microsoft lists the start as 9 Feb 2025 and the change cutoff as 4 Feb 2026; the years differ. Values are shown as published."
  );
  assert.equal(health.describe({ code: "other", message: "Plain" }, records), "Plain");
  assert.equal(
    health.describe(WARNING, records, { asPublished: false }),
    "Microsoft lists the start as 9 Feb 2025 and the change cutoff as 4 Feb 2026; the years differ."
  );
  assert.deepEqual(Object.keys(health.flagsByTrain({ records: [WARNING] })), ["10.0.46-PQU-1"]);
  assert.equal(health.formatInterval(360), "every 6 hours");
  assert.equal(health.formatInterval(60), "every hour");
  assert.equal(health.formatInterval(90), "every 90 minutes");
});

test("unreliableDates names the date fields a warning questions", () => {
  const quality = {
    records: [
      WARNING,
      { code: "invalid-cutoff-date", severity: "warning", pqu_id: "10.0.47-PQU-3", field: "change_cutoff_date" },
      { code: "something-new", severity: "warning", pqu_id: "10.0.47-PQU-4", field: "train_end_date" },
      { code: "end-before-start", severity: "info", pqu_id: "10.0.47-PQU-5", field: "train_end_date" },
      { code: "source-stale", severity: "warning", field: "service_updates" }
    ]
  };
  const result = health.unreliableDates(quality);
  assert.deepEqual(Object.keys(result).sort(), ["10.0.46-PQU-1", "10.0.47-PQU-3", "10.0.47-PQU-4"]);
  assert.deepEqual([...result["10.0.46-PQU-1"]].sort(), ["change_cutoff_date", "train_start_date"]);
  assert.deepEqual([...result["10.0.47-PQU-3"]], ["change_cutoff_date"]);
  assert.deepEqual([...result["10.0.47-PQU-4"]], ["train_end_date"]);
});

test("router parses every route with decoded parameters and queries", () => {
  assert.equal(router.parse("").name, "overview");
  assert.equal(router.parse("#/").name, "overview");
  const trains = router.parse("#/trains?status=On-Going&version=10.0.48&q=due%20soon");
  assert.equal(trains.name, "trains");
  assert.deepEqual(trains.query, { status: "On-Going", version: "10.0.48", q: "due soon" });
  assert.deepEqual(router.parse("#/train/10.0.48-PQU-6").params, { id: "10.0.48-PQU-6" });
  assert.deepEqual(router.parse("#/region/North%20Europe").params, { region: "North Europe" });
  assert.equal(router.parse("#/region").name, "region");
  assert.deepEqual(router.parse("#/learn/faq/what-is-the-biweekly-cadence-for-pqu").params, {
    faq: "what-is-the-biweekly-cadence-for-pqu"
  });
  assert.equal(router.parse("#/nope").name, "not-found");
  assert.equal(router.parse("#/train/%E0%A4%A").name, "not-found");
});

test("router builds hrefs that round-trip", () => {
  const href = router.href("trains", {}, { status: "On-Going", version: "", q: "PQU-7" });
  assert.equal(href, "#/trains?status=On-Going&q=PQU-7");
  assert.deepEqual(router.parse(href).query, { status: "On-Going", q: "PQU-7" });
  assert.equal(router.href("region", { region: "North Europe" }), "#/region/North%20Europe");
  assert.equal(router.href("overview"), "#/");
  assert.equal(router.href("train", { id: "10.0.48-PQU-6" }), "#/train/10.0.48-PQU-6");
});
