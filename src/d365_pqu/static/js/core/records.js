/* Filtering, sorting, and paging of PQU train records. */
(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.records = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  function load(name, file) {
    return typeof module === "object" && module.exports ? require(file) : root.PQU[name];
  }
  const dates = load("dates", "./dates.js");
  const versions = load("versions", "./versions.js");
  const text = load("text", "./text.js");

  const STATUS_ORDER = ["In-Progress", "Not Started", "Completed", "Canceled"];
  const STATUS_GROUPS = { "On-Going": ["In-Progress", "Not Started"] };
  const DUE_SOON_DAYS = 7;

  function isBlank(value) {
    return value === null || value === undefined || value === "";
  }

  function sortValue(record, key) {
    const value = record[key];
    if (isBlank(value)) {
      return null;
    }
    if (typeof value === "boolean") {
      return value ? 1 : 0;
    }
    if (key === "release_number") {
      return Number(value);
    }
    return String(value);
  }

  function compareRecords(a, b, key, direction) {
    const left = sortValue(a, key);
    const right = sortValue(b, key);
    if (left === null && right === null) {
      return 0;
    }
    if (left === null) {
      return 1;
    }
    if (right === null) {
      return -1;
    }
    if (key === "application_version" || key === "application_build" || key === "platform_build") {
      return versions.compareVersions(left, right) * direction;
    }
    if (typeof left === "number" && typeof right === "number") {
      return (left - right) * direction;
    }
    return String(left).localeCompare(String(right), "en", { numeric: true }) * direction;
  }

  function sortRecords(records, sort) {
    if (!sort || !sort.key) {
      return records.slice();
    }
    const direction = sort.direction === -1 ? -1 : 1;
    return records.slice().sort((a, b) => compareRecords(a, b, sort.key, direction));
  }

  function matchesStatus(record, status) {
    if (!status) {
      return true;
    }
    if (STATUS_GROUPS[status]) {
      return STATUS_GROUPS[status].includes(record.status);
    }
    return record.status === status;
  }

  /* Not Started trains whose published start date is within the next seven days. */
  function isDueSoon(record, todayIso) {
    if (!record || record.status !== "Not Started" || !dates.isIsoDate(record.train_start_date)) {
      return false;
    }
    const days = dates.diffDays(todayIso, record.train_start_date);
    return days !== null && days >= 0 && days <= DUE_SOON_DAYS;
  }

  function searchHaystack(record, extra) {
    return text.normalizeSearch(
      [
        record.pqu_id,
        text.trainLabel(record.pqu_id),
        record.application_version,
        record.pqu_train,
        record.status,
        record.application_build,
        record.platform_build,
        record.uep_version,
        extra || ""
      ].join(" ")
    );
  }

  function filterRecords(records, criteria = {}, extraText) {
    const search = text.normalizeSearch(criteria.search || "");
    return records.filter((record) => {
      if (!matchesStatus(record, criteria.status || "")) {
        return false;
      }
      if (criteria.version && record.application_version !== criteria.version) {
        return false;
      }
      if (!search) {
        return true;
      }
      const extra = typeof extraText === "function" ? extraText(record) : "";
      return searchHaystack(record, extra).includes(search);
    });
  }

  function paginate(items, page, pageSize) {
    const size = Math.max(1, Number(pageSize) || 20);
    const pageCount = Math.max(1, Math.ceil(items.length / size));
    const current = Math.min(Math.max(1, Number(page) || 1), pageCount);
    const start = (current - 1) * size;
    return {
      items: items.slice(start, start + size),
      page: current,
      pageCount,
      pageSize: size,
      first: items.length === 0 ? 0 : start + 1,
      last: Math.min(start + size, items.length),
      total: items.length
    };
  }

  function stationsFor(stations, pquId) {
    return stations.filter((row) => row.pqu_id === pquId).sort((a, b) => a.station - b.station);
  }

  function statusCounts(records) {
    const counts = {};
    for (const record of records) {
      counts[record.status] = (counts[record.status] || 0) + 1;
    }
    return counts;
  }

  /* Status filter options derived from the data: groups first, then observed statuses. */
  function statusOptions(records) {
    const counts = statusCounts(records);
    const options = [];
    for (const [group, members] of Object.entries(STATUS_GROUPS)) {
      const count = members.reduce((sum, status) => sum + (counts[status] || 0), 0);
      if (count > 0) {
        options.push({ value: group, label: group, count, members });
      }
    }
    const observed = Object.keys(counts).sort((a, b) => {
      const left = STATUS_ORDER.indexOf(a);
      const right = STATUS_ORDER.indexOf(b);
      return (left === -1 ? 99 : left) - (right === -1 ? 99 : right) || a.localeCompare(b);
    });
    for (const status of observed) {
      options.push({ value: status, label: status, count: counts[status], members: [status] });
    }
    return options;
  }

  const MAX_SEARCH_LENGTH = 200;
  /* How the Trains tab shows the matching trains; the first is the default. */
  const DISPLAYS = ["table", "timeline"];

  /*
   * Trains view state from URL query parameters. Values that do not match the published data
   * (unknown status, version, region, column, or page size) are ignored. `view` picks the
   * display and `zoom` the timeline range (options.zooms, default options.defaultZoom).
   */
  function parseTrainsQuery(query, options) {
    const input = query || {};
    const zooms = options.zooms || [];
    const state = {
      search: typeof input.q === "string" ? input.q.slice(0, MAX_SEARCH_LENGTH) : "",
      status: options.statuses.has(input.status) ? input.status : "",
      version: options.versions.has(input.version) ? input.version : "",
      region: options.regions.has(input.region) ? input.region : "",
      sort: { key: null, direction: 1 },
      page: 1,
      pageSize: options.defaultPageSize,
      display: DISPLAYS.includes(input.view) ? input.view : DISPLAYS[0],
      zoom: zooms.includes(input.zoom) ? input.zoom : options.defaultZoom || null
    };
    if (options.sortKeys.has(input.sort)) {
      state.sort = { key: input.sort, direction: input.dir === "desc" ? -1 : 1 };
    }
    const page = /^\d+$/.test(String(input.page || "")) ? Number(input.page) : 0;
    if (page > 0) {
      state.page = page;
    }
    const size = Number(input.size);
    if (options.pageSizes.includes(size)) {
      state.pageSize = size;
    }
    return state;
  }

  /* URL query for a trains view state; defaults are omitted so links stay short. The zoom is
   * only written for the timeline, where it applies. */
  function trainsQuery(state, defaultPageSize, defaultZoom = null) {
    const sortKey = state.sort && state.sort.key;
    const timeline = state.display === "timeline";
    return {
      q: state.search || null,
      status: state.status || null,
      version: state.version || null,
      region: state.region || null,
      sort: sortKey || null,
      dir: sortKey && state.sort.direction === -1 ? "desc" : null,
      page: state.page > 1 ? String(state.page) : null,
      size: state.pageSize !== defaultPageSize ? String(state.pageSize) : null,
      view: state.display && state.display !== DISPLAYS[0] ? state.display : null,
      zoom: timeline && state.zoom && state.zoom !== defaultZoom ? state.zoom : null
    };
  }

  return {
    DISPLAYS,
    DUE_SOON_DAYS,
    STATUS_GROUPS,
    STATUS_ORDER,
    compareRecords,
    filterRecords,
    isDueSoon,
    matchesStatus,
    paginate,
    parseTrainsQuery,
    searchHaystack,
    sortRecords,
    sortValue,
    stationsFor,
    statusCounts,
    statusOptions,
    trainsQuery
  };
});
