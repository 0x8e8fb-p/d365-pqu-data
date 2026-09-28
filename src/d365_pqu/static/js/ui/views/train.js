/* Train view (#/train/<id>): one PQU train in full. Dates, builds and status are Microsoft's;
 * the phase line, day counts, build position and chart geometry are calculated. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.views = PQU.views || {};
  const { el, extLink, visuallyHidden } = PQU.ui.dom;
  const dates = PQU.dates;
  const text = PQU.text;
  const windows = PQU.windows;
  const common = PQU.ui.common;

  const KINDS = [
    { key: "sandbox", label: "Sandbox" },
    { key: "production", label: "Production" }
  ];

  function findRecord(ctx, id) {
    const wanted = String(id || "")
      .trim()
      .replace(/\s+/g, "-")
      .toLowerCase();
    return ctx.records.find((record) => record.pqu_id.toLowerCase() === wanted) || null;
  }

  function yearNeeded(iso, todayIso) {
    return String(iso || "").slice(0, 4) !== String(todayIso).slice(0, 4);
  }

  function rangeText(startIso, endIso, todayIso) {
    return dates.formatDateRange(startIso, endIso, { weekday: true, year: yearNeeded(startIso, todayIso) });
  }

  function eventUrl(ctx, id) {
    const list = ctx.events && Array.isArray(ctx.events.records) ? ctx.events.records : [];
    const match = list.find((event) => event.id === id);
    return match ? match.url : null;
  }

  function commitUrl(ctx, commit) {
    const repository = ((ctx.metadata || {}).source || {}).repository;
    if (!repository || !/^[0-9a-f]{7,40}$/i.test(String(commit || ""))) {
      return null;
    }
    return `https://github.com/${repository}/commit/${commit}`;
  }

  function savedRegion(ctx) {
    const name = PQU.ui.prefs.read("region");
    return ctx.regions.find((row) => row.is_region && row.region === name) || null;
  }

  function fact(label, value, note) {
    return el("div", {}, [
      el("dt", { text: label }),
      el("dd", {}, [value, note ? [" ", el("span", { class: "fact-note", text: note })] : null])
    ]);
  }

  /* ---- Header ---- */

  function siblings(ctx, record) {
    const list = ctx.records
      .filter((item) => item.application_version === record.application_version)
      .sort((a, b) => a.release_number - b.release_number);
    const index = list.findIndex((item) => item.pqu_id === record.pqu_id);
    const previous = index > 0 ? list[index - 1] : null;
    const next = index >= 0 && index < list.length - 1 ? list[index + 1] : null;
    if (!previous && !next) {
      return null;
    }
    return el("nav", { class: "train-siblings", "aria-label": `Other ${record.application_version} trains` }, [
      previous
        ? el("a", { href: common.trainHref(previous.pqu_id), rel: "prev" }, [
            el("span", { "aria-hidden": "true", text: "← " }),
            text.trainLabel(previous.pqu_id)
          ])
        : null,
      next
        ? el("a", { href: common.trainHref(next.pqu_id), rel: "next" }, [
            text.trainLabel(next.pqu_id),
            el("span", { "aria-hidden": "true", text: " →" })
          ])
        : null
    ]);
  }

  function header(ctx, record) {
    const back = ctx.lastHash.trains || PQU.router.href("trains");
    const latest = (ctx.metadata || {}).latest_pqu_id === record.pqu_id;
    return [
      el("p", { class: "crumbs" }, [el("a", { href: back, text: "PQU trains" }), el("span", { "aria-hidden": "true", text: " / " }), text.trainLabel(record.pqu_id)]),
      el("div", { class: "section-head train-head" }, [
        el("div", {}, [
          el("p", { class: "kicker", text: `Application version ${record.application_version} · Release ${record.release_number}` }),
          el("h2", {
            id: "train-heading",
            tabindex: "-1",
            dataset: { viewHeading: "" },
            text: text.trainLabel(record.pqu_id)
          }),
          el("p", { class: "train-badges" }, [
            visuallyHidden("Microsoft status: "),
            common.statusBadge(record.status),
            common.newChip(record),
            latest
              ? el("span", {
                  class: "chip chip-latest",
                  title: "The newest train Microsoft lists as In-Progress",
                  text: "Newest active train"
                })
              : null
          ])
        ]),
        siblings(ctx, record)
      ])
    ];
  }

  function statusLines(ctx, record) {
    const phase = ctx.phases.get(record.pqu_id);
    const line = phase ? [phase.text, phase.detail].filter(Boolean).join(" · ") : "";
    const flags = ctx.flags[record.pqu_id] || [];
    return [
      line
        ? el("p", { class: "train-phase", id: "train-phase" }, [
            el("span", { class: "calc-mark", "aria-hidden": "true", text: "↳ " }),
            visuallyHidden("Calculated from published dates: "),
            line
          ])
        : null,
      phase && phase.conflict ? el("p", { class: "phase-note", text: phase.conflict }) : null,
      record.status_note
        ? el("p", { class: "status-note", id: "train-status-note" }, [
            el("span", { class: "status-note-label", text: "Microsoft note: " }),
            record.status_note
          ])
        : null,
      flags.map((item) =>
        el("p", { class: "inline-alert train-flag" }, [
          el("span", { class: "flag", "aria-hidden": "true", text: "⚑ " }),
          `Source warning: ${PQU.health.describe(item, ctx.recordsById)}`
        ])
      )
    ];
  }

  /* ---- Facts ---- */

  function buildNote(ctx, record) {
    if (!record.application_build) {
      return null;
    }
    const position = PQU.builds.locate(ctx.records, record.application_build);
    if (position.kind !== "exact") {
      return null;
    }
    if (!position.newerCount) {
      return `Newest build published for ${record.application_version}`;
    }
    return (
      `${text.plural(position.newerCount, "newer build")} published for ${record.application_version} ` +
      `(latest ${position.latest.application_build}, ${text.trainLabel(position.latest.pqu_id)})`
    );
  }

  function versionFact(ctx, record) {
    const doc = ctx.serviceUpdates;
    if (!doc || !Array.isArray(doc.records) || (doc.state !== "current" && doc.state !== "stale")) {
      return null;
    }
    const entry = doc.records.find((item) => item.version === record.application_version);
    if (!entry) {
      return fact(`Version ${record.application_version}`, "Not in Microsoft's service update schedule");
    }
    const assessment = PQU.lifecycle.assess(entry, ctx.todayIso);
    return fact(
      `Version ${record.application_version}`,
      el("a", {
        href: PQU.router.href("versions", {}, { version: record.application_version }),
        text: assessment.label
      }),
      assessment.summary
    );
  }

  function facts(ctx, record) {
    const cutoffDays = dates.isIsoDate(record.change_cutoff_date)
      ? dates.diffDays(ctx.todayIso, record.change_cutoff_date)
      : null;
    const length =
      dates.isIsoDate(record.train_start_date) && dates.isIsoDate(record.train_end_date)
        ? dates.diffDays(record.train_start_date, record.train_end_date) + 1
        : null;
    return el("dl", { class: "stat-strip train-facts", id: "train-facts" }, [
      fact(
        "Change cutoff",
        dates.formatDate(record.change_cutoff_date, { weekday: true }),
        cutoffDays === null ? null : text.capitalize(dates.daysPhrase(cutoffDays))
      ),
      fact(
        "Train",
        rangeText(record.train_start_date, record.train_end_date, ctx.todayIso),
        length ? text.plural(length, "day") : null
      ),
      versionFact(ctx, record),
      fact(
        "Application build",
        el("span", { class: "mono", text: record.application_build || "Not published yet" }),
        buildNote(ctx, record)
      ),
      fact("Platform build", el("span", { class: "mono", text: record.platform_build || "Not published yet" })),
      fact("UEP version", el("span", { class: "mono", text: record.uep_version || "Not published" }))
    ]);
  }

  /* ---- Station rollout ---- */

  function chart(ctx, record, rows, yours) {
    const geometry = PQU.rollout.chart(rows, ctx.todayIso);
    if (!geometry) {
      return null;
    }
    const label =
      `Station rollout for ${text.trainLabel(record.pqu_id)}, ${dates.formatDateRange(geometry.start, geometry.end)}. ` +
      (geometry.today === null ? "Today is outside this range. " : `Today is ${dates.formatDate(ctx.todayIso)}. `) +
      "The table below lists every window.";
    const lanes = geometry.rows.map((row) =>
      el("div", { class: ["rollout-row", yours && yours.station === row.station ? "is-yours" : null], dataset: { station: String(row.station) } }, [
        el("span", { class: "rollout-label", text: `Station ${row.station}` }),
        el(
          "div",
          { class: "rollout-lane" },
          row.bars.map((bar) =>
            el("span", {
              class: ["rollout-bar", `bar-${bar.kind}`, `bar-${bar.state}`],
              title: `Station ${row.station} ${bar.kind}: ${dates.formatDateRange(bar.start, bar.end, { weekday: true })}`,
              vars: { "--left": `${bar.left}%`, "--width": `${bar.width}%` }
            })
          )
        )
      ])
    );
    return el("figure", { class: "rollout-chart", id: "rollout-chart" }, [
      el("div", { class: "rollout-plot", role: "img", "aria-label": label }, [
        ...geometry.ticks.map((tick) => el("span", { class: "rollout-grid", vars: { "--f": String(tick.left / 100) } })),
        ...lanes,
        el(
          "div",
          { class: "rollout-row rollout-axis" },
          [
            el("span", { class: "rollout-label" }),
            el(
              "div",
              { class: "rollout-lane" },
              geometry.ticks.map((tick) =>
                el("span", {
                  class: "rollout-tick",
                  vars: { "--left": `${tick.left}%` },
                  text: dates.formatDate(tick.iso, { year: false })
                })
              )
            )
          ]
        ),
        geometry.today === null
          ? null
          : el("span", { class: "rollout-today", vars: { "--f": String(geometry.today / 100) } })
      ]),
      el("figcaption", { class: "legend" }, [
        el("span", {}, [el("span", { class: "legend-swatch bar-sandbox", "aria-hidden": "true" }), "Sandbox"]),
        el("span", {}, [el("span", { class: "legend-swatch bar-production", "aria-hidden": "true" }), "Production"]),
        geometry.today === null
          ? null
          : el("span", {}, [el("span", { class: "legend-today", "aria-hidden": "true" }), "Today"])
      ])
    ]);
  }

  function windowCell(ctx, row, kind) {
    const startIso = row[`${kind}_start_date`];
    if (!startIso) {
      return el("td", { class: "muted", text: "N/A" });
    }
    const state = windows.rangeState(startIso, row[`${kind}_end_date`], ctx.todayIso);
    return el("td", {}, [
      el("span", { class: "window-dates", text: rangeText(startIso, row[`${kind}_end_date`], ctx.todayIso) }),
      state
        ? [" ", el("span", { class: `window-state state-${state.state}` }, [visuallyHidden("Calculated: "), state.text])]
        : null
    ]);
  }

  function regionsCell(ctx, station) {
    const rows = ctx.regions.filter((row) => row.station === station);
    const regions = rows.filter((row) => row.is_region).sort((a, b) => a.region.localeCompare(b.region));
    const notes = rows.filter((row) => !row.is_region).map((row) => row.region);
    return el("td", { class: "regions-cell" }, [
      notes.map((note) => el("span", { class: "step-note", text: note })),
      regions.length
        ? el("details", { class: "step-regions" }, [
            el("summary", { text: text.plural(regions.length, "region") }),
            el(
              "ul",
              {},
              regions.map((row) =>
                el("li", {}, [el("a", { href: PQU.router.href("region", { region: row.region }), text: row.region })])
              )
            )
          ])
        : null
    ]);
  }

  function stationRow(ctx, row, yours) {
    const mine = Boolean(yours && yours.station === row.station);
    return el("tr", { class: mine ? "is-yours" : null, dataset: { station: String(row.station) } }, [
      el("th", { scope: "row" }, [
        row.station_label || `Station ${row.station}`,
        mine ? el("span", { class: "chip chip-yours", text: "Your station" }) : null
      ]),
      ...KINDS.map((kind) => windowCell(ctx, row, kind.key)),
      regionsCell(ctx, row.station)
    ]);
  }

  function stationTable(ctx, record, rows, yours) {
    const table = el("table", { class: "station-table", id: "station-table" }, [
      el("caption", { class: "visually-hidden", text: `Station windows for ${text.trainLabel(record.pqu_id)}` }),
      el("thead", {}, [
        el("tr", {}, [
          el("th", { scope: "col", text: "Station" }),
          ...KINDS.map((kind) => el("th", { scope: "col", text: kind.label })),
          el("th", { scope: "col", text: "Regions" })
        ])
      ]),
      el(
        "tbody",
        {},
        rows.map((row) => stationRow(ctx, row, yours))
      )
    ]);
    return el("div", { class: "table-panel" }, [el("div", { class: "table-scroll" }, [table])]);
  }

  function rulesPanel(ctx) {
    const article = PQU.ui.rich.article(ctx.learn, "schedule");
    if (!article) {
      return null;
    }
    const callouts = PQU.ui.rich.callouts(article).map(({ block }) => block);
    return PQU.ui.guidance.panel({
      id: "train-rules",
      title: "Microsoft's rollout rules",
      article,
      blocks: callouts,
      summaryNote: text.plural(callouts.length, "note")
    });
  }

  function rolloutSection(ctx, record) {
    const rows = ctx.stationsByTrain[record.pqu_id] || [];
    const yours = savedRegion(ctx);
    const children = [el("h3", { id: "train-rollout-heading", text: "Station rollout" })];
    if (ctx.errors.stations) {
      children.push(el("p", { class: "inline-alert", text: "Station schedules could not be loaded." }));
    } else if (!rows.length) {
      children.push(
        el("p", {
          class: "muted",
          id: "no-stations",
          text: "Microsoft's article has no detailed station schedule for this train."
        })
      );
    } else {
      const sectionUrl = eventUrl(ctx, `sandbox_window:${record.pqu_id}:station-${rows[0].station}`);
      if (yours) {
        const row = rows.find((item) => item.station === yours.station);
        children.push(
          el("p", { class: "section-lead", id: "train-your-station" }, [
            row
              ? `${yours.region} (your region) is on Station ${yours.station}. `
              : `${yours.region} (your region) is on Station ${yours.station}, which is not in this train's schedule. `,
            el("a", { href: PQU.router.href("region", { region: yours.region }), text: `Open ${yours.region}` })
          ])
        );
      }
      children.push(
        chart(ctx, record, rows, yours),
        stationTable(ctx, record, rows, yours),
        common.calcNote(`Window states are calculated for ${ctx.todayLabel} (${ctx.zoneName}).`),
        sectionUrl
          ? el("p", { class: "source-line" }, ["Station windows from ", extLink(sectionUrl, "Microsoft's station schedule")])
          : null
      );
    }
    children.push(rulesPanel(ctx));
    return el("section", { class: "train-section", id: "train-rollout", "aria-labelledby": "train-rollout-heading" }, children);
  }

  /* ---- Changes ---- */

  function changesSection(ctx, record) {
    const children = [el("h3", { id: "train-changes-heading", text: "Changes to this train" })];
    const doc = ctx.changes;
    if (ctx.errors.changes || !doc || !Array.isArray(doc.records)) {
      children.push(el("p", { class: "inline-alert", text: "The change history could not be loaded." }));
    } else {
      const groups = PQU.changes.bySync(PQU.changes.forTrain(doc.records, record.pqu_id));
      if (!groups.length) {
        children.push(
          el("p", {
            class: "muted",
            id: "train-no-changes",
            text:
              "No changes recorded since this dataset first saw the train on " +
              `${dates.formatDateTime(record.first_seen_at, ctx.zone, { locale: ctx.locale })}.`
          })
        );
      } else {
        children.push(
          el(
            "ol",
            { class: "change-groups", id: "train-change-list" },
            groups.map((group) => {
              const commit = group.changes[0].source_commit;
              const url = commitUrl(ctx, commit);
              return el("li", { class: "change-group" }, [
                el("p", { class: "change-when" }, [
                  el("time", {
                    datetime: group.changed_at,
                    text: dates.formatDateTime(group.changed_at, ctx.zone, { locale: ctx.locale })
                  }),
                  url ? [" · ", extLink(url, `Microsoft commit ${String(commit).slice(0, 7)}`)] : null
                ]),
                el(
                  "ul",
                  {},
                  PQU.changes.lines(group.changes).map((line) =>
                    el("li", { class: `change change-${line.type}`, dataset: { change: line.ids.join(" ") } }, [line.text])
                  )
                )
              ]);
            })
          )
        );
      }
    }
    return el("section", { class: "train-section", id: "train-changes", "aria-labelledby": "train-changes-heading" }, children);
  }

  /* ---- Source ---- */

  function sourceSection(ctx, record) {
    const source = record.source || {};
    const metadataSource = (ctx.metadata || {}).source || {};
    const trainUrl = eventUrl(ctx, `train_window:${record.pqu_id}`) || source.url;
    const commit = String(source.commit || "");
    return el("section", { class: "train-section", id: "train-source", "aria-labelledby": "train-source-heading" }, [
      el("h3", { id: "train-source-heading", text: "Source" }),
      el("p", {}, [
        "Microsoft's article ",
        extLink(trainUrl, "Release schedule for proactive quality updates"),
        metadataSource.markdown_date ? ` (updated ${dates.formatDate(metadataSource.markdown_date)})` : "",
        ". ",
        source.raw_url ? extLink(source.raw_url, `Markdown at commit ${commit.slice(0, 7)}`) : null,
        source.raw_url ? "." : null
      ]),
      el("p", { class: "muted" }, [
        `First seen in this dataset ${dates.formatDateTime(record.first_seen_at, ctx.zone, { locale: ctx.locale })}; ` +
          `last changed ${dates.formatDateTime(record.last_changed_at, ctx.zone, { locale: ctx.locale })}.`
      ])
    ]);
  }

  /* ---- Not found ---- */

  function notFound(container, ctx, id) {
    const removed =
      ctx.changes && Array.isArray(ctx.changes.records)
        ? ctx.changes.records
            .filter((change) => change.entity === "pqu" && change.change_type === "removed" && change.pqu_id === id)
            .sort((a, b) => String(b.changed_at).localeCompare(String(a.changed_at)))[0]
        : null;
    container.replaceChildren(
      el("section", { class: "section", "aria-labelledby": "train-heading" }, [
        el("p", { class: "kicker", text: "PQU train" }),
        el("h2", { id: "train-heading", tabindex: "-1", dataset: { viewHeading: "" }, text: "Train not found" }),
        el("p", { id: "train-missing" }, [
          `“${id}” is not in Microsoft's current schedule.`,
          removed
            ? ` It was removed on ${dates.formatDate(String(removed.changed_at).slice(0, 10))}` +
              `${(removed.old_value || {}).status ? ` (last status ${removed.old_value.status})` : ""}.`
            : ""
        ]),
        el("p", {}, [el("a", { href: PQU.router.href("trains", {}, { q: id }), text: "Search all trains" })])
      ])
    );
  }

  function render(container, ctx, route) {
    const id = route.params.id || "";
    const record = findRecord(ctx, id);
    if (!record) {
      notFound(container, ctx, id);
      return;
    }
    if (record.pqu_id !== id) {
      PQU.app.replaceHash(common.trainHref(record.pqu_id));
    }
    container.replaceChildren(
      el("article", { class: "section train-page", "aria-labelledby": "train-heading", dataset: { pqu: record.pqu_id } }, [
        ...header(ctx, record),
        ...statusLines(ctx, record),
        facts(ctx, record),
        common.calcNote(
          `Countdowns, the phase line and build positions are calculated from Microsoft's published data for ${ctx.todayLabel} (${ctx.zoneName}).`,
          { id: "train-calc-note" }
        ),
        rolloutSection(ctx, record),
        changesSection(ctx, record),
        sourceSection(ctx, record)
      ])
    );
  }

  PQU.views.train = {
    name: "train",
    label: "Train",
    documents: ["stations", "regions", "learn", "changes", "events", "service_updates"],
    title: (route, ctx) => {
      const record = findRecord(ctx, route.params.id);
      return record ? text.trainLabel(record.pqu_id) : "Train not found";
    },
    render
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
