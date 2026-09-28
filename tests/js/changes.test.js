"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const changes = require("../../src/d365_pqu/static/js/core/changes.js");

function change(entity, changeType, field, oldValue, newValue, extra = {}) {
  return {
    change_id: `${entity}-${changeType}-${field}`,
    changed_at: "2026-09-28T03:00:00Z",
    pqu_id: "10.0.48-PQU-6",
    entity,
    change_type: changeType,
    field,
    old_value: oldValue,
    new_value: newValue,
    source_commit: "c".repeat(40),
    ...extra
  };
}

test("train changes restate Microsoft's values", () => {
  const build = changes.describe(change("pqu", "modified", "platform_build", "7.0.7996.119", "7.0.7996.130"));
  assert.equal(build.subject, "10.0.48 PQU-6");
  assert.equal(build.text, "Platform build changed from 7.0.7996.119 to 7.0.7996.130");
  assert.equal(
    changes.describe(change("pqu", "modified", "status", "In-Progress", "Completed")).text,
    "Status changed from In-Progress to Completed"
  );
  assert.equal(
    changes.describe(change("pqu", "modified", "application_build", null, "10.0.2645.140")).text,
    "Application build published: 10.0.2645.140"
  );
  assert.equal(
    changes.describe(change("pqu", "modified", "train_end_date", "2026-10-10", "2026-10-17")).text,
    "Train end changed from 10 Oct 2026 to 17 Oct 2026"
  );
  assert.equal(
    changes.describe(change("pqu", "modified", "station_schedule_available", true, false)).text,
    "Station schedule changed from published to not published"
  );
  assert.equal(
    changes.describe(change("pqu", "added", null, null, { status: "Not Started" })).text,
    "Added to Microsoft's schedule as Not Started"
  );
  assert.equal(
    changes.describe(change("pqu", "removed", null, { status: "Completed" }, null)).text,
    "Removed from Microsoft's schedule (was Completed)"
  );
});

test("station changes name the station and its windows", () => {
  const window = {
    sandbox_start_date: "2026-10-05",
    sandbox_end_date: "2026-10-08",
    production_start_date: "2026-10-10",
    production_end_date: "2026-10-11"
  };
  assert.equal(
    changes.describe(change("station", "added", "station.5", null, window)).text,
    "Station 5 schedule published: sandbox 5–8 Oct 2026, production 10–11 Oct 2026"
  );
  assert.equal(changes.describe(change("station", "removed", "station.3", window, null)).text, "Station 3 schedule removed");
  // Older history records station rows without the station number.
  assert.equal(changes.describe(change("station", "removed", null, window, null)).text, "A station schedule removed");
  assert.equal(
    changes.describe(change("station", "modified", "station.4.sandbox_start_date", "2026-09-28", "2026-09-29")).text,
    "Station 4 sandbox start changed from 28 Sep 2026 to 29 Sep 2026"
  );
});

test("dataset-level changes", () => {
  const dataset = { pqu_id: "dataset" };
  const region = changes.describe(
    change("region", "added", "region.Mexico Central", null, { station: 3, region: "Mexico Central" }, dataset)
  );
  assert.deepEqual([region.subject, region.text], ["Mexico Central", "Added to Station 3"]);
  const guidance = changes.describe(
    change("guidance", "modified", "pqu_faq#what-are-pqus", { title: "What are PQUs?" }, { title: "What are PQUs?" }, dataset),
    { sourceLabel: (key) => (key === "pqu_faq" ? "Proactive quality updates FAQ" : null) }
  );
  assert.equal(guidance.subject, "Proactive quality updates FAQ");
  assert.equal(guidance.text, "Microsoft updated the text of “What are PQUs?”");
  assert.equal(
    changes.describe(change("guidance", "removed", "schedule#more-information", { title: "More information" }, null, dataset))
      .text,
    "Section “More information” removed"
  );
  assert.equal(changes.describe(change("guidance", "added", "schedule#x", null, {}, dataset)).subject, "Microsoft guidance");
  const serviceUpdate = changes.describe(
    change("service_update", "modified", "10.0.49#general_availability_date", "2026-09-11", "2026-09-18", dataset)
  );
  assert.deepEqual(
    [serviceUpdate.subject, serviceUpdate.text],
    ["10.0.49", "General availability changed from 11 Sep 2026 to 18 Sep 2026"]
  );
  const maintenance = changes.describe(
    change("maintenance_window", "modified", "Europe#days", ["Friday", "Saturday"], ["Saturday"], dataset)
  );
  assert.deepEqual(
    [maintenance.subject, maintenance.text],
    ["Europe", "Maintenance window days changed from Friday and Saturday to Saturday"]
  );
  assert.equal(
    changes.describe(change("service_update", "added", "10.0.50", null, {}, dataset)).text,
    "Added to Microsoft's service update schedule"
  );
});

