/* Overview: today's date, what is running, your region's next windows and the next two weeks.
 * Dates, statuses and builds are Microsoft's; phases, countdowns and pairings are calculated for
 * today in the viewer's time zone and set in italics. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.views = PQU.views || {};
  const { el, extLink, visuallyHidden } = PQU.ui.dom;
  const dates = PQU.dates;
  const text = PQU.text;
  const agenda = PQU.agenda;
  const lifecycle = PQU.lifecycle;
  const windows = PQU.windows;
  const common = PQU.ui.common;
  const prefs = PQU.ui.prefs;

  const NEXT_DATES = 4;
  const AGENDA_DAYS = agenda.DEFAULT_DAYS;
  const KIND_LABELS = {
    change_cutoff: "Change cutoff",
    train_window: "Train starts",
    sandbox_window: "Sandbox window",
    production_window: "Production window",
    preview: "Preview",
    preview_latest_update: "Latest preview update",
    general_availability: "General availability",
    autoupdate_first: "First autoupdate",
    autoupdate_second: "Second autoupdate",
    end_of_service: "End of service"
  };

  function events(ctx) {
    return (ctx.events && ctx.events.records) || [];
  }

  function yearNeeded(iso, todayIso) {
    return String(iso || "").slice(0, 4) !== String(todayIso).slice(0, 4);
  }

  function dayLabel(iso, todayIso) {
    return dates.formatDate(iso, { weekday: true, year: yearNeeded(iso, todayIso) });
  }

  function savedRegion(ctx) {
    const name = prefs.read("region");
    return ctx.regions.find((row) => row.is_region && row.region === name) || null;
  }

  function servicedVersions(ctx) {
    const doc = ctx.serviceUpdates;
    const list = doc && doc.state !== "not_configured" && Array.isArray(doc.records) ? doc.records : [];
    return list
      .filter((record) => lifecycle.assess(record, ctx.todayIso).serviced)
      .map((record) => record.version)
      .sort(PQU.versions.compareVersions);
  }

  /* ---- Summary ---- */

  function summary(ctx) {
    const running = ctx.records.filter((record) => record.status === "In-Progress");
    const parts = [
      visuallyHidden("Summary: "),
      `Microsoft lists ${text.plural(running.length, "train")} as In-Progress.`
    ];
    const next = agenda.nextOf(events(ctx), ctx.todayIso, ["change_cutoff"], 1)[0];
    if (next) {
      parts.push(
        ` The next change cutoff, for ${text.trainLabel(next.pqu_id)}, is `,
        el("span", { class: "calc", text: agenda.whenText(next, ctx.todayIso) }),
        ` (${dayLabel(next.start_date, ctx.todayIso)}).`
      );
    }
    const serviced = servicedVersions(ctx);
    if (serviced.length) {
      parts.push(
        ` ${text.joinList(serviced)} ${serviced.length === 1 ? "is" : "are"} `,
        el("span", { class: "calc", text: "in service" }),
        "."
      );
    }
    return el("p", { id: "ov-summary", class: "ov-summary" }, parts);
  }

  /* ---- Your region ---- */

  function regionFact(label, value) {
    return el("div", {}, [el("dt", { text: label }), el("dd", {}, value)]);
  }

  function regionBlock(ctx) {
    const region = savedRegion(ctx);
    if (!region) {
      return common.block("ov-region", "Your region", [
        el("p", {}, [
          "Pick your Azure region to see its station's next sandbox and production windows here. ",
          el("a", { href: PQU.router.href("region"), text: "Pick your region" })
        ])
      ]);
    }
    const rows = ctx.stations.filter((row) => row.station === region.station);
    const plan = windows.stationSchedule(rows, ctx.todayIso);
    const productions = plan.active
      .filter((item) => item.production && item.production.state !== "done")
      .sort((a, b) => a.row.production_start_date.localeCompare(b.row.production_start_date));
    const sandboxes = plan.active.filter((item) => item.sandbox && item.sandbox.state === "current");
    const facts = [];
    const next = productions[0];
    if (next) {
      facts.push(
        regionFact("Next production window", [
          el("span", { class: "ov-big" }, [
            visuallyHidden("Next production window: "),
            dates.formatDateRange(next.row.production_start_date, next.row.production_end_date, {
              weekday: true,
              year: yearNeeded(next.row.production_start_date, ctx.todayIso)
            })
          ]),
          el("span", { class: "ov-region-train" }, [
            common.trainLink(next.row.pqu_id),
            " · ",
            common.calc(next.production.text.toLowerCase())
          ])
        ])
      );
      const doc = ctx.maintenance;
      const window =
        doc && Array.isArray(doc.records) && region.maintenance_geo
          ? doc.records.find((item) => item.geo === region.maintenance_geo)
          : null;
      if (window) {
        const pair = windows.forRange(window, next.row.production_start_date, next.row.production_end_date);
        facts.push(
          regionFact(
            `${window.geo} dark hours that weekend`,
            pair.paired
              ? [
                  el(
                    "ul",
                    { class: "ov-dark-hours calc" },
                    pair.windows.map((occ) => el("li", { text: windows.rangeText(occ, ctx.zone, ctx.locale) }))
                  )
                ]
              : [el("span", { text: windows.ruleText(window) })]
          )
        );
      }
    } else {
      facts.push(
        regionFact("Next production window", [
          el("span", { text: `No upcoming Station ${region.station} production windows in Microsoft's schedule.` })
        ])
      );
    }
    facts.push(
      regionFact(
        "Sandbox now",
        sandboxes.length
          ? [
              ...sandboxes.flatMap((item, index) => [index ? ", " : "", common.trainLink(item.row.pqu_id)]),
              " · ",
              common.calc(sandboxes[0].sandbox.text.toLowerCase())
            ]
          : [el("span", { class: "muted", text: "No sandbox window today" })]
      )
    );
    return common.block(
      "ov-region",
      [
        el("span", { class: "ov-region-name", text: `${region.region} · Station ${region.station}` })
      ],
      [el("dl", { class: "ov-region-facts" }, facts)],
      { link: { href: PQU.router.href("region", { region: region.region }), text: "All windows" } }
    );
  }

  /* ---- In progress now ---- */

  function runningBlock(ctx) {
    const running = ctx.records
      .filter((record) => record.status === "In-Progress")
      .sort(
        (a, b) =>
          PQU.versions.compareVersions(a.application_version, b.application_version) ||
          a.release_number - b.release_number
      );
    const link = { href: PQU.router.href("trains", {}, { status: "In-Progress" }), text: "All in-progress trains" };
    if (!running.length) {
      return common.block(
        "ov-running",
        "In progress now",
        [el("p", { class: "muted", text: "Microsoft lists no trains as In-Progress." })],
        { link }
      );
    }
    const rows = running.map((record) => {
      const phase = ctx.phases.get(record.pqu_id);
      const line = phase ? [phase.text, phase.detail].filter(Boolean).join(" · ") : "";
      const flags = ctx.flags[record.pqu_id] || [];
      return el("tr", { dataset: { pqu: record.pqu_id } }, [
        el("th", { scope: "row" }, [common.trainLink(record.pqu_id), common.newTag(record)]),
        el("td", { class: "num", "data-label": "Application build", text: record.application_build || "Not published" }),
        el("td", { "data-label": "Where it is today" }, [
          line ? common.calc(line, { class: "phase-line", announce: true }) : null,
          phase && phase.conflict ? el("span", { class: "phase-note", text: phase.conflict }) : null,
          flags.length
            ? el("span", {
                class: "phase-note",
                text: `Source warning: ${flags.map((item) => PQU.health.describe(item, ctx.recordsById)).join(" ")}`
              })
            : null
        ])
      ]);
    });
    return common.block(
      "ov-running",
      "In progress now",
      [
        el("div", { class: "table-scroll" }, [
          el("table", { class: "ov-running-table stack-table" }, [
            el("caption", {
              class: "visually-hidden",
              text: "Trains Microsoft lists as In-Progress, with where each one is today"
            }),
            el("thead", {}, [
              el("tr", {}, [
                el("th", { scope: "col", text: "Train" }),
                el("th", { scope: "col", text: "Application build" }),
                el("th", { scope: "col", text: "Where it is today" })
              ])
            ]),
            el("tbody", {}, rows)
          ])
        ])
      ],
      { link }
    );
  }

  /* ---- Next 14 days ---- */

  function agendaBlock(ctx) {
    const region = savedRegion(ctx);
    const station = region ? region.station : null;
    const list = agenda.upcoming(events(ctx), ctx.todayIso, {
      days: AGENDA_DAYS,
      station,
      // Running trains are listed under "In progress now"; only open station windows repeat here.
      ongoingKinds: ["sandbox_window", "production_window"]
    });
    const groups = agenda.byDay(list, ctx.todayIso);
    const note = station
      ? `Station ${station} windows for ${region.region}, plus every change cutoff, train start and service update date.`
      : "Every published date. Pick your region to see only your station's windows.";
    const body = groups.length
      ? el(
          "ol",
          { class: "agenda", id: "agenda" },
          groups.map((group) =>
            el(
              "li",
              { class: ["agenda-day", group.day === ctx.todayIso ? "is-today" : null], dataset: { day: group.day } },
              [
                el("p", { class: "agenda-date" }, [
                  el("span", { text: dayLabel(group.day, ctx.todayIso) }),
                  " ",
                  el("span", {
                    class: "agenda-rel calc",
                    text:
                      group.day === ctx.todayIso
                        ? "today"
                        : dates.daysPhrase(dates.diffDays(ctx.todayIso, group.day))
                  })
                ]),
                el(
                  "ul",
                  {},
                  group.events.map((event) =>
                    el("li", { class: `agenda-event kind-${event.kind}`, dataset: { event: event.id } }, [
                      el("span", { class: "agenda-kind", text: KIND_LABELS[event.kind] }),
                      " ",
                      el("span", { class: "agenda-what" }, [
                        event.pqu_id
                          ? common.trainLink(event.pqu_id)
                          : el("span", { text: event.application_version }),
                        event.station ? ` · Station ${event.station}` : null,
                        event.end_date !== event.start_date
                          ? event.ongoing
                            ? [" · ", el("span", { class: "calc", text: agenda.whenText(event, ctx.todayIso) })]
                            : ` · ${dates.formatDateRange(event.start_date, event.end_date, { year: false })}`
                          : null,
                        event.warnings.length
                          ? el("span", { class: "flag", title: "Microsoft's article contradicts itself here", text: "Source warning" })
                          : null
                      ])
                    ])
                  )
                )
              ]
            )
          )
        )
      : el("p", { class: "muted", text: `No published dates in the next ${AGENDA_DAYS} days.` });
    const calendar = PQU.ui.calendar;
    const subscribe = el("details", { class: "rules calendar-details", id: "ov-calendar" }, [
      el("summary", {}, [el("span", { class: "rules-title", text: "Add these dates to your calendar" })]),
      el("div", { class: "calendar-blocks" }, [
        station ? calendar.stationBlock(ctx, station, "ov-calendar") : null,
        calendar.milestonesBlock(ctx, "ov-calendar")
      ]),
      station
        ? null
        : el("p", { class: "calendar-help" }, [
            "For your station's sandbox and production windows, ",
            el("a", { href: PQU.router.href("region"), text: "pick your region" }),
            "."
          ]),
      calendar.help()
    ]);
    return common.block(
      "ov-agenda",
      station ? `Next ${AGENDA_DAYS} days · Station ${station}` : `Next ${AGENDA_DAYS} days`,
      [el("p", { class: "note ov-agenda-note", text: note }), body, subscribe]
    );
  }

  /* ---- Aside: next cutoffs, service updates, figures, sources ---- */

  function nextDatesBlock(ctx) {
    const next = agenda.nextOf(events(ctx), ctx.todayIso, ["change_cutoff", "train_window"], NEXT_DATES * 2);
    const seen = new Set();
    const rows = [];
    for (const event of next) {
      const key = `${event.pqu_id}|${event.start_date}`;
      const record = ctx.recordsById[event.pqu_id];
      if (seen.has(key)) {
        continue;
      }
      seen.add(key);
      const sameDayStart = event.kind === "change_cutoff" && record && record.train_start_date === event.start_date;
      rows.push(
        el("li", {}, [
          el("span", { class: "ov-date" }, [
            el("span", { class: "ov-date-day", text: dayLabel(event.start_date, ctx.todayIso) }),
            " ",
            el("span", { class: "ov-date-when calc", text: agenda.whenText(event, ctx.todayIso) })
          ]),
          " ",
          el("span", { class: "ov-what" }, [
            common.trainLink(event.pqu_id),
            ` · ${sameDayStart ? "change cutoff and train start" : KIND_LABELS[event.kind].toLowerCase()}`
          ])
        ])
      );
      if (rows.length === NEXT_DATES) {
        break;
      }
    }
    return common.block(
      "ov-next",
      "Next cutoffs and starts",
      rows.length
        ? [el("ul", { class: "ruled-list ov-dates" }, rows)]
        : [el("p", { class: "muted", text: "No upcoming change cutoffs or train starts in Microsoft's schedule." })],
      { link: { href: PQU.router.href("trains", {}, { status: "Not Started" }), text: "Upcoming trains" } }
    );
  }

  function versionsBlock(ctx) {
    const doc = ctx.serviceUpdates;
    const records = doc && doc.state !== "not_configured" && Array.isArray(doc.records) ? doc.records : [];
    if (!records.length) {
      return common.block("ov-versions", "Service updates", [
        el("p", {
          class: "muted",
          text: ctx.errors.service_updates
            ? "Microsoft's service update schedule could not be loaded."
            : "Microsoft's service update schedule is not part of this dataset."
        })
      ]);
    }
    const assessed = records
      .map((record) => ({ record, assessment: lifecycle.assess(record, ctx.todayIso) }))
      .filter((item) => item.assessment.serviced || item.assessment.state === "preview")
      .sort((a, b) => PQU.versions.compareVersions(b.record.version, a.record.version));
    const rows = assessed.map(({ record, assessment }) =>
      el("li", { dataset: { version: record.version } }, [
        el("span", { class: "ov-version-line" }, [
          el("a", {
            class: "ov-version",
            href: PQU.router.href("versions", {}, { version: record.version }),
            text: record.version
          }),
          " ",
          common.calc(assessment.label, { class: "phase-name", announce: true })
        ]),
        " ",
        el("span", { class: "ov-version-next calc", text: assessment.summary })
      ])
    );
    return common.block(
      "ov-versions",
      "Service updates",
      [
        rows.length
          ? el("ul", { class: "ruled-list" }, rows)
          : el("p", { class: "muted", text: "No service update is in service today." }),
        el("p", { class: "note", id: "ov-find-build" }, [
          "Which train published your build? ",
          el("a", { href: PQU.router.href("versions"), text: "Find my build" })
        ])
      ],
      { link: { href: PQU.router.href("versions"), text: "All versions" } }
    );
  }

  function insightsBlock(ctx) {
    const doc = ctx.insights;
    if (!doc || !Array.isArray(doc.records) || !(doc.highlights || []).length) {
      return null;
    }
    const byId = Object.fromEntries(doc.records.map((record) => [record.id, record]));
    const items = doc.highlights.map((id) => byId[id]).filter(Boolean);
    return common.block(
      "ov-insights",
      "What the data says",
      [
        el(
          "ul",
          { class: "ruled-list" },
          items.map((record) => el("li", { dataset: { insight: record.id }, text: record.summary }))
        ),
        common.calcNote("Calculated from Microsoft's published dates. Microsoft doesn't publish these figures.")
      ],
      { link: { href: PQU.router.href("learn"), text: "More in Learn" } }
    );
  }

  function sourcesBlock(ctx) {
    const sources = (ctx.metadata && ctx.metadata.sources) || {};
    const entries = Object.values(sources).filter((entry) => entry && entry.source);
    if (!entries.length) {
      return null;
    }
    return common.block("ov-sources", "Sources", [
      el(
        "ul",
        { class: "ruled-list" },
        entries.map((entry) =>
          el("li", {}, [
            extLink(entry.article_url, entry.label),
            entry.source.markdown_date
              ? el("span", { class: "fact-note", text: `Microsoft Learn · updated ${dates.formatDate(entry.source.markdown_date)}` })
              : null,
            entry.state === "stale" ? el("span", { class: "phase-note", text: "Showing the last published copy" }) : null
          ])
        )
      )
    ]);
  }

  function render(container, ctx) {
    container.replaceChildren(
      el("div", { class: "page overview" }, [
        common.pageHead({
          id: "overview-heading",
          title: ctx.todayLong,
          sub: [summary(ctx), common.italicNote(ctx)]
        }),
        el("div", { class: "page-columns" }, [
          el("div", { class: "column-main" }, [regionBlock(ctx), runningBlock(ctx), agendaBlock(ctx)]),
          el("aside", { class: "column-aside", "aria-label": "Dates, versions and sources" }, [
            nextDatesBlock(ctx),
            versionsBlock(ctx),
            insightsBlock(ctx),
            sourcesBlock(ctx)
          ])
        ])
      ])
    );
  }

  PQU.views.overview = {
    name: "overview",
    label: "Overview",
    documents: ["stations", "regions", "events", "service_updates", "maintenance", "insights"],
    title: () => "Overview",
    render
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
