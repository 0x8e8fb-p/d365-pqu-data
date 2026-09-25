"use strict";

const TIME_ZONE = "Asia/Kolkata";
const TIME_ZONE_LABEL = "IST";
const THEME_KEY = "d365-pqu-theme";
const ASSET_VERSION = "__ASSET_VERSION__";
const DATE_FORMATTER = new Intl.DateTimeFormat("en-IN", {
  timeZone: TIME_ZONE,
  day: "2-digit",
  month: "short",
  year: "numeric"
});
const TIME_FORMATTER = new Intl.DateTimeFormat("en-IN", {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false
});

const state = {
  records: [],
  stations: [],
  regions: [],
  metadata: null,
  health: null,
  sort: { key: null, direction: 1 },
  page: 1,
  pageSize: 20,
  activeStation: null,
  expanded: []
};

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined) {
      continue;
    }
    if (key === "class") {
      node.className = value;
    } else if (key === "text") {
      node.textContent = value;
    } else if (key === "href") {
      node.href = value;
    } else if (key === "hidden" || key === "disabled") {
      node[key] = Boolean(value);
    } else if (
      key === "type" ||
      key === "value" ||
      key === "placeholder" ||
      key === "datetime" ||
      key === "role" ||
      key.startsWith("aria-") ||
      key.startsWith("data-")
    ) {
      node.setAttribute(key, value);
    }
  }
  for (const child of children) {
    if (child === null || child === undefined) {
      continue;
    }
    node.append(child);
  }
  return node;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) {
    node.textContent = value === null || value === undefined || value === "" ? "—" : String(value);
  }
}

function formatDate(value) {
  if (!value) {
    return "—";
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value).trim());
  if (!match) {
    return String(value);
  }
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return DATE_FORMATTER.format(date);
}

function formatTimestamp(value) {
  if (!value) {
    return "—";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return `${DATE_FORMATTER.format(date)} · ${TIME_FORMATTER.format(date)} ${TIME_ZONE_LABEL}`;
}

function requireElement(id) {
  const node = document.getElementById(id);
  if (!node) {
    throw new Error(`Dashboard is missing required element: ${id} (assets ${ASSET_VERSION})`);
  }
  return node;
}

function showLoadError(error) {
  const banner = document.getElementById("load-error");
  const message = `The dataset could not be loaded: ${error.message} (assets ${ASSET_VERSION})`;
  if (!banner) {
    return;
  }
  banner.hidden = false;
  banner.textContent = message;
  setText("sync-label", "Dataset unavailable");
  setTime("sync-time", null);
}

function setTime(id, value) {
  const node = document.getElementById(id);
  if (!node) {
    return;
  }
  if (value) {
    node.setAttribute("datetime", String(value));
  } else {
    node.removeAttribute("datetime");
  }
  node.textContent = formatTimestamp(value);
}

function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

function applyTheme(theme, persist = true) {
  const next = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  const toggle = document.getElementById("theme-toggle");
  const moon = document.getElementById("theme-icon-moon");
  const sun = document.getElementById("theme-icon-sun");
  if (toggle) {
    toggle.setAttribute("aria-pressed", next === "light" ? "true" : "false");
    toggle.setAttribute(
      "aria-label",
      next === "light" ? "Switch to dark theme" : "Switch to light theme"
    );
  }
  if (moon) {
    moon.style.display = next === "light" ? "none" : "";
  }
  if (sun) {
    sun.style.display = next === "light" ? "" : "none";
  }
  if (persist) {
    try {
      window.localStorage.setItem(THEME_KEY, next);
    } catch (error) {
      /* Storage may be unavailable; the data-theme attribute still controls the theme. */
    }
  }
}

function todayIstIso(now = Date.now()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).formatToParts(new Date(now));
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function addDaysIso(isoDate, days) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate);
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function isDueSoon(record, todayIso = todayIstIso()) {
  if (!record || record.status !== "Not Started") {
    return false;
  }
  if (!/^(\d{4})-(\d{2})-(\d{2})$/.exec(record.train_start_date || "")) {
    return false;
  }
  return (
    record.train_start_date >= todayIso && record.train_start_date <= addDaysIso(todayIso, 7)
  );
}

function statusClass(status) {
  return (
    "badge " +
    String(status).toLowerCase().replace(/[^a-z]+/g, "-").replace(/(^-|-$)/g, "")
  );
}

