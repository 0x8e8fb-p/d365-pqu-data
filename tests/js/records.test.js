"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const versions = require("../../src/d365_pqu/static/js/core/versions.js");
const records = require("../../src/d365_pqu/static/js/core/records.js");
const text = require("../../src/d365_pqu/static/js/core/text.js");

function train(overrides) {
  return {
    pqu_id: "10.0.48-PQU-6",
    application_version: "10.0.48",
    pqu_train: "PQU-6",
    release_number: 6,
    status: "In-Progress",
    change_cutoff_date: "2026-09-16",
    train_start_date: "2026-09-16",
    train_end_date: "2026-10-10",
    application_build: "10.0.2645.136",
    platform_build: "7.0.7996.119",
    uep_version: "10.0.48.7",
    station_schedule_available: true,
    ...overrides
  };
}

test("compareVersions orders numerically, not lexically", () => {
  assert.equal(versions.compareVersions("10.0.9", "10.0.10"), -1);
  assert.equal(versions.compareVersions("10.0.2527.215", "10.0.2527.160"), 1);
  assert.equal(versions.compareVersions("10.0.48", "10.0.48"), 0);
  assert.deepEqual(versions.uniqueSortedVersions(["10.0.48", "10.0.9", "10.0.48", "x"]), [
    "10.0.9",
    "10.0.48"
  ]);
  assert.equal(versions.isBuild("10.0.2527.160"), true);
  assert.equal(versions.isBuild("10.0.2527"), false);
});

test("sortRecords handles versions, numbers, and blanks last", () => {
  const list = [
    train({ pqu_id: "b", application_version: "10.0.9", release_number: 3 }),
    train({ pqu_id: "a", application_version: "10.0.10", release_number: 12 }),
    train({ pqu_id: "c", application_version: "10.0.9", release_number: 11, application_build: null })
  ];
  assert.deepEqual(
    records.sortRecords(list, { key: "application_version", direction: 1 }).map((r) => r.pqu_id),
    ["b", "c", "a"]
  );
  assert.deepEqual(
    records.sortRecords(list, { key: "release_number", direction: -1 }).map((r) => r.pqu_id),
    ["a", "c", "b"]
  );
  assert.equal(
    records.sortRecords(list, { key: "application_build", direction: -1 }).at(-1).pqu_id,
    "c"
  );
  assert.deepEqual(records.sortRecords(list, null).map((r) => r.pqu_id), ["b", "a", "c"]);
});

test("filterRecords applies status groups, version, and search", () => {
  const list = [
    train({ pqu_id: "10.0.48-PQU-6", status: "In-Progress" }),
    train({ pqu_id: "10.0.48-PQU-7", status: "Not Started", application_build: null }),
    train({ pqu_id: "10.0.47-PQU-2", application_version: "10.0.47", status: "Canceled" })
  ];
  assert.equal(records.filterRecords(list, { status: "On-Going" }).length, 2);
  assert.equal(records.filterRecords(list, { status: "Canceled" }).length, 1);
  assert.equal(records.filterRecords(list, { version: "10.0.47" }).length, 1);
  assert.equal(records.filterRecords(list, { search: "10.0.48 pqu-7" }).length, 1);
  assert.equal(records.filterRecords(list, { search: "  CANCELED " }).length, 1);
  assert.equal(
    records.filterRecords(list, { search: "due soon" }, (r) => (r.status === "Not Started" ? "due soon" : ""))
      .length,
    1
  );
});

test("isDueSoon covers only Not Started trains starting within seven days", () => {
  const today = "2026-09-28";
  assert.equal(records.isDueSoon(train({ status: "Not Started", train_start_date: "2026-09-30" }), today), true);
  assert.equal(records.isDueSoon(train({ status: "Not Started", train_start_date: "2026-10-05" }), today), true);
  assert.equal(records.isDueSoon(train({ status: "Not Started", train_start_date: "2026-10-06" }), today), false);
  assert.equal(records.isDueSoon(train({ status: "Not Started", train_start_date: "2026-09-27" }), today), false);
  assert.equal(records.isDueSoon(train({ status: "In-Progress", train_start_date: "2026-09-30" }), today), false);
  assert.equal(records.isDueSoon(train({ status: "Not Started", train_start_date: null }), today), false);
});

test("paginate clamps the page and reports the visible range", () => {
  const items = Array.from({ length: 45 }, (_, index) => index);
  const page = records.paginate(items, 3, 20);
  assert.equal(page.page, 3);
  assert.equal(page.pageCount, 3);
  assert.equal(page.first, 41);
  assert.equal(page.last, 45);
  assert.equal(records.paginate(items, 99, 20).page, 3);
  assert.equal(records.paginate([], 1, 20).first, 0);
});

