/* Changes view (#/changes): what differed between published copies of Microsoft's articles,
 * newest first, grouped by day in the viewer's time zone. The pipeline records the history; this
 * view only words, filters and groups it. Filters live in the URL (?kind=pqu&q=PQU-6). */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.views = PQU.views || {};
  const { el, extLink, visuallyHidden } = PQU.ui.dom;
  const dates = PQU.dates;
  const text = PQU.text;
  const changes = PQU.changes;
  const common = PQU.ui.common;

  const DAYS_PER_PAGE = 14;
  const SEARCH_SYNC_DELAY = 300;
  const MAX_SEARCH_LENGTH = 200;
  const KIND_ORDER = ["pqu", "station", "service_update", "maintenance_window", "region", "guidance"];

  const view = { kind: "", search: "", shownDays: DAYS_PER_PAGE, appliedHash: null };
  let ctx = null;
  let nodes = {};
  let days = [];
  let syncTimer = null;

  function sourceEntry(key) {
    return (((ctx.metadata || {}).sources || {})[key]) || null;
  }

  function sourceLabel(key) {
    const entry = sourceEntry(key);
    return entry && entry.label ? entry.label : null;
  }

  function commitUrl(commit) {
    const repository = ((ctx.metadata || {}).source || {}).repository;
    if (!repository || !/^[\w.-]+\/[\w.-]+$/.test(repository) || !/^[0-9a-f]{7,40}$/i.test(String(commit || ""))) {
      return null;
    }
    return `https://github.com/${repository}/commit/${commit}`;
  }

  /* Every display line, grouped by day and by check; built once per render. */
  function prepare(records) {
    return changes.byDay(records, ctx.zone).map((day) => ({
      day: day.day,
      syncs: day.syncs.map((sync) => ({
        changed_at: sync.changed_at,
        commits: changes.commitsOf(sync.changes),
        lines: changes.lines(sync.changes, { sourceLabel })
      }))
    }));
  }

  function allLines(list) {
    return list.flatMap((day) => day.syncs.flatMap((sync) => sync.lines));
  }

  function matches(line) {
    if (view.kind && line.entity !== view.kind) {
      return false;
    }
    const query = text.normalizeSearch(view.search);
    if (!query) {
      return true;
    }
    return text.normalizeSearch([line.subject, line.text, line.pquId, line.field].join(" ")).includes(query);
  }

  function filtered() {
    return days
      .map((day) => ({
        day: day.day,
        syncs: day.syncs
          .map((sync) => ({ ...sync, lines: sync.lines.filter(matches) }))
          .filter((sync) => sync.lines.length)
      }))
      .filter((day) => day.syncs.length);
  }

  /* ---- URL ---- */

  function query() {
    return { kind: view.kind || null, q: view.search || null };
  }

  function syncUrl(delay = 0) {
    root.clearTimeout(syncTimer);
    const write = () => {
      PQU.app.replaceHash(PQU.router.href("changes", {}, query()));
      view.appliedHash = root.location.hash;
    };
    if (delay > 0) {
      syncTimer = root.setTimeout(write, delay);
    } else {
      write();
    }
  }

  function applyRoute(route) {
    if (root.location.hash === view.appliedHash) {
      return;
    }
    const input = (route && route.query) || {};
    view.kind = Object.prototype.hasOwnProperty.call(changes.ENTITY_LABELS, input.kind) ? input.kind : "";
    view.search = typeof input.q === "string" ? input.q.slice(0, MAX_SEARCH_LENGTH) : "";
    view.shownDays = DAYS_PER_PAGE;
    view.appliedHash = root.location.hash;
  }

  /* ---- Rendering ---- */

  function summaryText() {
    const metadata = ctx.metadata || {};
    const since = metadata.first_published_at
      ? dates.formatDateTime(metadata.first_published_at, ctx.zone, { locale: ctx.locale })
      : null;
    const total = allLines(days).length;
    const checks = days.reduce((count, day) => count + day.syncs.length, 0);
    const start = since ? ` since tracking began on ${since}` : "";
    if (!total) {
      return `No changes detected${start}.`;
    }
    return `${text.plural(total, "change")} found in ${text.plural(checks, "check")}${start}.`;
  }

  function methodText() {
    const interval = PQU.health.formatInterval((ctx.metadata || {}).check_interval_minutes);
    return (
      (interval ? `Microsoft's articles are checked ${interval}. ` : "") +
      "A change is listed when a published value differs from the previous published copy. " +
      `Times are shown in ${ctx.zoneName}.`
    );
  }

  function kindOptions() {
    const counts = {};
    for (const line of allLines(days)) {
      counts[line.entity] = (counts[line.entity] || 0) + 1;
    }
    const kinds = [
      ...KIND_ORDER.filter((kind) => counts[kind] || kind === view.kind),
      ...Object.keys(counts)
        .filter((kind) => !KIND_ORDER.includes(kind))
        .sort()
    ];
    const total = Object.values(counts).reduce((sum, count) => sum + count, 0);
    return [
      { value: "", label: `All changes (${total})` },
      ...kinds.map((kind) => ({
        value: kind,
        label: `${changes.ENTITY_LABELS[kind] || kind} (${counts[kind] || 0})`
      }))
    ];
  }

  function filters() {
    const select = el(
      "select",
      {
        id: "changes-kind",
        on: {
          change: (event) => {
            view.kind = event.target.value;
            view.shownDays = DAYS_PER_PAGE;
            renderList();
            syncUrl();
          }
        }
      },
      kindOptions().map((option) =>
        el("option", { value: option.value, text: option.label, selected: option.value === view.kind })
      )
    );
    const search = el("input", {
      id: "changes-search",
      type: "search",
      autocomplete: "off",
      placeholder: "Train, version, region, or text",
      value: view.search,
      on: {
        input: (event) => {
          view.search = event.target.value.slice(0, MAX_SEARCH_LENGTH);
          view.shownDays = DAYS_PER_PAGE;
          renderList();
          syncUrl(SEARCH_SYNC_DELAY);
        }
      }
    });
    nodes.kind = select;
    nodes.search = search;
    return el("div", { class: "changes-filters", role: "search", "aria-label": "Filter changes" }, [
      el("label", { class: "field" }, [el("span", { text: "What changed" }), select]),
      el("label", { class: "field field-search" }, [el("span", { text: "Search" }), search])
    ]);
  }

  function resetFilters() {
    view.kind = "";
    view.search = "";
    view.shownDays = DAYS_PER_PAGE;
    nodes.kind.value = "";
    nodes.search.value = "";
    renderList();
    syncUrl();
    nodes.kind.focus();
  }

  function subjectLink(line) {
    if (line.entity === "guidance") {
      const entry = sourceEntry(changes.keyedField(line.field).name);
      return entry && entry.article_url
        ? extLink(entry.article_url, line.subject, { class: "change-subject-link" })
        : el("span", { class: "change-subject-link", text: line.subject });
    }
    if (line.href && line.href.startsWith("#/")) {
      return el("a", { class: "change-subject-link", href: line.href, text: line.subject });
    }
    return el("span", { class: "change-subject-link", text: line.subject });
  }

  /* Lines of one check, grouped by what they are about (a train, a version, an article, …). */
  function subjects(lines) {
    const groups = [];
    const index = new Map();
    for (const line of lines) {
      const family = line.entity === "station" ? "pqu" : line.entity;
      const key = `${family}|${line.subject}`;
      if (!index.has(key)) {
        const group = { key, first: line, lines: [] };
        index.set(key, group);
        groups.push(group);
      }
      index.get(key).lines.push(line);
    }
    return groups;
  }

  function lineItem(line) {
    const learnMore =
      line.entity === "guidance" && line.type !== "removed" && line.href && /^https:\/\//i.test(line.href)
        ? [" · ", extLink(line.href, "Read on Microsoft Learn")]
        : null;
    return el(
      "li",
      { class: ["change", `change-${line.type}`], dataset: { change: line.ids.join(" "), entity: line.entity } },
      [line.text, learnMore]
    );
  }

  function syncItem(sync) {
    const time = `${dates.formatTime(sync.changed_at, ctx.zone)} ${dates.zoneLabel(ctx.zone, sync.changed_at, ctx.locale)}`;
    const commits = sync.commits
      .map((commit) => ({ commit, url: commitUrl(commit) }))
      .filter((item) => item.url)
      .flatMap((item) => [" · ", extLink(item.url, `Microsoft commit ${item.commit.slice(0, 7)}`)]);
    return el("li", { class: "change-group", dataset: { changedAt: sync.changed_at } }, [
      el("p", { class: "change-when" }, [el("time", { datetime: sync.changed_at, text: time }), ...commits]),
      el(
        "ul",
        { class: "change-subjects" },
        subjects(sync.lines).map((group) =>
          el("li", { class: "change-subject", dataset: { subject: group.first.subject } }, [
            subjectLink(group.first),
            el("ul", { class: "change-lines" }, group.lines.map(lineItem))
          ])
        )
      )
    ]);
  }

  function dayItem(day) {
    const offset = dates.diffDays(ctx.todayIso, day.day);
    const relative = offset === null ? "" : dates.daysPhrase(offset);
    const headingId = `changes-day-${day.day}`;
    return el("li", { class: "change-day", dataset: { day: day.day } }, [
      el("h2", { class: "change-day-title", id: headingId, tabindex: "-1" }, [
        el("time", { datetime: day.day, text: dates.formatDate(day.day, { weekday: true }) }),
        relative ? el("span", { class: "muted calc", text: ` · ${relative}` }) : null
      ]),
      el("ol", { class: "change-groups" }, day.syncs.map(syncItem))
    ]);
  }

  function renderList(focusDay = null) {
    const shown = filtered();
    const total = allLines(days).length;
    const matching = allLines(shown).length;
    const active = Boolean(view.kind || text.normalizeSearch(view.search));
    nodes.status.textContent = active ? `${text.plural(matching, "change")} of ${total} match.` : "";
    const children = [];
    if (!total) {
      // The summary above already says that nothing has changed since tracking began.
    } else if (!shown.length) {
      children.push(
        el("p", { class: "changes-empty", id: "changes-none" }, [
          "No changes match these filters. ",
          el("button", { class: "link-button", type: "button", text: "Show all changes", on: { click: resetFilters } })
        ])
      );
    } else {
      const visible = shown.slice(0, view.shownDays);
      children.push(el("ol", { class: "change-days", id: "change-days" }, visible.map(dayItem)));
      const hidden = shown.slice(view.shownDays);
      if (hidden.length) {
        const remaining = allLines(hidden).length;
        children.push(
          el("button", {
            class: "button small changes-more",
            type: "button",
            id: "changes-more",
            text: `Show older changes (${text.plural(remaining, "more change")})`,
            on: {
              click: () => {
                const next = hidden[0].day;
                view.shownDays += DAYS_PER_PAGE;
                renderList(next);
              }
            }
          })
        );
      }
    }
    nodes.list.replaceChildren(...children);
    if (focusDay) {
      const heading = nodes.list.querySelector(`[data-day="${focusDay}"] .change-day-title`);
      if (heading) {
        heading.focus();
      }
    }
  }

  function render(container, context, route) {
    ctx = context;
    applyRoute(route);
    nodes = {};
    const doc = ctx.changes;
    const failed = ctx.errors.changes || !doc || !Array.isArray(doc.records);
    days = failed ? [] : prepare(doc.records);
    const feed = [
      el("a", { class: "feed-link", href: "./feed.xml", type: "application/atom+xml", text: "Atom feed" }),
      visuallyHidden(" of these changes")
    ];
    if (failed) {
      container.replaceChildren(
        el("div", { class: "page changes" }, [
          common.pageHead({ id: "changes-heading", title: "Changes in Microsoft's articles", aside: feed }),
          el("p", { class: "inline-alert", id: "changes-error", text: "The change history could not be loaded." })
        ])
      );
      return;
    }
    nodes.status = el("p", { class: "changes-status", id: "changes-status", role: "status", "aria-live": "polite" });
    nodes.list = el("div", { class: "changes-list", id: "changes-list" });
    const total = allLines(days).length;
    container.replaceChildren(
      el("div", { class: "page changes" }, [
        common.pageHead({
          id: "changes-heading",
          title: "Changes in Microsoft's articles",
          sub: [
            el("p", { id: "changes-summary", text: summaryText() }),
            el("p", { class: "changes-method note", text: methodText() })
          ],
          aside: feed
        }),
        total ? filters() : null,
        nodes.status,
        nodes.list
      ])
    );
    renderList();
  }

  PQU.views.changes = {
    name: "changes",
    label: "Changes",
    documents: ["changes"],
    title: () => "Changes",
    render,
    state: view
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
