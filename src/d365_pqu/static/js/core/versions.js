/* Numeric comparison of dotted versions (10.0.48) and builds (10.0.2645.136). */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.versions = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const DOTTED = /^\d+(\.\d+)*$/;
  const BUILD = /^\d+\.\d+\.\d+\.\d+$/;

  function parseVersion(value) {
    const text = String(value === null || value === undefined ? "" : value).trim();
    if (!DOTTED.test(text)) {
      return null;
    }
    return text.split(".").map(Number);
  }

  function compareVersions(a, b) {
    const left = parseVersion(a) || [];
    const right = parseVersion(b) || [];
    for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
      const diff = (left[index] || 0) - (right[index] || 0);
      if (diff !== 0) {
        return diff < 0 ? -1 : 1;
      }
    }
    return 0;
  }

  function isBuild(value) {
    return BUILD.test(String(value === null || value === undefined ? "" : value).trim());
  }

  function uniqueSortedVersions(values) {
    return [...new Set(values.filter((value) => parseVersion(value)))].sort(compareVersions);
  }

  return { compareVersions, isBuild, parseVersion, uniqueSortedVersions };
});
