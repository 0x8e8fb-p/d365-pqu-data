"use strict";

const TIME_ZONE = "Asia/Kolkata";
const TIME_ZONE_LABEL = "IST";
const THEME_KEY = "d365-pqu-theme";
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
  quality: null,
  health: null,
  sort: { key: null, direction: 1 },
  page: 1,
  pageSize: 20,
  stationPqu: "",
  stationQuery: ""
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

function statusClass(status) {
  return (
    "badge " +
    String(status).toLowerCase().replace(/[^a-z]+/g, "-").replace(/(^-|-$)/g, "")
  );
}

function statusCell(status) {
  return el("td", {}, [el("span", { class: statusClass(status), text: status })]);
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

function filteredRecords() {
  const search = (document.getElementById("search").value || "").trim().toLowerCase();
  const status = document.getElementById("status-filter").value;
  const version = document.getElementById("version-filter").value;
  const matches = state.records.filter((record) => {
    if (status && record.status !== status) {
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
      record.uep_version
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
    const row = el("tr", {}, [
      textCell(record.pqu_id, true),
      textCell(record.application_version, true),
      textCell(record.pqu_train, true),
      statusCell(record.status),
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
    fragment.append(row);
  }
  body.append(fragment);
  updateSortIndicators();
  const first = records.length === 0 ? 0 : start + 1;
  const last = Math.min(start + state.pageSize, records.length);
  setText("filter-note", `${records.length} of ${state.records.length} trains shown`);
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

function filteredStations() {
  const query = (document.getElementById("station-search").value || "").trim().toLowerCase();
  return state.stations.filter((row) => {
    if (state.stationPqu && row.pqu_id !== state.stationPqu) {
      return false;
    }
    if (!query) {
      return true;
    }
    const haystack = [
      row.pqu_id,
      row.station_label,
      `station ${row.station}`,
      row.sandbox_start_date,
      row.sandbox_end_date,
      row.production_start_date,
      row.production_end_date
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(query);
  });
}

function renderStationFilters() {
  const select = document.getElementById("station-pqu-filter");
  if (select.options.length <= 1 && state.stations.length > 0) {
    const trains = [...new Map(state.stations.map((row) => [row.pqu_id, row])).values()].sort(
      (a, b) =>
        compareVersions(a.application_version, b.application_version) ||
        a.release_number - b.release_number
    );
    for (const train of trains) {
      select.append(el("option", { value: train.pqu_id, text: train.pqu_id }));
    }
  }
  select.value = state.stationPqu;
}

function renderStations() {
  renderStationFilters();
  const body = document.querySelector("#station-table tbody");
  const rows = filteredStations().sort((a, b) => {
    const version = compareVersions(a.application_version, b.application_version);
    return version !== 0 ? version : a.release_number - b.release_number || a.station - b.station;
  });
  body.replaceChildren();
  const fragment = document.createDocumentFragment();
  for (const row of rows) {
    fragment.append(
      el("tr", {}, [
        textCell(row.pqu_id, true),
        textCell(row.station_label, true),
        textCell(
          row.sandbox_start_date
            ? `${formatDate(row.sandbox_start_date)} to ${formatDate(row.sandbox_end_date)}`
            : "N/A"
        ),
        textCell(
          row.production_start_date
            ? `${formatDate(row.production_start_date)} to ${formatDate(row.production_end_date)}`
            : "N/A"
        )
      ])
    );
  }
  body.append(fragment);
  setText("station-note", `${rows.length} of ${state.stations.length} station windows shown`);
}

function renderSummary() {
  const metadata = state.metadata || {};
  const current = state.records.filter((record) => record.status === "In-Progress");
  const upcoming = state.records.filter((record) => record.status === "Not Started");
  const latest = state.records.find((record) => record.pqu_id === metadata.latest_pqu_id) || null;
  const sortedUpcoming = [...upcoming].sort((a, b) => {
    const aDate = a.train_start_date || "9999-12-31";
    const bDate = b.train_start_date || "9999-12-31";
    if (aDate !== bDate) {
      return aDate.localeCompare(bDate);
    }
    return (
      compareVersions(a.application_version, b.application_version) ||
      a.release_number - b.release_number
    );
  });
  const next = sortedUpcoming[0] || null;

  setText("latest-pqu", latest ? latest.pqu_id : "None");
  setText(
    "latest-pqu-note",
    latest
      ? `${latest.application_build || "Build pending"} · ${latest.platform_build || "Platform pending"}`
      : "No active train in the published schedule"
  );
  setText("current-count", String(current.length));
  setText("next-pqu", next ? next.pqu_id : "None");
  setText(
    "next-pqu-note",
    next ? `Cutoff ${formatDate(next.change_cutoff_date)}` : "No upcoming train published"
  );
  setText("record-count", String(state.records.length));
  setText(
    "record-note",
    `${current.length} active · ${upcoming.length} upcoming · ${metadata.station_schedule_count || state.stations.length} station rows`
  );
  setText(
    "overview-note",
    `Last synchronized ${formatTimestamp(metadata.last_published_at || metadata.generated_at)}`
  );
  setTime("sync-time", (state.health || {}).checked_at || metadata.last_published_at || metadata.generated_at);
  setText("source-date", formatDate(metadata.source ? metadata.source.markdown_date : null));
  setText("source-synced", formatTimestamp(metadata.generated_at));
  setText("source-hash", metadata.source ? metadata.source.sha256 : null);
  setText("source-commit", metadata.source ? metadata.source.commit : null);
  const sourceLink = document.getElementById("source-link");
  if (sourceLink && metadata.source) {
    sourceLink.textContent = "Microsoft Learn";
    sourceLink.href = metadata.source.article_url;
  }
}

function renderFilters() {
  const statusFilter = document.getElementById("status-filter");
  const versionFilter = document.getElementById("version-filter");
  const statuses = [...new Set(state.records.map((record) => record.status))];
  const versions = [...new Set(state.records.map((record) => record.application_version))].sort(
    compareVersions
  );
  for (const status of statuses) {
    statusFilter.append(el("option", { value: status, text: status }));
  }
  for (const version of versions) {
    versionFilter.append(el("option", { value: version, text: version }));
  }
}

function renderRegions() {
  const select = document.getElementById("region-select");
  const result = document.getElementById("region-result");
  const showStation = document.getElementById("show-station");
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
      result.textContent = "Select a region to see its station.";
      showStation.hidden = true;
      return;
    }
    const peers = regions
      .filter((row) => row.station === match.station)
      .map((row) => row.region)
      .sort((a, b) => a.localeCompare(b));
    result.textContent = `${match.region} is covered by Station ${match.station}. Also in Station ${match.station}: ${peers.join(", ")}.`;
    showStation.hidden = false;
    showStation.onclick = () => {
      state.stationPqu = "";
      state.stationQuery = `Station ${match.station}`;
      const stationSelect = document.getElementById("station-pqu-filter");
      const stationSearch = document.getElementById("station-search");
      if (stationSelect) {
        stationSelect.value = "";
      }
      if (stationSearch) {
        stationSearch.value = state.stationQuery;
      }
      renderStations();
      document.getElementById("stations-heading").scrollIntoView({ block: "start" });
    };
  });
}

function renderQuality() {
  const statusBar = document.querySelector(".sync");
  const quality = state.quality;
  const warnings = quality && Array.isArray(quality.records) ? quality.records : [];
  const fatal = warnings.filter((item) => item.severity === "error");
  if (statusBar) {
    statusBar.classList.remove("is-warn", "is-error");
  }
  if (fatal.length > 0) {
    if (statusBar) {
      statusBar.classList.add("is-error");
    }
    setText("sync-label", `Dataset has ${fatal.length} validation issue(s)`);
    return;
  }
  if (warnings.length > 0) {
    if (statusBar) {
      statusBar.classList.add("is-warn");
    }
    setText("sync-label", `Healthy with ${warnings.length} warning(s)`);
    const block = document.getElementById("quality-block");
    const list = document.getElementById("quality-list");
    block.hidden = false;
    list.replaceChildren();
    for (const item of warnings) {
      const prefix = item.pqu_id ? `${item.pqu_id}: ` : "";
      list.append(el("li", { text: `${prefix}${item.message}` }));
    }
    return;
  }
  setText("sync-label", "Dataset healthy");
}

async function load() {
  try {
    const [metadata, pqu, stations, regions, quality, health] = await Promise.all([
      fetchJson("./api/metadata.json"),
      fetchJson("./api/pqu.json"),
      fetchJson("./api/stations.json"),
      fetchJson("./api/regions.json"),
      fetchJson("./api/quality-report.json"),
      fetchJson("./api/health.json")
    ]);
    state.metadata = metadata;
    state.records = pqu.records || [];
    state.stations = stations.records || [];
    state.regions = regions.records || [];
    state.quality = quality;
    state.health = health;
    renderSummary();
    renderFilters();
    renderRows();
    renderStations();
    renderRegions();
    renderQuality();
  } catch (error) {
    const banner = document.getElementById("load-error");
    banner.hidden = false;
    banner.textContent = `The dataset could not be loaded: ${error.message}`;
    setText("sync-label", "Dataset unavailable");
    setTime("sync-time", null);
  }
}

function resetSchedule() {
  document.getElementById("search").value = "";
  document.getElementById("status-filter").value = "";
  document.getElementById("version-filter").value = "";
  document.getElementById("page-size").value = "20";
  state.sort = { key: null, direction: 1 };
  state.page = 1;
  state.pageSize = 20;
  renderRows();
}

function resetStations() {
  state.stationPqu = "";
  state.stationQuery = "";
  const select = document.getElementById("station-pqu-filter");
  const search = document.getElementById("station-search");
  if (select) {
    select.value = "";
  }
  if (search) {
    search.value = "";
  }
  renderStations();
}

function wireControls() {
  applyTheme(currentTheme(), false);
  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  }
  for (const id of ["search", "status-filter", "version-filter"]) {
    const control = document.getElementById(id);
    control.addEventListener("input", () => {
      state.page = 1;
      renderRows();
    });
    control.addEventListener("change", () => {
      state.page = 1;
      renderRows();
    });
  }
  document.getElementById("page-size").addEventListener("change", (event) => {
    state.pageSize = Number(event.target.value) || 20;
    state.page = 1;
    renderRows();
  });
  document.getElementById("reset-filters").addEventListener("click", resetSchedule);
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
  document.getElementById("prev-page").addEventListener("click", () => {
    state.page = Math.max(1, state.page - 1);
    renderRows();
  });
  document.getElementById("next-page").addEventListener("click", () => {
    state.page += 1;
    renderRows();
  });
  document.getElementById("station-pqu-filter").addEventListener("change", (event) => {
    state.stationPqu = event.target.value;
    renderStations();
  });
  document.getElementById("station-search").addEventListener("input", (event) => {
    state.stationQuery = event.target.value;
    renderStations();
  });
  document.getElementById("reset-stations").addEventListener("click", resetStations);
}

wireControls();
load();