test("train filter and sync grouping", () => {
  const list = [
    change("pqu", "modified", "status", "In-Progress", "Completed", { changed_at: "2026-09-29T03:00:00Z" }),
    change("station", "removed", "station.4", {}, null, { changed_at: "2026-09-29T03:00:00Z" }),
    change("pqu", "modified", "platform_build", "a", "b"),
    change("pqu", "modified", "status", "Not Started", "In-Progress", { pqu_id: "10.0.48-PQU-7" }),
    change("guidance", "modified", "schedule#schedule", {}, {}, { pqu_id: "dataset" })
  ];
  const mine = changes.forTrain(list, "10.0.48-PQU-6");
  assert.equal(mine.length, 3);
  assert.equal(mine[0].changed_at, "2026-09-29T03:00:00Z");
  const groups = changes.bySync(mine);
  assert.deepEqual(
    groups.map((group) => [group.changed_at, group.changes.length]),
    [
      ["2026-09-29T03:00:00Z", 2],
      ["2026-09-28T03:00:00Z", 1]
    ]
  );
});

test("station schedules published or removed together share one line", () => {
  const at = { changed_at: "2026-09-29T03:00:00Z" };
  const removed = [1, 2, 3, 4, 5, 6].map((station) => change("station", "removed", `station.${station}`, {}, null, at));
  const list = [
    change("pqu", "modified", "status", "In-Progress", "Completed", at),
    ...removed,
    change("station", "added", "station.2", null, {}, { ...at, pqu_id: "10.0.48-PQU-7" }),
    change("station", "modified", "station.4.sandbox_end_date", "2026-10-01", "2026-10-02", at)
  ];
  const result = changes.lines(list);
  assert.deepEqual(
    result.map((line) => line.text),
    [
      "Status changed from In-Progress to Completed",
      "Schedules removed for Stations 1, 2, 3, 4, 5 and 6",
      "Station 2 schedule published",
      "Station 4 sandbox end changed from 1 Oct 2026 to 2 Oct 2026"
    ]
  );
  assert.equal(result[1].ids.length, 6);
  assert.equal(result[1].subject, "10.0.48 PQU-6");
  assert.equal(result[2].subject, "10.0.48 PQU-7");
  assert.equal(result[1].href, "#/train/10.0.48-PQU-6");
  assert.deepEqual(result[1].commits, ["c".repeat(40)]);
});

test("each change links to where the dashboard shows it", () => {
  const dataset = { pqu_id: "dataset" };
  const href = (entity, type, field, oldValue = null, newValue = null) =>
    changes.hrefFor(change(entity, type, field, oldValue, newValue, entity === "pqu" || entity === "station" ? {} : dataset));
  assert.equal(href("pqu", "modified", "status"), "#/train/10.0.48-PQU-6");
  assert.equal(href("station", "removed", "station.3"), "#/train/10.0.48-PQU-6");
  assert.equal(href("service_update", "modified", "10.0.49#preview_date"), "#/versions?version=10.0.49");
  assert.equal(href("region", "added", "region.North Europe"), "#/region/North%20Europe");
  assert.equal(href("region", "removed", "region.North Europe"), null);
  assert.equal(href("maintenance_window", "modified", "Europe#days"), "#/learn");
  const url = "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates-faq#faq";
  assert.equal(href("guidance", "modified", "pqu_faq#faq", { url }, { url }), url);
  assert.equal(href("guidance", "added", "pqu_faq#faq", null, { url: "javascript:alert(1)" }), null);
});

test("checks are grouped by day in the viewer's time zone", () => {
  const list = [
    change("pqu", "modified", "status", "a", "b", { changed_at: "2026-09-27T20:00:00Z" }),
    change("pqu", "modified", "uep_version", "a", "b", { changed_at: "2026-09-27T20:00:00Z" }),
    change("pqu", "modified", "status", "a", "b", { changed_at: "2026-09-27T17:00:00Z" }),
    change("pqu", "modified", "status", "a", "b", { changed_at: "2026-09-28T03:00:00Z" })
  ];
  const kolkata = changes.byDay(list, "Asia/Kolkata");
  assert.deepEqual(
    kolkata.map((day) => [day.day, day.syncs.map((sync) => [sync.changed_at, sync.changes.length])]),
    [
      [
        "2026-09-28",
        [
          ["2026-09-28T03:00:00Z", 1],
          ["2026-09-27T20:00:00Z", 2]
        ]
      ],
      ["2026-09-27", [["2026-09-27T17:00:00Z", 1]]]
    ]
  );
  const utc = changes.byDay(list, "UTC");
  assert.deepEqual(
    utc.map((day) => [day.day, day.syncs.length]),
    [
      ["2026-09-28", 1],
      ["2026-09-27", 2]
    ]
  );
});
