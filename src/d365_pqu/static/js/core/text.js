/* Small wording helpers shared by the views. They format values; they never state facts. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.text = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function plural(count, singular, pluralForm) {
    const word = count === 1 ? singular : pluralForm || `${singular}s`;
    return `${count} ${word}`;
  }

  function joinList(items) {
    const values = items.filter((item) => item !== null && item !== undefined && item !== "");
    if (values.length <= 1) {
      return values.join("");
    }
    if (values.length === 2) {
      return `${values[0]} and ${values[1]}`;
    }
    return `${values.slice(0, -1).join(", ")} and ${values[values.length - 1]}`;
  }

  function stationList(numbers) {
    const sorted = [...new Set(numbers)].sort((a, b) => a - b);
    if (sorted.length === 0) {
      return "";
    }
    if (sorted.length === 1) {
      return `Station ${sorted[0]}`;
    }
    return `Stations ${joinList(sorted.map(String))}`;
  }

  function normalizeSearch(value) {
    return String(value === null || value === undefined ? "" : value)
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .toLowerCase()
      .replace(/\s+/g, " ")
      .trim();
  }

  /* "10.0.48-PQU-6" -> "10.0.48 PQU-6" for reading; identifiers stay unchanged in data. */
  function trainLabel(pquId) {
    const match = /^(\d+\.\d+\.\d+)-(PQU-\d+)$/.exec(String(pquId || ""));
    return match ? `${match[1]} ${match[2]}` : String(pquId || "");
  }

  function capitalize(value) {
    const text = String(value || "");
    return text ? text[0].toUpperCase() + text.slice(1) : text;
  }

  return { capitalize, joinList, normalizeSearch, plural, stationList, trainLabel };
});
