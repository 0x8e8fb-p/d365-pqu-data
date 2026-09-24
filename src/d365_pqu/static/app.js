"use strict";

const state = {
  records: [],
  stations: [],
  regions: [],
  metadata: null,
  quality: null,
  health: null,
  apiIndex: null,
};

function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") {
      node.className = value;
    } else if (key === "text") {
      node.textContent = value;
    } else if (key === "href") {
      node.href = value;
    } else if (key === "hidden") {
      node.hidden = Boolean(value);
    } else {
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
    node.textContent = value === null || value === undefined || value === "" ? "-" : String(value);
  }
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const parts = String(value).split("-");
  if (parts.length !== 3) {
    return String(value);
  }
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const monthIndex = Number(parts[1]) - 1;
  if (monthIndex < 0 || monthIndex > 11) {
    return String(value);
  }
  return `${Number(parts[2])} ${months[monthIndex]} ${parts[0]}`;
}

function formatTimestamp(value) {
  if (!value) {
    return "-";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toISOString().replace("T", " ").replace(".000Z", " UTC");
}

function statusClass(status) {
  return "badge " + String(status).toLowerCase().replace(/[^a-z]+/g, "-").replace(/(^-|-$)/g, "");
}

function statusCell(status) {
  return el("td", {}, [el("span", { class: statusClass(status), text: status })]);
}

function textCell(value, mono = false) {
  return el("td", { class: mono ? "mono" : "", text: value === null || value === undefined || value === "" ? "-" : String(value) });
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
    return compareVersions(a.application_version, b.application_version) || a.release_number - b.release_number;
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
    next ? `Change cutoff ${formatDate(next.change_cutoff_date)}` : "No upcoming train published"
  );
  setText("record-count", String(state.records.length));
  setText(
    "record-note",
    `${current.length} active · ${upcoming.length} upcoming · ${metadata.station_schedule_count || state.stations.length} station rows`
  );
  setText("sync-time", formatTimestamp(metadata.last_published_at || metadata.generated_at));
  setText("source-date", metadata.source ? metadata.source.markdown_date : null);
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
  const versions = [...new Set(state.records.map((record) => record.application_version))].sort(compareVersions);
  for (const status of statuses) {
    statusFilter.append(el("option", { value: status, text: status }));
  }
  for (const version of versions) {
    versionFilter.append(el("option", { value: version, text: version }));
  }
}

function filteredRecords() {
  const search = (document.getElementById("search").value || "").trim().toLowerCase();
  const status = document.getElementById("status-filter").value;
  const version = document.getElementById("version-filter").value;
  return state.records.filter((record) => {
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
      record.uep_version,
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(search);
  });
}

function renderRows() {
  const body = document.querySelector("#pqu-table tbody");
  const records = filteredRecords();
  body.replaceChildren();
  const fragment = document.createDocumentFragment();
  for (const record of records) {
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
      textCell(record.station_schedule_available ? "Published" : "Not published"),
    ]);
    if (record.pqu_id === (state.metadata || {}).latest_pqu_id) {
      row.classList.add("latest-row");
      row.style.fontWeight = "600";
    }
    fragment.append(row);
  }
  body.append(fragment);
  setText("filter-note", `${records.length} of ${state.records.length} records shown`);
}

function renderStations() {
  const body = document.querySelector("#station-table tbody");
  body.replaceChildren();
  const fragment = document.createDocumentFragment();
  const sorted = [...state.stations].sort((a, b) => {
    const version = compareVersions(a.application_version, b.application_version);
    return version !== 0 ? version : a.release_number - b.release_number || a.station - b.station;
  });
  for (const row of sorted) {
    fragment.append(
      el("tr", {}, [
        textCell(row.pqu_id, true),
        textCell(row.station_label, true),
        textCell(
          row.sandbox_start_date ? `${formatDate(row.sandbox_start_date)} to ${formatDate(row.sandbox_end_date)}` : "N/A"
        ),
        textCell(
          row.production_start_date
            ? `${formatDate(row.production_start_date)} to ${formatDate(row.production_end_date)}`
            : "N/A"
        ),
      ])
    );
  }
  body.append(fragment);
}

function renderRegions() {
  const select = document.getElementById("region-select");
  const result = document.getElementById("region-result");
  const regions = state.regions.filter((row) => row.is_region);
  const unique = [...new Set(regions.map((row) => row.region))].sort((a, b) => a.localeCompare(b));
  for (const region of unique) {
    select.append(el("option", { value: region, text: region }));
  }
  select.addEventListener("change", () => {
    const match = regions.find((row) => row.region === select.value);
    if (!match) {
      result.textContent = "Select a region to see its station.";
      return;
    }
    const peers = regions
      .filter((row) => row.station === match.station)
      .map((row) => row.region)
      .sort((a, b) => a.localeCompare(b));
    result.textContent = `${match.region} is covered by Station ${match.station}. Other regions in that station: ${peers.join(", ")}.`;
  });
}

function renderEndpoints() {
  const list = document.getElementById("endpoint-list");
  const index = state.apiIndex;
  if (!index || !Array.isArray(index.endpoints)) {
    return;
  }
  list.replaceChildren();
  for (const endpoint of index.endpoints) {
    const jsonPath = "./api/" + String(endpoint.path).replace(/^\.\//, "");
    const children = [
      el("strong", { text: endpoint.name }),
      el("p", { text: endpoint.description }),
      el("code", {}, [el("a", { href: jsonPath, text: jsonPath })]),
    ];
    if (endpoint.csv) {
      const csvPath = "./api/" + String(endpoint.csv).replace(/^\.\//, "");
      children.push(el("p", {}, [el("code", {}, [el("a", { href: csvPath, text: csvPath })])]));
    }
    list.append(el("li", {}, children));
  }
}

function renderQuality() {
  const quality = state.quality;
  const statusBar = document.querySelector(".status-bar");
  const warnings = quality && Array.isArray(quality.records) ? quality.records : [];
  const fatal = warnings.filter((item) => item.severity === "error");
  if (fatal.length > 0) {
    statusBar.classList.add("is-error");
    setText("sync-state", `Dataset has ${fatal.length} fatal validation issue(s)`);
    return;
  }
  if (warnings.length > 0) {
    statusBar.classList.add("is-warn");
    setText("sync-state", `Dataset healthy with ${warnings.length} source warning(s)`);
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
  setText("sync-state", "Dataset healthy");
}

async function load() {
  try {
    const [index, metadata, pqu, stations, regions, quality, health] = await Promise.all([
      fetchJson("./api/index.json"),
      fetchJson("./api/metadata.json"),
      fetchJson("./api/pqu.json"),
      fetchJson("./api/stations.json"),
      fetchJson("./api/regions.json"),
      fetchJson("./api/quality-report.json"),
      fetchJson("./api/health.json"),
    ]);
    state.apiIndex = index;
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
    renderEndpoints();
    renderQuality();
  } catch (error) {
    const banner = document.getElementById("load-error");
    banner.hidden = false;
    banner.textContent = `The dataset could not be loaded: ${error.message}`;
    setText("sync-state", "Dataset unavailable");
  }
}

function wireFilters() {
  for (const id of ["search", "status-filter", "version-filter"]) {
    document.getElementById(id).addEventListener("input", renderRows);
    document.getElementById(id).addEventListener("change", renderRows);
  }
  document.getElementById("reset-filters").addEventListener("click", () => {
    document.getElementById("search").value = "";
    document.getElementById("status-filter").value = "";
    document.getElementById("version-filter").value = "";
    renderRows();
  });
}

wireFilters();
load();