test("statusOptions are derived from the data with counts", () => {
  const list = [
    train({ status: "In-Progress" }),
    train({ status: "Not Started" }),
    train({ status: "Not Started" }),
    train({ status: "Completed" })
  ];
  const options = records.statusOptions(list);
  assert.deepEqual(
    options.map((option) => [option.value, option.count]),
    [
      ["On-Going", 3],
      ["In-Progress", 1],
      ["Not Started", 2],
      ["Completed", 1]
    ]
  );
});

test("text helpers format lists and labels", () => {
  assert.equal(text.plural(1, "train"), "1 train");
  assert.equal(text.plural(5, "train"), "5 trains");
  assert.equal(text.joinList(["a", "b", "c"]), "a, b and c");
  assert.equal(text.stationList([3, 2]), "Stations 2 and 3");
  assert.equal(text.stationList([4]), "Station 4");
  assert.equal(text.trainLabel("10.0.48-PQU-6"), "10.0.48 PQU-6");
  assert.equal(text.normalizeSearch("  Zürich   North "), "zurich north");
});

const QUERY_OPTIONS = {
  statuses: new Set(["On-Going", "In-Progress", "Not Started", "Completed", "Canceled"]),
  versions: new Set(["10.0.47", "10.0.48"]),
  regions: new Set(["North Europe", "East US"]),
  sortKeys: new Set(["pqu_id", "train_start_date"]),
  pageSizes: [10, 20, 50],
  defaultPageSize: 20,
  zooms: ["3m", "6m", "all"],
  defaultZoom: "3m"
};

test("parseTrainsQuery keeps only values that exist in the data", () => {
  const state = records.parseTrainsQuery(
    {
      q: "pqu-7",
      status: "On-Going",
      version: "10.0.48",
      region: "North Europe",
      sort: "train_start_date",
      dir: "desc",
      page: "2",
      size: "50"
    },
    QUERY_OPTIONS
  );
  assert.deepEqual(state, {
    search: "pqu-7",
    status: "On-Going",
    version: "10.0.48",
    region: "North Europe",
    sort: { key: "train_start_date", direction: -1 },
    page: 2,
    pageSize: 50,
    display: "table",
    zoom: "3m"
  });
  const junk = records.parseTrainsQuery(
    {
      status: "Exploded",
      version: "9.9.9",
      region: "Mars",
      sort: "evil",
      page: "-3",
      size: "7",
      view: "chart",
      zoom: "12m"
    },
    QUERY_OPTIONS
  );
  assert.deepEqual(junk, {
    search: "",
    status: "",
    version: "",
    region: "",
    sort: { key: null, direction: 1 },
    page: 1,
    pageSize: 20,
    display: "table",
    zoom: "3m"
  });
  assert.equal(records.parseTrainsQuery({ q: "x".repeat(500) }, QUERY_OPTIONS).search.length, 200);
  assert.equal(records.parseTrainsQuery({ page: "2.5" }, QUERY_OPTIONS).page, 1);
});

test("trainsQuery omits defaults and round-trips", () => {
  const state = {
    search: "due soon",
    status: "",
    version: "10.0.47",
    region: "",
    sort: { key: "pqu_id", direction: 1 },
    page: 1,
    pageSize: 20,
    display: "table",
    zoom: "3m"
  };
  const query = records.trainsQuery(state, 20, "3m");
  assert.deepEqual(
    Object.fromEntries(Object.entries(query).filter(([, value]) => value !== null)),
    { q: "due soon", version: "10.0.47", sort: "pqu_id" }
  );
  assert.deepEqual(records.parseTrainsQuery(query, QUERY_OPTIONS), state);
  const descending = records.trainsQuery({ ...state, sort: { key: "pqu_id", direction: -1 }, page: 3, pageSize: 10 }, 20);
  assert.equal(descending.dir, "desc");
  assert.equal(descending.page, "3");
  assert.equal(descending.size, "10");
});

test("the display and timeline zoom round-trip; zoom is written only for the timeline", () => {
  const base = records.parseTrainsQuery({}, QUERY_OPTIONS);
  const timeline = { ...base, display: "timeline", zoom: "all" };
  const query = records.trainsQuery(timeline, 20, "3m");
  assert.equal(query.view, "timeline");
  assert.equal(query.zoom, "all");
  assert.deepEqual(records.parseTrainsQuery(query, QUERY_OPTIONS), timeline);
  assert.equal(records.trainsQuery({ ...timeline, zoom: "3m" }, 20, "3m").zoom, null);
  const table = records.trainsQuery({ ...timeline, display: "table" }, 20, "3m");
  assert.equal(table.view, null);
  assert.equal(table.zoom, null);
  assert.deepEqual(records.DISPLAYS, ["table", "timeline"]);
});
