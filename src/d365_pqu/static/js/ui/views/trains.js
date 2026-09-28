/* Trains view: filter rail, sortable paged table, and expandable station windows.
 * The view state (filters, sort, page) lives in the URL so every view can be shared. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.views = PQU.views || {};
  const { el, setText } = PQU.ui.dom;
  const dates = PQU.dates;
  const records = PQU.records;
  const versions = PQU.versions;

  const COLUMNS = [
    { key: "pqu_id", label: "PQU ID" },
    { key: "application_version", label: "App version" },
    { key: "pqu_train", label: "Train", optional: true },
    { key: "status", label: "Status" },
    { key: "change_cutoff_date", label: "Cutoff" },
    { key: "train_start_date", label: "Start" },
    { key: "train_end_date", label: "End" },
    { key: "application_build", label: "App build" },
    { key: "platform_build", label: "Platform build" },
    { key: "uep_version", label: "UEP", optional: true },
    { key: "station_schedule_available", label: "Stations" }
  ];
  const SORT_KEYS = new Set(COLUMNS.map((column) => column.key));
  const PAGE_SIZES = [10, 20, 50];
  const DEFAULT_PAGE_SIZE = 20;
  const SEARCH_SYNC_DELAY = 300;
  const DISPLAY_OPTIONS = [
    { id: "table", label: "Table" },
    { id: "timeline", label: "Timeline" }
  ];
  const TITLES = { table: "PQU trains", timeline: "PQU train timeline" };

  const view = {
    search: "",
    status: "",
    version: "",
    region: "",
    activeStation: null,
    pageSize: DEFAULT_PAGE_SIZE,
    page: 1,
    sort: { key: null, direction: 1 },
    display: "table",
    zoom: PQU.timeline.DEFAULT_ZOOM,
    expanded: [],
    appliedHash: null
  };
  let ctx = null;
  let nodes = {};
  let syncTimer = null;
  const common = PQU.ui.common;

  function textCell(value, mono = false) {
    return el("td", {
      class: mono ? "mono" : null,
      text: value === null || value === undefined || value === "" ? "—" : String(value)
    });
  }

  function statusCell(record) {
    const cell = el("td", { class: "status-cell" }, [common.statusBadge(record.status)]);
    if (records.isDueSoon(record, ctx.todayIso)) {
      cell.append(el("span", { class: "due", text: "Due soon" }));
    }
    const phase = ctx.phases.get(record.pqu_id);
    const line = phase ? [phase.text, phase.detail].filter(Boolean).join(" · ") : "";
    if (line) {
      cell.append(
        el("span", { class: "phase" }, [PQU.ui.dom.visuallyHidden("Calculated from published dates: "), line])
      );
    }
    if (phase && phase.conflict) {
      cell.append(el("span", { class: "phase-note", text: phase.conflict }));
    }
    if (record.status_note) {
      cell.append(
        el("span", { class: "status-note" }, [
          el("span", { class: "status-note-label", text: "Microsoft note: " }),
          record.status_note
        ])
      );
    }
    return cell;
  }

  function stationsCell(record) {
    if (!record.station_schedule_available) {
      return el("td", { class: "muted", text: "Not published" });
    }
    return el("td", {}, ["Published", common.newChip(record)]);
  }

  /* Microsoft's own description of the table and its callouts, from learn.json. */
  function scheduleGuidance() {
    const rich = PQU.ui.rich;
    const article = rich.article(ctx.learn, "schedule");
    if (!article) {
      return ctx.errors.learn
        ? el("p", { class: "inline-alert", text: "Microsoft's schedule notes could not be loaded." })
        : null;
    }
    const children = [];
    const { before } = PQU.ui.guidance.datasetContext(article, "trains");
    const intro = before.filter((block) => block.type === "paragraph");
    if (intro.length) {
      children.push(el("div", { class: "source-note", id: "train-table-note" }, rich.blocks(intro)));
    }
    const callouts = rich.callouts(article).map(({ block }) => block);
    const panel = PQU.ui.guidance.panel({
      id: "rules-panel",
      title: "Microsoft's rollout rules",
      article,
      blocks: callouts,
      summaryNote: `${callouts.length} ${callouts.length === 1 ? "note" : "notes"}`
    });
    if (panel) {
      children.push(panel);
    }
    return children.length ? el("div", { class: "guidance" }, children) : null;
  }

  function stationWindow(row, startKey, endKey) {
    if (!row[startKey]) {
      return "N/A";
    }
    return `${dates.formatDate(row[startKey])} to ${dates.formatDate(row[endKey])}`;
  }

  function stationDetailRow(record) {
    const detailId = `stations-${record.pqu_id}`;
    const title =
      view.activeStation === null
        ? `Station windows · ${record.pqu_id}`
        : `Station ${view.activeStation} window · ${record.pqu_id}`;
    const body = el("div", { class: "station-detail-body", id: detailId }, [
      el("p", { class: "detail-title", text: title })
    ]);
    const cell = el("td", { colspan: String(COLUMNS.length) }, [body]);
    let rows = records.stationsFor(ctx.stations, record.pqu_id);
    if (view.activeStation !== null) {
      rows = rows.filter((row) => row.station === view.activeStation);
    }
    if (rows.length === 0) {
      body.append(el("p", { class: "detail-empty", text: "No detailed station schedule published." }));
      return el("tr", { class: "station-detail" }, [cell]);
    }
    const tableBody = el("tbody");
    for (const row of rows) {
      tableBody.append(
        el("tr", { class: row.station === view.activeStation ? "station-active" : null }, [
          textCell(row.station_label, true),
          textCell(stationWindow(row, "sandbox_start_date", "sandbox_end_date")),
          textCell(stationWindow(row, "production_start_date", "production_end_date"))
        ])
      );
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

  function idCell(record, hasStations, expanded) {
    const flags = ctx.flags[record.pqu_id] || [];
    const flag = flags.length
      ? el("span", {
          class: "flag",
          role: "img",
          "aria-label": `Source warning: ${flags.map((item) => PQU.health.describe(item, ctx.recordsById)).join(" ")}`,
          title: flags.map((item) => PQU.health.describe(item, ctx.recordsById)).join("\n"),
          text: "⚑"
        })
      : null;
    const link = el("a", { class: "train-id", href: common.trainHref(record.pqu_id), text: record.pqu_id });
    if (!hasStations) {
      return el("td", { class: "mono id-cell" }, [
        el("span", { class: "row-toggle-spacer", "aria-hidden": "true" }),
        link,
        flag
      ]);
    }
    const toggle = el(
      "button",
      {
        class: "row-toggle",
        type: "button",
        "aria-expanded": expanded ? "true" : "false",
        // Only reference the station row while it exists.
        "aria-controls": expanded ? `stations-${record.pqu_id}` : null,
        "aria-label": `${expanded ? "Collapse" : "Expand"} station windows for ${record.pqu_id}`,
        on: {
          click: () => {
            view.expanded = view.expanded.includes(record.pqu_id)
              ? view.expanded.filter((id) => id !== record.pqu_id)
              : [...view.expanded, record.pqu_id];
            renderRows();
          }
        }
      },
      [el("span", { class: "row-toggle-icon", "aria-hidden": "true", text: expanded ? "−" : "+" })]
    );
    return el("td", { class: "mono id-cell" }, [toggle, link, flag]);
  }

  function filtered() {
    const matches = records.filterRecords(
      ctx.records,
      { search: view.search, status: view.status, version: view.version },
      (record) =>
        [
          records.isDueSoon(record, ctx.todayIso) ? "due soon" : "",
          PQU.phase.searchText(ctx.phases.get(record.pqu_id))
        ].join(" ")
    );
    return records.sortRecords(matches, view.sort);
  }

  function updateSortIndicators() {
    for (const button of nodes.table.querySelectorAll(".th-sort")) {
      const header = button.closest("th");
      if (button.dataset.sort === view.sort.key) {
        header.setAttribute("aria-sort", view.sort.direction === 1 ? "ascending" : "descending");
      } else {
        header.setAttribute("aria-sort", "none");
      }
    }
  }

  function renderRows() {
    const list = filtered();
    const pageData = records.paginate(list, view.page, view.pageSize);
    view.page = pageData.page;
    const fragment = document.createDocumentFragment();
    for (const record of pageData.items) {
      const hasStations = records.stationsFor(ctx.stations, record.pqu_id).length > 0;
      const expanded = hasStations && view.expanded.includes(record.pqu_id);
      const row = el(
        "tr",
        {
          class: [
            record.pqu_id === (ctx.metadata || {}).latest_pqu_id ? "latest" : null,
            records.isDueSoon(record, ctx.todayIso) ? "due-soon" : null,
            ctx.flags[record.pqu_id] ? "has-flag" : null
          ]
        },
        [
          idCell(record, hasStations, expanded),
          textCell(record.application_version, true),
          el("td", { class: "mono col-optional", text: record.pqu_train || "—" }),
          statusCell(record),
          textCell(dates.formatDate(record.change_cutoff_date)),
          textCell(dates.formatDate(record.train_start_date)),
          textCell(dates.formatDate(record.train_end_date)),
          textCell(record.application_build, true),
          textCell(record.platform_build, true),
          el("td", { class: "mono col-optional", text: record.uep_version || "—" }),
          stationsCell(record)
        ]
      );
      fragment.append(row);
      if (expanded) {
        fragment.append(stationDetailRow(record));
      }
    }
    nodes.tbody.replaceChildren(fragment);
    updateSortIndicators();
    const dueCount = list.filter((record) => records.isDueSoon(record, ctx.todayIso)).length;
    setText(
      nodes.filterNote,
      `${list.length} of ${ctx.records.length} trains shown` +
        (dueCount > 0 ? ` · ${dueCount} due soon` : "") +
        (view.activeStation !== null ? ` · Station ${view.activeStation} context` : "")
    );
    setText(
      nodes.pageInfo,
      `Page ${pageData.page} of ${pageData.pageCount} · ${pageData.first}–${pageData.last} of ${pageData.total}`
    );
    nodes.prev.disabled = pageData.page <= 1;
    nodes.next.disabled = pageData.page >= pageData.pageCount;
  }

  /* Write the view state into the URL without adding a history entry. */
  function syncUrl(delay = 0) {
    root.clearTimeout(syncTimer);
    const write = () => {
      const hash = PQU.router.href(
        "trains",
        {},
        records.trainsQuery(view, DEFAULT_PAGE_SIZE, PQU.timeline.DEFAULT_ZOOM)
      );
      if (root.location.hash !== hash) {
        try {
          root.history.replaceState(root.history.state, "", hash);
        } catch (error) {
          /* Browsers throttle rapid history updates; the next change writes the URL again. */
        }
      }
      view.appliedHash = root.location.hash;
      if (nodes.container && nodes.container.isConnected) {
        nodes.container.dataset.renderedHash = root.location.hash;
      }
    };
    if (delay > 0) {
      syncTimer = root.setTimeout(write, delay);
    } else {
      write();
    }
  }

  function update(changes, delay = 0) {
    Object.assign(view, changes);
    renderResults();
    syncUrl(delay);
  }

  /* ---- Timeline ---- */

  function renderTimeline() {
    const list = filtered();
    const layout = PQU.timeline.layout(list, {
      zoom: view.zoom,
      todayIso: ctx.todayIso,
      unreliable: PQU.health.unreliableDates({ records: ctx.quality })
    });
    nodes.panel.replaceChildren(
      PQU.ui.timeline.render(ctx, list, layout, { onZoom: (zoom) => setZoom(zoom, true) })
    );
    setText(
      nodes.filterNote,
      `${list.length} of ${ctx.records.length} trains match · ${layout.drawn} on the timeline`
    );
  }

  function renderResults() {
    if (view.display === "timeline") {
      renderTimeline();
    } else {
      renderRows();
    }
  }

  function pressed(buttons, current) {
    for (const [id, button] of Object.entries(buttons)) {
      button.setAttribute("aria-pressed", id === current ? "true" : "false");
    }
  }

  /* Show the table or the timeline in place; the pressed toggle keeps focus. */
  function showDisplay() {
    const timeline = view.display === "timeline";
    pressed(nodes.displayButtons, view.display);
    nodes.zoomGroup.hidden = !timeline;
    nodes.tableCalc.hidden = timeline;
    if (nodes.pageSizeField) {
      nodes.pageSizeField.hidden = timeline;
    }
    if (timeline) {
      renderTimeline();
    } else {
      nodes.panel.replaceChildren(buildTable());
      renderRows();
    }
  }

  function setDisplay(display) {
    if (display === view.display) {
      return;
    }
    view.display = display;
    showDisplay();
    syncUrl();
    PQU.app.setTitle(TITLES[display]);
  }

  function setZoom(zoom, focusButton = false) {
    view.zoom = zoom;
    pressed(nodes.zoomButtons, zoom);
    renderTimeline();
    syncUrl();
    if (focusButton && nodes.zoomButtons[zoom]) {
      nodes.zoomButtons[zoom].focus();
    }
  }

  function segmented(id, label, options, current, onPick) {
    const buttons = {};
    const group = el(
      "div",
      { class: "segmented", role: "group", "aria-label": label, id },
      options.map((option) => {
        buttons[option.id] = el("button", {
          type: "button",
          id: `${id}-${option.id}`,
          "aria-pressed": option.id === current ? "true" : "false",
          text: option.label,
          on: { click: () => onPick(option.id) }
        });
        return buttons[option.id];
      })
    );
    return { group, buttons };
  }

  function toolbar() {
    const display = segmented("display", "Show trains as", DISPLAY_OPTIONS, view.display, setDisplay);
    const zoom = segmented("zoom", "Timeline range", PQU.timeline.ZOOMS, view.zoom, (value) =>
      setZoom(value)
    );
    nodes.displayButtons = display.buttons;
    nodes.zoomButtons = zoom.buttons;
    nodes.zoomGroup = zoom.group;
    return el("div", { class: "view-toolbar" }, [display.group, zoom.group]);
  }

  function regionRecords() {
    return ctx.regions.filter((row) => row.is_region);
  }

  function regionResultContent() {
    const match = regionRecords().find((row) => row.region === view.region);
    if (!match) {
      return ["Select a region to see its station."];
    }
    const peers = regionRecords()
      .filter((row) => row.station === match.station && row.region !== match.region)
      .map((row) => row.region)
      .sort((a, b) => a.localeCompare(b));
    return [
      `${match.region} is covered by Station ${match.station}.` +
        (peers.length ? ` Also in Station ${match.station}: ${peers.join(", ")}.` : "") +
        " Expanded trains show only this station. ",
      el("a", {
        href: PQU.router.href("region", { region: match.region }),
        text: `Open ${match.region} in My region`
      })
    ];
  }

  function applyRegion(region) {
    const match = regionRecords().find((row) => row.region === region);
    view.region = match ? match.region : "";
    view.activeStation = match ? match.station : null;
    if (nodes.regionResult) {
      nodes.regionResult.replaceChildren(...regionResultContent());
    }
  }

  function selectField(id, label, options, value, onChange) {
    const select = el(
      "select",
      { id, on: { change: (event) => onChange(event.target.value) } },
      options.map((option) =>
        el("option", { value: option.value, text: option.label, selected: option.value === value })
      )
    );
    return el("label", { class: "field" }, [el("span", { text: label }), select]);
  }

  function statusChoices() {
    return records
      .statusOptions(ctx.records)
      .map((option) => ({ value: option.value, label: `${option.label} (${option.count})` }));
  }

  function versionChoices() {
    return versions
      .uniqueSortedVersions(ctx.records.map((record) => record.application_version))
      .map((version) => ({ value: version, label: version }));
  }

  function buildRail() {
    const regionOptions = [...new Set(regionRecords().map((row) => row.region))]
      .sort((a, b) => a.localeCompare(b))
      .map((region) => ({ value: region, label: region }));
    const search = el("input", {
      id: "search",
      type: "search",
      placeholder: "PQU, version, build, or status",
      autocomplete: "off",
      value: view.search,
      on: {
        input: (event) => update({ search: event.target.value, page: 1 }, SEARCH_SYNC_DELAY)
      }
    });
    nodes.regionResult = el(
      "p",
      { id: "region-result", "aria-live": "polite" },
      regionResultContent()
    );
    const reset = el("button", {
      id: "reset-filters",
      class: "button small rail-button",
      type: "button",
      text: "Reset all filters",
      on: { click: resetAll }
    });
    return el("aside", { class: "filters-rail", "aria-labelledby": "filters-heading" }, [
      el("h2", { id: "filters-heading", text: "Filters" }),
      el("fieldset", { class: "filter-group", "aria-label": "Refine dashboard results" }, [
        el("legend", { text: "Refine" }),
        el("label", { class: "field field-search" }, [el("span", { text: "Search" }), search]),
        selectField(
          "status-filter",
          "Status",
          [{ value: "", label: `All statuses (${ctx.records.length})` }, ...statusChoices()],
          view.status,
          (value) => update({ status: value, page: 1 })
        ),
        selectField(
          "version-filter",
          "Application version",
          [{ value: "", label: "All versions" }, ...versionChoices()],
          view.version,
          (value) => update({ version: value, page: 1 })
        ),
        selectField(
          "region-select",
          "Region",
          [{ value: "", label: "Select a region" }, ...regionOptions],
          view.region,
          (value) => {
            applyRegion(value);
            PQU.ui.prefs.write("region", view.region || null);
            update({});
          }
        ),
        el("div", { class: "lookup-result" }, [nodes.regionResult]),
        (nodes.pageSizeField = selectField(
          "page-size",
          "Rows",
          PAGE_SIZES.map((size) => ({ value: String(size), label: String(size) })),
          String(view.pageSize),
          (value) => update({ pageSize: Number(value) || DEFAULT_PAGE_SIZE, page: 1 })
        )),
        reset
      ])
    ]);
  }

  function buildTable() {
    const headerCells = COLUMNS.map((column) =>
      el("th", { scope: "col", class: column.optional ? "col-optional" : null, "aria-sort": "none" }, [
        el(
          "button",
          {
            type: "button",
            class: "th-sort",
            dataset: { sort: column.key },
            on: {
              click: () => {
                const direction =
                  view.sort.key === column.key && view.sort.direction === 1 ? -1 : 1;
                update({ sort: { key: column.key, direction }, page: 1 });
              }
            }
          },
          [`${column.label} `, el("span", { class: "sort-indicator", "aria-hidden": "true" })]
        )
      ])
    );
    nodes.tbody = el("tbody");
    nodes.table = el("table", { id: "pqu-table" }, [
      el("caption", { class: "visually-hidden", text: ctx.caption }),
      el("thead", {}, [el("tr", {}, headerCells)]),
      nodes.tbody
    ]);
    nodes.pageInfo = el("p", { id: "page-info", "aria-live": "polite" });
    nodes.prev = el("button", {
      id: "prev-page",
      class: "button small",
      type: "button",
      text: "Previous",
      on: { click: () => update({ page: Math.max(1, view.page - 1) }) }
    });
    nodes.next = el("button", {
      id: "next-page",
      class: "button small",
      type: "button",
      text: "Next",
      on: { click: () => update({ page: view.page + 1 }) }
    });
    return el("div", { class: "table-panel" }, [
      el("div", { class: "table-scroll" }, [nodes.table]),
      el("div", { class: "pager" }, [
        nodes.pageInfo,
        el("div", { class: "pager-actions" }, [nodes.prev, nodes.next])
      ])
    ]);
  }

  function resetAll() {
    Object.assign(view, {
      search: "",
      status: "",
      version: "",
      region: "",
      activeStation: null,
      pageSize: DEFAULT_PAGE_SIZE,
      page: 1,
      sort: { key: null, direction: 1 }
    });
    PQU.ui.prefs.write("region", null);
    syncUrl();
    build();
  }

  /*
   * Apply URL parameters when the URL differs from what this view last wrote or applied.
   * Without a region parameter, the region saved in My region applies. Returns true when the
   * URL should be rewritten to show the applied state.
   */
  function applyRoute(route) {
    if (!route || route.name !== "trains") {
      return false;
    }
    const regions = new Set(regionRecords().map((row) => row.region));
    if (root.location.hash !== view.appliedHash) {
      const state = records.parseTrainsQuery(route.query, {
        statuses: new Set(records.statusOptions(ctx.records).map((option) => option.value)),
        versions: new Set(ctx.records.map((record) => record.application_version)),
        regions,
        sortKeys: SORT_KEYS,
        pageSizes: PAGE_SIZES,
        defaultPageSize: DEFAULT_PAGE_SIZE,
        zooms: PQU.timeline.ZOOMS.map((zoom) => zoom.id),
        defaultZoom: PQU.timeline.DEFAULT_ZOOM
      });
      Object.assign(view, state);
    }
    let rewrite = false;
    if (!route.query.region) {
      const saved = PQU.ui.prefs.read("region");
      const wanted = saved && regions.has(saved) ? saved : "";
      if (wanted && view.region !== wanted) {
        view.region = wanted;
        rewrite = true;
      }
    }
    applyRegion(view.region);
    view.appliedHash = root.location.hash;
    return rewrite;
  }

  function build() {
    const container = nodes.container;
    nodes = { container };
    nodes.filterNote = el("p", { class: "section-note", id: "filter-note", "aria-live": "polite" });
    const notices = [];
    if (ctx.errors.stations) {
      notices.push("Station schedules could not be loaded; station windows are unavailable.");
    }
    if (ctx.errors.regions) {
      notices.push("The region mapping could not be loaded; region lookup is unavailable.");
    }
    const main = el("div", { class: "workspace-main" }, [
      el("section", { class: "section", "aria-labelledby": "schedule-heading" }, [
        el("div", { class: "section-head" }, [
          el("div", {}, [
            el("p", { class: "kicker", text: "Schedule" }),
            el("h2", {
              id: "schedule-heading",
              tabindex: "-1",
              dataset: { viewHeading: "" },
              text: "PQU trains"
            })
          ]),
          nodes.filterNote
        ]),
        scheduleGuidance(),
        (nodes.tableCalc = el("p", { class: "calc-note", id: "calc-note" }, [
          el("span", { class: "calc-mark", "aria-hidden": "true", text: "↳" }),
          ` Lines under a status are calculated from Microsoft's published dates for ${ctx.todayLabel} (${ctx.zoneName}).`
        ])),
        notices.map((notice) => el("p", { class: "inline-alert", text: notice })),
        toolbar(),
        (nodes.panel = el("div", { class: "results", id: "results" }))
      ])
    ]);
    container.replaceChildren(el("div", { class: "workspace" }, [buildRail(), main]));
    showDisplay();
  }

  function render(container, context, route) {
    ctx = context;
    nodes = { container };
    const rewrite = applyRoute(route);
    applyRegion(view.region);
    build();
    if (rewrite) {
      syncUrl();
    }
  }

  PQU.views.trains = {
    name: "trains",
    label: "Trains",
    documents: ["stations", "regions", "learn"],
    title: (route) => TITLES[route && route.query && route.query.view === "timeline" ? "timeline" : "table"],
    render,
    state: view
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
