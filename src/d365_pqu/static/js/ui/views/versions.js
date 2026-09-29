/* Versions view: every service update on one lifecycle chart, Microsoft's milestone dates in a
 * table, the PQU trains published for each version, and Find my build. Dates, statuses and
 * builds are Microsoft's; phases, countdowns and build positions are calculated. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.views = PQU.views || {};
  const { el, extLink } = PQU.ui.dom;
  const dates = PQU.dates;
  const lifecycle = PQU.lifecycle;
  const records = PQU.records;
  const text = PQU.text;
  const common = PQU.ui.common;

  const MILESTONE_COLUMNS = [
    { field: "preview_date", label: "Preview" },
    { field: "preview_latest_update_date", label: "Latest preview update" },
    { field: "general_availability_date", label: "General availability" },
    { field: "first_autoupdate_date", label: "First autoupdate" },
    { field: "second_autoupdate_date", label: "Second autoupdate" },
    { field: "end_of_service_date", label: "End of service" }
  ];

  function slug(version) {
    return `version-${String(version).replace(/[^0-9a-z]+/gi, "-")}`;
  }

  function serviceDocument(ctx) {
    return ctx.serviceUpdates && Array.isArray(ctx.serviceUpdates.records) ? ctx.serviceUpdates : null;
  }

  function sourceNotice(ctx) {
    const document = serviceDocument(ctx);
    if (!document || ctx.errors.service_updates) {
      return el("p", {
        class: "inline-alert",
        text: "Microsoft's service update schedule could not be loaded, so lifecycle dates are not shown."
      });
    }
    if (document.state === "stale" && document.source) {
      return el("p", {
        class: "inline-alert",
        text:
          "The latest service update article could not be read. Showing the last published copy " +
          `(retrieved ${dates.formatDate(String(document.source.retrieved_at || "").slice(0, 10))}).`
      });
    }
    if (document.state !== "current") {
      return el("p", {
        class: "inline-alert",
        text: "Microsoft's service update schedule is not part of this dataset, so lifecycle dates are not shown."
      });
    }
    return null;
  }

  /* ---- Facts ---- */

  function statFacts(entries, todayIso) {
    const assessed = entries
      .filter((entry) => entry.lifecycle)
      .map((entry) => ({ entry, assessment: lifecycle.assess(entry.lifecycle, todayIso) }));
    if (!assessed.length) {
      return null;
    }
    const serviced = assessed.filter((item) => item.assessment.serviced);
    const upcoming = assessed
      .filter((item) => item.assessment.next)
      .sort(
        (a, b) =>
          a.assessment.next.date.localeCompare(b.assessment.next.date) ||
          PQU.versions.compareVersions(a.entry.version, b.entry.version)
      );
    const endings = serviced
      .filter((item) => item.entry.lifecycle.end_of_service_date)
      .sort((a, b) =>
        a.entry.lifecycle.end_of_service_date.localeCompare(b.entry.lifecycle.end_of_service_date)
      );
    const stats = [
      {
        label: "In service today",
        value: serviced.length
          ? text.joinList(
              serviced
                .map((item) => item.entry.version)
                .sort((a, b) => PQU.versions.compareVersions(a, b))
            )
          : "None"
      }
    ];
    if (upcoming.length) {
      const first = upcoming[0];
      stats.push({
        label: "Next milestone",
        value: `${first.entry.version} ${first.assessment.next.label.toLowerCase()} · ${dates.formatDate(
          first.assessment.next.date,
          { weekday: true }
        )} (${dates.daysPhrase(first.assessment.daysToNext)})`
      });
    }
    if (endings.length) {
      const first = endings[0];
      const eos = first.entry.lifecycle.end_of_service_date;
      stats.push({
        label: "Next end of service",
        value: `${first.entry.version} · ${dates.formatDate(eos, { weekday: true })} (${dates.daysPhrase(
          dates.diffDays(todayIso, eos)
        )})`
      });
    }
    return el(
      "dl",
      { class: "facts", id: "version-stats" },
      stats.map((stat) => el("div", {}, [el("dt", { text: stat.label }), el("dd", { class: "calc", text: stat.value })]))
    );
  }

  /* ---- Lifecycle chart ---- */

  function legend() {
    return el("ul", { class: "legend", "aria-label": "Chart key" }, [
      el("li", {}, [el("span", { class: "legend-swatch swatch-hollow", "aria-hidden": "true" }), "Preview"]),
      el("li", {}, [
        el("span", { class: "legend-swatch swatch-solid", "aria-hidden": "true" }),
        "General availability to end of service"
      ]),
      el("li", {}, [el("span", { class: "legend-notch", "aria-hidden": "true" }), "Autoupdates"]),
      el("li", {}, [el("span", { class: "legend-swatch swatch-past", "aria-hidden": "true" }), "Ended"]),
      el("li", {}, [el("span", { class: "legend-today", "aria-hidden": "true" }), "Today"])
    ]);
  }

  function lifecycleChart(ctx, entries) {
    const geometry = lifecycle.chart(
      entries.filter((entry) => entry.lifecycle).map((entry) => entry.lifecycle),
      ctx.todayIso
    );
    if (!geometry) {
      return null;
    }
    const label =
      `Lifecycle of ${text.plural(geometry.rows.length, "service update")} from ${dates.formatDate(geometry.start)} ` +
      `to ${dates.formatDate(geometry.end)}. ` +
      (geometry.today === null ? "Today is outside this range. " : `Today is ${dates.formatDate(ctx.todayIso)}. `) +
      "The table below lists every date.";
    const rows = geometry.rows.map((row) =>
      el("div", { class: ["lc-row", row.state === "end-of-service" ? "is-past" : null], dataset: { version: row.version } }, [
        el("span", { class: "lc-label", text: row.version }),
        el("div", { class: "lc-lane" }, [
          ...row.segments.map((segment) =>
            el("span", {
              class: ["lc-seg", `seg-${segment.kind}`],
              title: `${row.version} ${segment.kind === "preview" ? "preview" : "in service"}: ${dates.formatDateRange(
                segment.start,
                segment.end
              )}`,
              vars: { "--left": `${segment.left}%`, "--width": `${segment.width}%` }
            })
          ),
          ...row.marks.map((mark) => el("span", { class: "lc-mark", vars: { "--left": `${mark.left}%` } }))
        ])
      ])
    );
    return el("figure", { class: "lc-chart", id: "lifecycle-chart" }, [
      el("div", { class: "lc-scroll" }, [
        el("div", { class: "lc-plot", role: "img", "aria-label": label }, [
          ...geometry.ticks.map((tick) => el("span", { class: "lc-grid", vars: { "--f": String(tick.left / 100) } })),
          ...rows,
          el("div", { class: "lc-row lc-axis" }, [
            el("span", { class: "lc-label" }),
            el(
              "div",
              { class: "lc-lane" },
              geometry.ticks.map((tick) => el("span", { class: "lc-tick", vars: { "--left": `${tick.left}%` }, text: tick.label }))
            )
          ]),
          geometry.today === null
            ? null
            : el("span", { class: "lc-today", vars: { "--f": String(geometry.today / 100) } })
        ])
      ]),
      el("figcaption", {}, [legend()])
    ]);
  }

  /* ---- Dates table ---- */

  function milestoneCell(record, column, assessment, todayIso) {
    const value = record[column.field];
    if (!dates.isIsoDate(value)) {
      return el("td", { class: "muted", text: "—" });
    }
    const isNext = assessment.next && assessment.next.field === column.field;
    return el("td", {
      class: [isNext ? "is-next" : null, value <= todayIso ? "is-reached" : null],
      text: dates.formatDate(value)
    });
  }

  function versionRow(ctx, entry, focusVersion) {
    const id = slug(entry.version);
    const record = entry.lifecycle;
    const targeted = focusVersion === entry.version;
    const heading = el(
      "th",
      {
        scope: "row",
        id: `${id}-title`,
        tabindex: targeted ? "-1" : null,
        dataset: targeted ? { focusTarget: "" } : {}
      },
      [
        entry.version,
        record && (record.release_label || record.is_major)
          ? el("span", { class: "cell-note" }, [
              record.release_label || "",
              record.release_label && record.is_major ? " · " : "",
              record.is_major ? el("span", { class: "tag tag-major", text: "Major release" }) : null
            ])
          : null
      ]
    );
    if (!record) {
      return el("tr", { id, class: [targeted ? "is-target" : null], dataset: { version: entry.version } }, [
        heading,
        el("td", {}, [el("span", { class: "phase-name muted", text: "No lifecycle dates" })]),
        el("td", {
          class: "muted version-missing",
          colspan: String(MILESTONE_COLUMNS.length),
          text: "This version is not in Microsoft's current service update schedule."
        })
      ]);
    }
    const assessment = lifecycle.assess(record, ctx.todayIso);
    return el(
      "tr",
      { id, class: [targeted ? "is-target" : null, `phase-${assessment.state}`], dataset: { version: entry.version } },
      [
        heading,
        el("td", { class: "phase-cell" }, [
          common.calc(assessment.label, { class: "phase-name", announce: true }),
          el("span", { class: "cell-note calc version-next", text: assessment.summary })
        ]),
        ...MILESTONE_COLUMNS.map((column) => milestoneCell(record, column, assessment, ctx.todayIso))
      ]
    );
  }

  function datesTable(ctx, entries, focusVersion) {
    return el("div", { class: "table-scroll" }, [
      el("table", { class: "version-table", id: "version-table" }, [
        el("caption", {
          class: "visually-hidden",
          text: "Microsoft's milestone dates for each service update, with its phase today"
        }),
        el("thead", {}, [
          el("tr", {}, [
            el("th", { scope: "col", text: "Version" }),
            el("th", { scope: "col", text: "Today" }),
            ...MILESTONE_COLUMNS.map((column) => el("th", { scope: "col", text: column.label }))
          ])
        ]),
        el(
          "tbody",
          {},
          entries.map((entry) => versionRow(ctx, entry, focusVersion))
        )
      ])
    ]);
  }

  /* ---- Trains by version ---- */

  function trainsTable(entries) {
    const withTrains = entries.filter((entry) => entry.trains.length);
    if (!withTrains.length) {
      return el("p", { class: "muted", text: "No PQU trains in the current schedule." });
    }
    const summaries = withTrains.map((entry) => ({ entry, summary: lifecycle.trainSummary(entry.trains) }));
    const present = new Set(summaries.flatMap((item) => Object.keys(item.summary.counts)));
    const statuses = [
      ...records.STATUS_ORDER.filter((status) => present.has(status)),
      ...[...present].filter((status) => !records.STATUS_ORDER.includes(status)).sort()
    ];
    return el("div", { class: "table-scroll" }, [
      el("table", { class: "trains-by-version", id: "version-trains" }, [
        el("caption", {
          class: "visually-hidden",
          text: "PQU trains in Microsoft's schedule for each version, by status, with the newest published build"
        }),
        el("thead", {}, [
          el("tr", {}, [
            el("th", { scope: "col", text: "Version" }),
            el("th", { scope: "col", class: "num", text: "Trains" }),
            ...statuses.map((status) => el("th", { scope: "col", text: status })),
            el("th", { scope: "col", text: "Newest published build" })
          ])
        ]),
        el(
          "tbody",
          {},
          summaries.map(({ entry, summary }) =>
            el("tr", { class: "version-trains", dataset: { version: entry.version } }, [
              el("th", { scope: "row" }, [
                el("a", {
                  href: PQU.router.href("trains", {}, { version: entry.version }),
                  "aria-label": `Show ${entry.version} trains`,
                  text: entry.version
                })
              ]),
              el("td", { text: String(summary.total) }),
              ...statuses.map((status) => el("td", { text: String(summary.counts[status] || 0) })),
              el(
                "td",
                {},
                summary.latest
                  ? [
                      summary.latest.application_build,
                      " ",
                      el("span", { class: "cell-note" }, [
                        `Platform ${summary.latest.platform_build || "—"} · `,
                        common.trainLink(summary.latest.pqu_id)
                      ])
                    ]
                  : [el("span", { class: "muted", text: "No build published yet" })]
              )
            ])
          )
        )
      ])
    ]);
  }

  function scheduleNotes(ctx) {
    const article = PQU.ui.rich.article(ctx.learn, "service_updates");
    if (!article) {
      return null;
    }
    const intro = (article.sections.find((section) => section.id === "intro") || { blocks: [] }).blocks;
    const { before, after } = PQU.ui.guidance.datasetContext(article, "service_updates");
    return PQU.ui.guidance.panel({
      id: "service-update-rules",
      title: "How Microsoft schedules service updates",
      article,
      blocks: [...intro, ...before, ...after],
      summaryNote: "Microsoft Learn"
    });
  }

  /* ---- Find my build ---- */

  /* An example taken from the data: the newest train's builds. */
  function exampleBuilds(ctx) {
    const withBuild = ctx.records.filter((record) => record.application_build && record.platform_build);
    const latest =
      withBuild.find((record) => record.pqu_id === (ctx.metadata || {}).latest_pqu_id) ||
      [...withBuild].sort((a, b) => PQU.versions.compareVersions(b.application_build, a.application_build))[0];
    return latest ? { application: latest.application_build, platform: latest.platform_build } : null;
  }

  function versionState(ctx, version) {
    const document = serviceDocument(ctx);
    if (!document || (document.state !== "current" && document.state !== "stale")) {
      return null;
    }
    const record = document.records.find((item) => item.version === version);
    if (!record) {
      return `${version} is not in Microsoft's current service update schedule.`;
    }
    const assessment = lifecycle.assess(record, ctx.todayIso);
    return `${version} today: ${assessment.label} · ${assessment.summary}.`;
  }

  function trainRef(record, field) {
    return [record[field], " (", common.trainLink(record.pqu_id), ")"];
  }

  function newerText(count) {
    return count ? `${text.plural(count, "newer build")} published` : "No newer build published";
  }

  function buildResult(ctx, input) {
    const result = PQU.builds.locate(ctx.records, input);
    const example = exampleBuilds(ctx);
    const detail = (children, props = {}) => el("p", { class: "build-detail", ...props }, children);
    if (result.kind === "invalid") {
      return [
        detail(
          [
            "Enter a four-part build number",
            example ? `, for example ${example.application} (application) or ${example.platform} (platform)` : "",
            "."
          ],
          { class: "build-detail build-invalid" }
        )
      ];
    }
    if (result.kind === "unknown") {
      const lines = new Map();
      for (const record of ctx.records) {
        if (record.application_build) {
          lines.set(record.application_version, `${PQU.builds.lineOf(record.application_build)}.x`);
        }
      }
      const known = [...lines.entries()]
        .sort((a, b) => PQU.versions.compareVersions(a[0], b[0]))
        .map(([version, line]) => `${version} (${line})`);
      return [
        el("p", {
          class: "build-headline",
          text: `No train in Microsoft's schedule uses build line ${PQU.builds.lineOf(result.input)}`
        }),
        known.length ? detail([`The schedule lists application builds for ${text.joinList(known)}.`]) : null
      ];
    }
    const other = result.field === "application_build" ? "platform_build" : "application_build";
    const otherLabel = other === "application_build" ? "Application build" : "Platform build";
    let headline;
    let lines;
    switch (result.kind) {
      case "exact":
        headline = [common.trainLink(result.match.pqu_id), " · ", el("span", { class: "calc", text: newerText(result.newerCount) })];
        lines = [
          detail([
            `${result.input} is the ${result.label} of ${text.trainLabel(result.match.pqu_id)} ` +
              `(Microsoft status: ${result.match.status}).`,
            result.match[other] ? ` ${otherLabel} ${result.match[other]}.` : ""
          ]),
          result.newerCount
            ? detail([`Newest ${result.version} build published: `, ...trainRef(result.latest, result.field), "."])
            : null
        ];
        break;
      case "between":
        headline = [
          `Between ${text.trainLabel(result.older.pqu_id)} and ${text.trainLabel(result.newer.pqu_id)} · `,
          el("span", { class: "calc", text: newerText(result.newerCount) })
        ];
        lines = [
          detail([
            `Microsoft's schedule doesn't list ${result.input} as a PQU build. It is newer than `,
            ...trainRef(result.older, result.field),
            " and older than ",
            ...trainRef(result.newer, result.field),
            "."
          ])
        ];
        break;
      case "before":
        headline = [
          `Older than every ${result.version} build listed · `,
          el("span", { class: "calc", text: newerText(result.newerCount) })
        ];
        lines = [
          detail([`The earliest ${result.version} build in Microsoft's schedule is `, ...trainRef(result.newer, result.field), "."])
        ];
        break;
      default:
        headline = [`Newer than every ${result.version} build listed`];
        lines = [
          detail([`The newest ${result.version} build in Microsoft's schedule is `, ...trainRef(result.older, result.field), "."])
        ];
    }
    const state = versionState(ctx, result.version);
    return [
      el("p", { class: "build-headline" }, headline),
      ...lines,
      state
        ? detail([
            el("span", { class: "calc", text: state }),
            " ",
            el("a", {
              href: PQU.router.href("versions", {}, { build: result.input, version: result.version }),
              text: `Show ${result.version}`
            })
          ])
        : null
    ];
  }

  function buildFinder(ctx, route) {
    const example = exampleBuilds(ctx);
    const result = el("div", { id: "build-result", class: "build-result", "aria-live": "polite" });
    const input = el("input", {
      id: "build-input",
      name: "build",
      type: "text",
      inputmode: "decimal",
      autocomplete: "off",
      spellcheck: "false",
      placeholder: example ? `For example ${example.application}` : "Build number",
      value: route.query.build || ""
    });
    function show(value) {
      const trimmed = String(value || "").trim();
      result.replaceChildren(...(trimmed ? buildResult(ctx, trimmed) : []));
      return trimmed;
    }
    const form = el(
      "form",
      {
        id: "build-form",
        class: "build-form",
        role: "search",
        "aria-label": "Find my build",
        novalidate: true,
        on: {
          submit: (event) => {
            event.preventDefault();
            const value = show(input.value);
            PQU.app.replaceHash(PQU.router.href("versions", {}, { build: value }));
          }
        }
      },
      [
        el("label", { class: "field" }, [el("span", { text: "Application or platform build" }), input]),
        el("button", { class: "button primary", type: "submit", text: "Find" })
      ]
    );
    show(route.query.build);
    return common.block(
      "build-finder",
      "Find my build",
      [
        el("p", {
          text: "Enter the build your environment runs to see which PQU train published it and how many newer builds Microsoft lists for its version."
        }),
        form,
        result,
        common.calcNote("Build positions are calculated by comparing the number with the PQU builds in Microsoft's schedule.")
      ],
      { headingId: "build-finder-heading" }
    );
  }

  function render(container, ctx, route) {
    const document = serviceDocument(ctx);
    const serviceRecords = document && document.state !== "not_configured" ? document.records : [];
    const entries = lifecycle.mergeVersions(serviceRecords, ctx.records);
    const source = document && document.source ? document.source : null;
    const focusVersion = (route && route.query.version) || null;
    const hasDates = entries.some((entry) => entry.lifecycle);
    container.replaceChildren(
      el("div", { class: "page versions" }, [
        common.pageHead({
          id: "versions-heading",
          title: "Service updates",
          sub: "Each service update (version) moves from preview to general availability, two autoupdates and end of service. PQU trains deliver fixes to the versions in service.",
          aside: source
            ? [
                "Dates from ",
                extLink(source.article_url, "Service update availability"),
                source.markdown_date ? ` · updated ${dates.formatDate(source.markdown_date)}` : ""
              ]
            : null
        }),
        sourceNotice(ctx),
        statFacts(entries, ctx.todayIso),
        hasDates ? common.italicNote(ctx) : null,
        buildFinder(ctx, route || { query: {} }),
        common.block("version-lifecycle", "Lifecycle", [
          hasDates ? lifecycleChart(ctx, entries) : null,
          datesTable(ctx, entries, focusVersion),
          scheduleNotes(ctx)
        ]),
        common.block("version-train-counts", "PQU trains by version", [trainsTable(entries)])
      ])
    );
  }

  PQU.views.versions = {
    name: "versions",
    label: "Versions",
    documents: ["service_updates", "learn"],
    title: () => "Service updates",
    render
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
