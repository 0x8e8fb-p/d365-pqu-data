/* Place a build number among the PQU builds Microsoft has published.
 *
 * Each application version has its own build line: application builds are 10.0.<line>.<rev>
 * and platform builds 7.0.<line>.<rev>, and a line only appears in one version's trains. A
 * build is placed by finding the version that uses its line, then comparing it with that
 * version's published builds. Nothing is inferred beyond the published build numbers. */
(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.builds = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  function load(name, file) {
    return typeof module === "object" && module.exports ? require(file) : root.PQU[name];
  }
  const versions = load("versions", "./versions.js");

  const KINDS = [
    { field: "application_build", label: "application build" },
    { field: "platform_build", label: "platform build" }
  ];
  const BUILD = /^\d+\.\d+\.\d+\.\d+$/;

  function normalize(value) {
    return String(value === null || value === undefined ? "" : value)
      .trim()
      .replace(/^v(?=\d)/i, "");
  }

  function lineOf(build) {
    return build.split(".").slice(0, 3).join(".");
  }

  /* Published builds of one kind that share `input`'s line, oldest first. */
  function candidates(records, field, line) {
    return records
      .filter((record) => BUILD.test(String(record[field] || "")) && lineOf(record[field]) === line)
      .sort((a, b) => versions.compareVersions(a[field], b[field]));
  }

  /*
   * Result kinds:
   *   invalid  - not a four-part build number
   *   exact    - a published train has this build (match)
   *   between  - newer than `older`, older than `newer`
   *   before   - older than the first published build of its version
   *   after    - newer than the latest published build of its version
   *   unknown  - no published train uses this build line
   */
  function locate(records, input) {
    const value = normalize(input);
    if (!BUILD.test(value)) {
      return { kind: "invalid", input: value };
    }
    const line = lineOf(value);
    for (const kind of KINDS) {
      const list = candidates(records || [], kind.field, line);
      if (!list.length) {
        continue;
      }
      const base = {
        input: value,
        field: kind.field,
        label: kind.label,
        version: list[0].application_version,
        published: list
      };
      const match = list.find((record) => versions.compareVersions(record[kind.field], value) === 0);
      if (match) {
        const newer = list.filter((record) => versions.compareVersions(record[kind.field], value) > 0);
        return { ...base, kind: "exact", match, newerCount: newer.length, latest: list[list.length - 1] };
      }
      const older = list.filter((record) => versions.compareVersions(record[kind.field], value) < 0);
      const newer = list.filter((record) => versions.compareVersions(record[kind.field], value) > 0);
      if (!older.length) {
        return { ...base, kind: "before", newer: newer[0], newerCount: newer.length, latest: list[list.length - 1] };
      }
      if (!newer.length) {
        return { ...base, kind: "after", older: older[older.length - 1], newerCount: 0, latest: list[list.length - 1] };
      }
      return {
        ...base,
        kind: "between",
        older: older[older.length - 1],
        newer: newer[0],
        newerCount: newer.length,
        latest: list[list.length - 1]
      };
    }
    return { kind: "unknown", input: value };
  }

  return { locate, lineOf, normalize };
});
