/* Application shell: loads published documents, renders the tab bar and the active view. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  const { el } = PQU.ui.dom;
  const dates = PQU.dates;
  const router = PQU.router;

  const ASSET_VERSION = "__ASSET_VERSION__";
  const APP_TITLE = "D365 PQU Tracker";
  const DOCUMENTS = {
    metadata: "./api/metadata.json",
    pqu: "./api/pqu.json",
    stations: "./api/stations.json",
    regions: "./api/regions.json",
    health: "./api/health.json",
    quality: "./api/quality-report.json",
    learn: "./api/learn.json",
    service_updates: "./api/service-updates.json",
    maintenance: "./api/maintenance-windows.json",
    insights: "./api/insights.json",
    events: "./api/events.json",
    changes: "./api/changes.json",
    index: "./api/index.json"
  };
  const SHELL_DOCUMENTS = ["metadata", "pqu", "health", "quality"];
  /* Show loading placeholders only when documents take longer than this to arrive. */
  const SKELETON_DELAY_MS = 150;
  const MINUTE_MS = 60000;
  /* Tabs in display order; only views that are registered are shown. */
  const NAV = [
    { name: "overview", label: "Overview" },
    { name: "region", label: "My region" },
    { name: "trains", label: "Trains" },
    { name: "versions", label: "Versions" },
    { name: "learn", label: "Learn" },
    { name: "changes", label: "Changes" }
  ];
  /* Routes that belong to a tab (for aria-current) and fallbacks while a view is unavailable. */
  const SECTION_OF = { train: "trains" };
  const FALLBACK = { overview: "trains" };

  const state = {
    docs: {},
    errors: {},
    pending: {},
    route: null,
    renderToken: 0,
    lastHash: {},
    // Documents from an older dataset are discarded when a refresh replaces the dataset.
    generation: 0,
    lastRefresh: 0,
    refreshing: false,
    renderedToday: null,
    nextChange: null,
    tickTimer: null
  };

  async function fetchJson(path) {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`${path} returned ${response.status}`);
    }
    return response.json();
  }

  /* Load documents once; failures are recorded per document instead of failing the page. */
  async function need(names) {
    await Promise.allSettled(
      names.map((name) => {
        if (!DOCUMENTS[name] || state.docs[name] || state.errors[name]) {
          return Promise.resolve();
        }
        if (!state.pending[name]) {
          const generation = state.generation;
          const pending = state.pending;
          pending[name] = fetchJson(DOCUMENTS[name])
            .then((document) => {
              if (generation === state.generation) {
                state.docs[name] = document;
              }
            })
            .catch((error) => {
              if (generation === state.generation) {
                state.errors[name] = error;
              }
            })
            .finally(() => {
              delete pending[name];
            });
        }
        return state.pending[name];
      })
    );
  }

  function records() {
    return (state.docs.pqu || {}).records || [];
  }

  function stations() {
    return (state.docs.stations || {}).records || [];
  }

  function recordsById() {
    const byId = {};
    for (const record of records()) {
      byId[record.pqu_id] = record;
    }
    return byId;
  }

  function stationsByTrain() {
    const byTrain = {};
    for (const row of stations()) {
      (byTrain[row.pqu_id] = byTrain[row.pqu_id] || []).push(row);
    }
    for (const list of Object.values(byTrain)) {
      list.sort((a, b) => a.station - b.station);
    }
    return byTrain;
  }

  function showLoadError(error) {
    const banner = document.getElementById("load-error");
    if (banner) {
      banner.hidden = false;
      banner.textContent = `The dataset could not be loaded: ${error.message} (assets ${ASSET_VERSION})`;
    }
  }

  function trainHref(pquId) {
    return PQU.ui.common.trainHref(pquId);
  }

  function renderHealth() {
    const zone = PQU.ui.zone.get().zone;
    return PQU.ui.health.render({
      health: state.docs.health,
      metadata: state.docs.metadata,
      quality: state.docs.quality,
      errors: state.errors,
      now: Date.now(),
      zone,
      locale: PQU.ui.zone.locale(),
      recordsById: recordsById(),
      trainHref
    });
  }

  function renderFooter() {
    const metadata = state.docs.metadata || {};
    const sourceDate = document.getElementById("source-date");
    if (sourceDate) {
      const raw = (metadata.source || {}).markdown_date || null;
      sourceDate.textContent = dates.formatDate(raw);
      if (raw) {
        sourceDate.setAttribute("datetime", String(raw));
      }
    }
  }

  function context() {
    const zone = PQU.ui.zone.get().zone;
    const locale = PQU.ui.zone.locale();
    const todayIso = dates.todayIn(zone);
    const metadata = state.docs.metadata || {};
    const markdownDate = (metadata.source || {}).markdown_date || null;
    const byTrain = stationsByTrain();
    const phases = new Map();
    for (const record of records()) {
      phases.set(
        record.pqu_id,
        PQU.phase.compute(record, byTrain[record.pqu_id] || [], todayIso, { markdownDate })
      );
    }
    const zoneName = dates.displayZone(zone);
    return {
      metadata: state.docs.metadata,
      records: records(),
      stations: stations(),
      stationsByTrain: byTrain,
      regions: (state.docs.regions || {}).records || [],
      learn: state.docs.learn || null,
      serviceUpdates: state.docs.service_updates || null,
      maintenance: state.docs.maintenance || null,
      insights: state.docs.insights || null,
      events: state.docs.events || null,
      changes: state.docs.changes || null,
      index: state.docs.index || null,
      quality: (state.docs.quality || {}).records || [],
      health: state.docs.health || null,
      errors: state.errors,
      flags: PQU.health.flagsByTrain(state.docs.quality),
      recordsById: recordsById(),
      phases,
      zone,
      zoneName,
      locale,
      now: Date.now(),
      todayIso,
      todayLabel: dates.formatDate(todayIso, { weekday: true }),
      todayLong: dates.formatDate(todayIso, { weekday: true, long: true }),
      lastHash: { ...state.lastHash },
      caption:
        "Proactive quality update trains. Dates are Microsoft's published calendar dates; " +
        `status lines are calculated for today, ${dates.formatDate(todayIso, { weekday: true })}, ` +
        `in ${zoneName}.`
    };
  }

  function resolveView(route) {
    let name = route.name;
    if (!PQU.views[name] && FALLBACK[name]) {
      name = FALLBACK[name];
    }
    return PQU.views[name] && name !== "notFound" ? PQU.views[name] : PQU.views.notFound;
  }

  function renderNav(view) {
    const nav = document.getElementById("tabs");
    if (!nav) {
      return;
    }
    const current = SECTION_OF[view.name] || view.name;
    const links = NAV.filter((item) => PQU.views[item.name]).map((item) => {
      const href = router.href(item.name);
      const exact = item.name === view.name;
      const inSection = item.name === current;
      return el("a", {
        class: "tab",
        href,
        "aria-current": exact ? "page" : inSection ? "true" : null,
        text: item.label
      });
    });
    nav.replaceChildren(...links);
    // Data & API lives in the footer rather than the tab bar.
    const dataLink = document.getElementById("data-link");
    if (dataLink) {
      if (view.name === "data") {
        dataLink.setAttribute("aria-current", "page");
      } else {
        dataLink.removeAttribute("aria-current");
      }
    }
  }

  /* After a render: a deep-link target (data-focus-target) wins; otherwise, when navigating,
   * focus the view heading and return to the top. Jumps are instant: a long animated scroll
   * after a navigation reads as lag. */
  function focusView(container, navigating) {
    const target = container.querySelector("[data-focus-target]");
    if (target) {
      target.focus({ preventScroll: true });
      target.scrollIntoView({ block: "start", behavior: "instant" });
      return;
    }
    if (!navigating) {
      return;
    }
    const heading = container.querySelector("[data-view-heading]");
    if (heading) {
      heading.focus({ preventScroll: true });
    }
    root.scrollTo({ top: 0, behavior: "instant" });
  }

  function setTitle(viewTitle) {
    document.title = `${viewTitle} · ${APP_TITLE}`;
  }

  /* Keep the rendered-hash marker in step when a view rewrites the URL in place. */
  function replaceHash(hash) {
    try {
      root.history.replaceState(root.history.state, "", hash);
    } catch (error) {
      /* Browsers throttle rapid history updates; the view keeps working without the URL. */
    }
    const container = document.getElementById("view");
    if (container) {
      container.dataset.renderedHash = root.location.hash;
    }
  }

  async function renderRoute({ focus = false, preserve = false } = {}) {
    const token = ++state.renderToken;
    const route = router.parse(root.location.hash);
    const view = resolveView(route);
    const container = document.getElementById("view");
    const missing = (view.documents || []).some(
      (name) => DOCUMENTS[name] && !state.docs[name] && !state.errors[name]
    );
    const skeletonTimer =
      missing && !preserve
        ? root.setTimeout(() => {
            if (token === state.renderToken) {
              showSkeleton(container);
            }
          }, SKELETON_DELAY_MS)
        : null;
    await need(view.documents || []);
    root.clearTimeout(skeletonTimer);
    if (token !== state.renderToken) {
      return;
    }
    const snapshot = preserve ? capture(container) : null;
    state.route = route;
    const ctx = context();
    view.render(container, ctx, route);
    container.removeAttribute("aria-busy");
    container.dataset.route = view.name;
    container.dataset.renderedHash = root.location.hash;
    state.lastHash[SECTION_OF[view.name] || view.name] = root.location.hash || "#/";
    state.renderedToday = ctx.todayIso;
    state.nextChange = typeof view.nextChange === "function" ? view.nextChange(ctx) : null;
    setTitle(view.title(route, ctx));
    renderNav(view);
    renderHealth();
    if (snapshot) {
      restore(container, snapshot);
    } else {
      focusView(container, focus);
    }
  }

  /* ---- Loading placeholders ---- */

  function showSkeleton(container) {
    container.setAttribute("aria-busy", "true");
    container.replaceChildren(
      el("div", { class: "skeleton", "aria-hidden": "true" }, [
        el("span", { class: "skeleton-line skeleton-title" }),
        el("span", { class: "skeleton-line" }),
        el("span", { class: "skeleton-line skeleton-short" })
      ]),
      el("p", { class: "visually-hidden", text: "Loading the dataset…" })
    );
  }

  /* ---- Keeping the reader's place when a view is redrawn in place ---- */

  function pathTo(node, container) {
    const path = [];
    let current = node;
    while (current && current !== container) {
      const parent = current.parentElement;
      if (!parent) {
        return null;
      }
      path.unshift(Array.prototype.indexOf.call(parent.children, current));
      current = parent;
    }
    return current === container ? path : null;
  }

  function nodeAt(path, container) {
    let current = container;
    for (const index of path || []) {
      current = current ? current.children[index] : null;
    }
    return current && current !== container ? current : null;
  }

  function capture(container) {
    const active = document.activeElement;
    const inside = Boolean(active && active !== container && container.contains(active));
    return {
      scrollY: root.scrollY,
      open: [...container.querySelectorAll("details[open][id]")].map((node) => node.id),
      focus: inside
        ? {
            id: active.id || null,
            path: pathTo(active, container),
            tag: active.tagName,
            text: (active.textContent || "").trim(),
            selection:
              typeof active.selectionStart === "number" ? [active.selectionStart, active.selectionEnd] : null
          }
        : null
    };
  }

  function restore(container, snapshot) {
    for (const id of snapshot.open) {
      const details = document.getElementById(id);
      if (details && details.tagName === "DETAILS" && !details.open && container.contains(details)) {
        details.dataset.restoring = "true";
        details.open = true;
      }
    }
    const focus = snapshot.focus;
    if (focus) {
      let target = focus.id ? document.getElementById(focus.id) : null;
      if (!target) {
        const candidate = nodeAt(focus.path, container);
        if (candidate && candidate.tagName === focus.tag && (candidate.textContent || "").trim() === focus.text) {
          target = candidate;
        }
      }
      if (!target || !container.contains(target)) {
        target = container.querySelector("[data-view-heading]");
      }
      if (target) {
        target.focus({ preventScroll: true });
        if (focus.selection && target.id && target.id === focus.id && typeof target.setSelectionRange === "function") {
          try {
            target.setSelectionRange(focus.selection[0], focus.selection[1]);
          } catch (error) {
            /* Not a text field; focus alone is kept. */
          }
        }
      }
    }
    root.scrollTo({ top: snapshot.scrollY, behavior: "instant" });
  }

  /* A <details> reopened by restore() fires one "toggle" event later; views skip that one. */
  function isRestoring(details) {
    if (details && details.dataset && details.dataset.restoring) {
      delete details.dataset.restoring;
      return true;
    }
    return false;
  }

  function announce(message) {
    const node = document.getElementById("app-status");
    if (node) {
      node.textContent = message;
    }
  }

  /* ---- Keeping the data and the clock current ---- */

  function checkIntervalMs() {
    const minutes =
      (state.docs.metadata || {}).check_interval_minutes || (state.docs.health || {}).check_interval_minutes;
    return Number.isFinite(minutes) && minutes > 0 ? minutes * MINUTE_MS : null;
  }

  /* Look for a newer published dataset. Whatever fails, the loaded data stays on screen. */
  async function refresh() {
    if (state.refreshing) {
      return;
    }
    state.refreshing = true;
    state.lastRefresh = Date.now();
    try {
      const metadata = await fetchJson(DOCUMENTS.metadata);
      const health = await fetchJson(DOCUMENTS.health).catch(() => null);
      if (metadata.generated_at === (state.docs.metadata || {}).generated_at) {
        if (health) {
          state.docs.health = health;
          delete state.errors.health;
        }
        renderHealth();
        return;
      }
      const names = [...new Set([...Object.keys(state.docs), ...Object.keys(state.errors)])].filter(
        (name) => DOCUMENTS[name] && name !== "metadata" && name !== "health"
      );
      const docs = { metadata };
      const errors = {};
      if (health) {
        docs.health = health;
      } else {
        errors.health = new Error(`${DOCUMENTS.health} could not be loaded`);
      }
      await Promise.allSettled(
        names.map((name) =>
          fetchJson(DOCUMENTS[name]).then(
            (document) => {
              docs[name] = document;
            },
            (error) => {
              errors[name] = error;
            }
          )
        )
      );
      // One build writes every document with the same generated_at; a mix means the site was
      // being deployed while it was read. Keep the current data and try again next time.
      if (!docs.pqu || docs.pqu.generated_at !== metadata.generated_at) {
        return;
      }
      state.generation += 1;
      state.pending = {};
      state.docs = docs;
      state.errors = errors;
      renderFooter();
      await renderRoute({ preserve: true });
      const zone = PQU.ui.zone.get().zone;
      announce(
        `Updated with the data published ${dates.formatDateTime(metadata.generated_at, zone, {
          locale: PQU.ui.zone.locale()
        })}.`
      );
    } catch (error) {
      /* Offline or mid-deployment: keep the loaded data and try again at the next check. */
    } finally {
      state.refreshing = false;
    }
  }

  /* Every minute and when the page becomes visible: relative times, the date in the chosen time
   * zone, instants a view depends on (maintenance windows starting or ending), and new data. */
  function check(now = Date.now()) {
    renderHealth();
    const zone = PQU.ui.zone.get().zone;
    const today = dates.todayIn(zone, now);
    const dayChanged = state.renderedToday !== null && today !== state.renderedToday;
    const clockChanged = state.nextChange !== null && now >= state.nextChange;
    if (dayChanged || clockChanged) {
      renderRoute({ preserve: true })
        .then(() => {
          if (dayChanged) {
            announce(`Dates and countdowns recalculated for ${dates.formatDate(today, { weekday: true })}.`);
          }
        })
        .catch(showLoadError);
    }
    const interval = checkIntervalMs();
    if (document.visibilityState === "visible" && interval !== null && now - state.lastRefresh >= interval) {
      refresh();
    }
  }

  function scheduleTick() {
    root.clearTimeout(state.tickTimer);
    const now = Date.now();
    // Just after the next minute boundary, so minute-based text changes on time.
    state.tickTimer = root.setTimeout(() => {
      scheduleTick();
      check();
    }, MINUTE_MS - (now % MINUTE_MS) + 20);
  }

  /* The skip link's "#main" would be read as a route; move focus without changing the address. */
  function wireSkipLink() {
    const link = document.querySelector(".skip-link");
    const main = document.getElementById("main");
    if (!link || !main) {
      return;
    }
    link.addEventListener("click", (event) => {
      event.preventDefault();
      main.focus({ preventScroll: true });
      main.scrollIntoView({ block: "start", behavior: "instant" });
    });
  }

  async function start() {
    PQU.ui.theme.wireTheme();
    wireSkipLink();
    PQU.ui.zone.renderPicker(() => {
      renderRoute().catch(showLoadError);
    });
    const container = document.getElementById("view");
    showSkeleton(container);
    await need(SHELL_DOCUMENTS);
    state.lastRefresh = Date.now();
    renderHealth();
    if (state.errors.pqu || state.errors.metadata) {
      container.replaceChildren();
      container.removeAttribute("aria-busy");
      showLoadError(state.errors.pqu || state.errors.metadata);
      document.body.dataset.ready = "true";
      return;
    }
    renderFooter();
    root.addEventListener("hashchange", () => {
      renderRoute({ focus: true }).catch(showLoadError);
    });
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        check();
      }
    });
    await renderRoute();
    document.body.dataset.ready = "true";
    scheduleTick();
  }

  PQU.app = {
    ASSET_VERSION,
    DOCUMENTS,
    NAV,
    announce,
    check,
    isRestoring,
    need,
    refresh,
    renderHealth,
    replaceHash,
    setTitle,
    showLoadError,
    start,
    state,
    trainHref
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