function statusCell(record) {
  const cell = el("td", {}, [
    el("span", { class: statusClass(record.status), text: record.status })
  ]);
  if (isDueSoon(record)) {
    cell.append(
      el("span", {
        class: "due",
        text: `Due soon · starts ${formatDate(record.train_start_date)}`
      })
    );
  }
  return cell;
}

function textCell(value, mono = false) {
  return el("td", {
    class: mono ? "mono" : "",
    text: value === null || value === undefined || value === "" ? "—" : String(value)
  });
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`${path} returned ${response.status}`);
  }
  return response.json();
}

function compareVersions(a, b) {
  const left = String(a).split(".").map(Number);
  const right = String(b).split(".").map(Number);
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const diff = (left[index] || 0) - (right[index] || 0);
    if (diff !== 0) {
      return diff;
    }
  }
  return 0;
}

function sortValue(record, key) {
  const value = record[key];
  if (value === null || value === undefined || value === "") {
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
  if (key === "application_version") {
    return compareVersions(left, right) * direction;
  }
  if (typeof left === "number" && typeof right === "number") {
    return (left - right) * direction;
  }
  return String(left).localeCompare(String(right), "en", { numeric: true }) * direction;
}

const STATUS_GROUPS = {
  "On-Going": ["In-Progress", "Not Started"]
};

function filteredRecords() {
  const search = (document.getElementById("search").value || "").trim().toLowerCase();
  const status = document.getElementById("status-filter").value;
  const version = document.getElementById("version-filter").value;
  const matches = state.records.filter((record) => {
    if (status === "On-Going") {
      if (!STATUS_GROUPS["On-Going"].includes(record.status)) {
        return false;
      }
    } else if (status && record.status !== status) {
      return false;
    }
    if (version && record.application_version !== version) {
      return false;
    }
    if (!search) {
      return true;
    }
    const haystack = [
      record.pqu_id,
      record.application_version,
      record.pqu_train,
      record.status,
      record.application_build,
      record.platform_build,
      record.uep_version,
      isDueSoon(record) ? "due soon" : ""
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(search);
  });
  if (state.sort.key) {
    return [...matches].sort((a, b) =>
      compareRecords(a, b, state.sort.key, state.sort.direction)
    );
  }
  return matches;
}

function updateSortIndicators() {
  const buttons = document.querySelectorAll("#pqu-table .th-sort");
  buttons.forEach((button) => {
    const header = button.closest("th");
    if (!header) {
      return;
    }
    if (button.dataset.sort === state.sort.key) {
      header.setAttribute("aria-sort", state.sort.direction === 1 ? "ascending" : "descending");
    } else {
      header.setAttribute("aria-sort", "none");
    }
  });
}

function stationsFor(pquId) {
  return state.stations
    .filter((row) => row.pqu_id === pquId)
    .sort((a, b) => a.station - b.station);
}

function orderedStations(pquId) {
  const rows = stationsFor(pquId);
  if (state.activeStation === null) {
    return rows;
  }
  return rows.filter((row) => row.station === state.activeStation);
}

function stationWindow(row, startKey, endKey) {
  if (!row[startKey]) {
    return "N/A";
  }
  return `${formatDate(row[startKey])} to ${formatDate(row[endKey])}`;
}

function stationDetailRow(record) {
  const detailId = `stations-${record.pqu_id}`;
  const title =
    state.activeStation === null
      ? `Station windows · ${record.pqu_id}`
      : `Station ${state.activeStation} window · ${record.pqu_id}`;
  const cell = el("td", {}, [
    el("div", { class: "station-detail-body", id: detailId }, [
      el("p", { class: "detail-title", text: title })
    ])
  ]);
  cell.colSpan = 11;
  const body = cell.firstChild;
  const rows = orderedStations(record.pqu_id);
  if (rows.length === 0) {
    body.append(el("p", { class: "detail-empty", text: "No detailed station schedule published." }));
    return el("tr", { class: "station-detail" }, [cell]);
  }
  const tableBody = el("tbody", {}, []);
  for (const row of rows) {
    const stationRow = el("tr", {}, [
      textCell(row.station_label, true),
      textCell(stationWindow(row, "sandbox_start_date", "sandbox_end_date")),
      textCell(stationWindow(row, "production_start_date", "production_end_date"))
    ]);
    if (row.station === state.activeStation) {
      stationRow.classList.add("station-active");
    }
    tableBody.append(stationRow);
  }
  body.append(
    el("table", { class: "station-detail-table" }, [
      el("caption", { class: "visually-hidden", text: `Station windows for ${record.pqu_id}` }),
      el("thead", {}, [
        el("tr", {}, [
          el("th", { scope: "col", text: "Station" }),
          el("th", { scope: "col", text: "Sandbox window" }),
          el("th", { scope: "col", text: "Production window" })
        ])
      ]),
      tableBody
    ])
  );
  return el("tr", { class: "station-detail" }, [cell]);
}

function renderRows() {
  const body = document.querySelector("#pqu-table tbody");
  const records = filteredRecords();
  const pageCount = Math.max(1, Math.ceil(records.length / state.pageSize));
  state.page = Math.min(Math.max(1, state.page), pageCount);
  const start = (state.page - 1) * state.pageSize;
  const pageRecords = records.slice(start, start + state.pageSize);
  body.replaceChildren();
  const fragment = document.createDocumentFragment();
  for (const record of pageRecords) {
    const detailId = `stations-${record.pqu_id}`;
    const hasStations = stationsFor(record.pqu_id).length > 0;
    const expanded = hasStations && state.expanded.includes(record.pqu_id);
    let idCell;
    if (hasStations) {
      const toggle = el(
        "button",
        {
          class: "row-toggle",
          type: "button",
          "aria-expanded": expanded ? "true" : "false",
          "aria-controls": detailId,
          "aria-label": `${expanded ? "Collapse" : "Expand"} station windows for ${record.pqu_id}`
        },
        [
          el("span", { class: "row-toggle-icon", "aria-hidden": "true", text: expanded ? "−" : "+" }),
          el("span", { text: record.pqu_id })
        ]
      );
      toggle.addEventListener("click", () => {
        if (state.expanded.includes(record.pqu_id)) {
          state.expanded = state.expanded.filter((id) => id !== record.pqu_id);
        } else {
          state.expanded = [...state.expanded, record.pqu_id];
        }
        renderRows();
      });
      idCell = el("td", { class: "mono" }, [toggle]);
    } else {
      idCell = textCell(record.pqu_id, true);
    }
    const row = el("tr", {}, [
      idCell,
      textCell(record.application_version, true),
      textCell(record.pqu_train, true),
      statusCell(record),
      textCell(formatDate(record.change_cutoff_date)),
      textCell(formatDate(record.train_start_date)),
      textCell(formatDate(record.train_end_date)),
      textCell(record.application_build, true),
      textCell(record.platform_build, true),
      textCell(record.uep_version, true),
      textCell(record.station_schedule_available ? "Published" : "Not published")
    ]);
    if (record.pqu_id === (state.metadata || {}).latest_pqu_id) {
      row.classList.add("latest");
    }
    if (isDueSoon(record)) {
      row.classList.add("due-soon");
    }
    fragment.append(row);
    if (expanded) {
      fragment.append(stationDetailRow(record));
    }
  }
  body.append(fragment);
  updateSortIndicators();
  const first = records.length === 0 ? 0 : start + 1;
  const last = Math.min(start + state.pageSize, records.length);
  const dueCount = records.filter((record) => isDueSoon(record)).length;
  setText(
    "filter-note",
    `${records.length} of ${state.records.length} trains shown` +
      (dueCount > 0 ? ` · ${dueCount} due soon` : "") +
      (state.activeStation !== null ? ` · Station ${state.activeStation} context` : "")
  );
  setText("page-info", `Page ${state.page} of ${pageCount} · ${first}–${last} of ${records.length}`);
  const prev = document.getElementById("prev-page");
  const next = document.getElementById("next-page");
  if (prev) {
    prev.disabled = state.page <= 1;
  }
  if (next) {
    next.disabled = state.page >= pageCount;
  }
}

function renderSummary() {
  const metadata = state.metadata || {};
  setTime("sync-time", (state.health || {}).checked_at || metadata.last_published_at || metadata.generated_at);
  const sourceDate = document.getElementById("source-date");
  if (sourceDate) {
    const raw = (metadata.source || {}).markdown_date || null;
    sourceDate.textContent = formatDate(raw);
    if (raw) {
      sourceDate.setAttribute("datetime", String(raw));
    } else {
      sourceDate.removeAttribute("datetime");
    }
  }
}

function renderFilters() {
  const statusFilter = requireElement("status-filter");
  const versionFilter = requireElement("version-filter");
  const versions = [...new Set(state.records.map((record) => record.application_version))].sort(
    compareVersions
  );
  for (const status of ["On-Going", "Completed", "Canceled"]) {
    statusFilter.append(el("option", { value: status, text: status }));
  }
  for (const version of versions) {
    versionFilter.append(el("option", { value: version, text: version }));
  }
}

function renderRegions() {
  const select = requireElement("region-select");
  const result = requireElement("region-result");
  const regions = state.regions.filter((row) => row.is_region);
  const unique = [...new Set(regions.map((row) => row.region))].sort((a, b) =>
    a.localeCompare(b)
  );
  for (const region of unique) {
    select.append(el("option", { value: region, text: region }));
  }
  select.addEventListener("change", () => {
    const match = regions.find((row) => row.region === select.value);
    if (!match) {
      state.activeStation = null;
      result.textContent = "Select a region to see its station.";
      renderRows();
      return;
    }
    const peers = regions
      .filter((row) => row.station === match.station)
      .map((row) => row.region)
      .sort((a, b) => a.localeCompare(b));
    state.activeStation = match.station;
    result.textContent = `${match.region} is covered by Station ${match.station}. Also in Station ${match.station}: ${peers.join(", ")}. Expanded trains show only this station.`;
    renderRows();
  });
}

function resetAllFilters() {
  state.activeStation = null;
  document.getElementById("search").value = "";
  document.getElementById("status-filter").value = "";
  document.getElementById("version-filter").value = "";
  document.getElementById("region-select").value = "";
  document.getElementById("page-size").value = "20";
  state.sort = { key: null, direction: 1 };
  state.page = 1;
  state.pageSize = 20;
  setText("region-result", "Select a region to see its station.");
  renderRows();
}

function renderQuality() {
  const statusBar = document.querySelector(".sync");
  if (statusBar) {
    statusBar.classList.remove("is-warn", "is-error");
  }
  setText("sync-label", "Dataset healthy");
}

async function load() {
  try {
    const [metadata, pqu, stations, regions, health] = await Promise.all([
      fetchJson("./api/metadata.json"),
      fetchJson("./api/pqu.json"),
      fetchJson("./api/stations.json"),
      fetchJson("./api/regions.json"),
      fetchJson("./api/health.json")
    ]);
    state.metadata = metadata;
    state.records = pqu.records || [];
    state.stations = stations.records || [];
    state.regions = regions.records || [];
    state.health = health;
    renderSummary();
    renderFilters();
    renderRows();
    renderRegions();
    renderQuality();
  } catch (error) {
    showLoadError(error);
  }
}



function wireControls() {
  applyTheme(currentTheme(), false);
  const themeToggle = requireElement("theme-toggle");
  themeToggle.addEventListener("click", () => {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  });
  requireElement("search").addEventListener("input", () => {
    state.page = 1;
    renderRows();
  });
  for (const id of ["status-filter", "version-filter"]) {
    const control = requireElement(id);
    control.addEventListener("input", () => {
      state.page = 1;
      renderRows();
    });
    control.addEventListener("change", () => {
      state.page = 1;
      renderRows();
    });
  }
  requireElement("page-size").addEventListener("change", (event) => {
    state.pageSize = Number(event.target.value) || 20;
    state.page = 1;
    renderRows();
  });
  requireElement("reset-filters").addEventListener("click", resetAllFilters);
  document.querySelectorAll("#pqu-table .th-sort").forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.dataset.sort;
      if (state.sort.key !== key) {
        state.sort = { key, direction: 1 };
      } else {
        state.sort.direction = state.sort.direction === 1 ? -1 : 1;
      }
      state.page = 1;
      renderRows();
    });
  });
  requireElement("prev-page").addEventListener("click", () => {
    state.page = Math.max(1, state.page - 1);
    renderRows();
  });
  requireElement("next-page").addEventListener("click", () => {
    state.page += 1;
    renderRows();
  });
}

try {
  wireControls();
  void load();
} catch (error) {
  showLoadError(error);
}
