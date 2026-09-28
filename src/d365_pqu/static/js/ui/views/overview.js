/* Overview: what is happening now, what comes next, and where to go for detail. Every number
 * comes from the published documents, and every phase is calculated for today. */
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

  function card(id, title, children, options = {}) {
    return el("section", { class: ["ov-card", options.class], id, "aria-labelledby": `${id}-title` }, [
      el("div", { class: "ov-card-head" }, [
        el("h3", { id: `${id}-title`, text: title }),
        options.link ? el("a", { class: "ov-card-link", href: options.link.href, text: options.link.text }) : null
      ]),
      ...children
    ]);
  }

  /* ---- Summary line ---- */

  function summary(ctx) {
    const running = ctx.records.filter((record) => record.status === "In-Progress");
    const parts = [
      `Microsoft lists ${text.plural(running.length, "train")} as In-Progress`
    ];
    const next = agenda.nextOf(events(ctx), ctx.todayIso, ["change_cutoff"], 1)[0];
    if (next) {
      parts.push(
        `the next change cutoff is ${text.trainLabel(next.pqu_id)} ${agenda.whenText(next, ctx.todayIso)} (${dayLabel(
          next.start_date,
          ctx.todayIso
        )})`
      );
    }
    const serviced = (ctx.serviceUpdates && ctx.serviceUpdates.state !== "not_configured" ? ctx.serviceUpdates.records : [])
      .filter((record) => lifecycle.assess(record, ctx.todayIso).serviced)
      .map((record) => record.version)
      .sort(PQU.versions.compareVersions);
    if (serviced.length) {
      parts.push(`${text.joinList(serviced)} ${serviced.length === 1 ? "is" : "are"} in service`);
    }
    return el("p", { class: "ov-summary", id: "ov-summary" }, [
      visuallyHidden("Summary: "),
      `${text.capitalize(text.joinList(parts))}.`
    ]);
  }

  /* ---- In progress now ---- */

  function runningCard(ctx) {
    const running = ctx.records
      .filter((record) => record.status === "In-Progress")
      .sort(
        (a, b) =>
          PQU.versions.compareVersions(a.application_version, b.application_version) ||
          a.release_number - b.release_number
      );
    if (!running.length) {
      return card("ov-running", "In progress now", [
        el("p", { class: "muted", text: "Microsoft lists no trains as In-Progress." })
      ]);
    }
    const items = running.map((record) => {
      const phase = ctx.phases.get(record.pqu_id);
      const line = phase ? [phase.text, phase.detail].filter(Boolean).join(" · ") : "";
      return el("li", { dataset: { pqu: record.pqu_id } }, [
        el("div", { class: "ov-row-head" }, [
          common.trainLink(record.pqu_id, { class: "ov-train" }),
          common.statusBadge(record.status),
          common.newChip(record),
          record.application_build ? el("span", { class: "mono muted build", text: record.application_build }) : null
        ]),
        line ? el("p", { class: "phase" }, [visuallyHidden("Calculated from published dates: "), line]) : null,
        phase && phase.conflict ? el("p", { class: "phase-note", text: phase.conflict }) : null,
        (ctx.flags[record.pqu_id] || []).length
          ? el("p", { class: "phase-note" }, [
              "⚑ ",
              (ctx.flags[record.pqu_id] || []).map((item) => PQU.health.describe(item, ctx.recordsById)).join(" ")
            ])
          : null
      ]);
    });
    return card("ov-running", "In progress now", [el("ul", { class: "ov-list" }, items)], {
      link: { href: PQU.router.href("trains", {}, { status: "In-Progress" }), text: "All in-progress trains" }
    });
  }

  /* ---- Next dates ---- */

  function nextDatesCard(ctx) {
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
      const sameDayStart =
        event.kind === "change_cutoff" && record && record.train_start_date === event.start_date;
      rows.push(
        el("li", {}, [
          el("span", { class: "ov-date" }, [
            el("span", { class: "ov-date-day", text: dayLabel(event.start_date, ctx.todayIso) }),
            el("span", { class: "ov-date-when", text: agenda.whenText(event, ctx.todayIso) })
          ]),
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
    return card(
      "ov-next",
      "Next cutoffs and starts",
      rows.length
        ? [el("ul", { class: "ov-list ov-dates" }, rows)]
        : [el("p", { class: "muted", text: "No upcoming change cutoffs or train starts in Microsoft's schedule." })],
      { link: { href: PQU.router.href("trains", {}, { status: "Not Started" }), text: "Upcoming trains" } }
    );
  }

  /* ---- Your region ---- */

  function regionCard(ctx) {
    const region = savedRegion(ctx);
    if (!region) {
      return card("ov-region", "Your region", [
        el("p", { class: "muted", text: "Pick your Azure region to see your station's next sandbox and production windows here." }),
        el("p", {}, [el("a", { class: "button small", href: PQU.router.href("region"), text: "Pick your region" })])
      ]);
    }
    const rows = ctx.stations.filter((row) => row.station === region.station);
    const plan = windows.stationSchedule(rows, ctx.todayIso);
    const productions = plan.active
      .filter((item) => item.production && item.production.state !== "done")
      .sort((a, b) => a.row.production_start_date.localeCompare(b.row.production_start_date));
    const sandboxes = plan.active.filter((item) => item.sandbox && item.sandbox.state === "current");
    const children = [
      el("p", { class: "ov-region-name" }, [
        el("strong", { text: region.region }),
        ` · Station ${region.station}`
      ])
    ];
    const next = productions[0];
    if (next) {
      const lines = [
        el("p", { class: "ov-big" }, [
          visuallyHidden("Next production window: "),
          dates.formatDateRange(next.row.production_start_date, next.row.production_end_date, {
            weekday: true,
            year: yearNeeded(next.row.production_start_date, ctx.todayIso)
          })
        ]),
        el("p", { class: "muted" }, [
          "Production · ",
          common.trainLink(next.row.pqu_id),
          ` · ${next.production.text}`
        ])
      ];
      const doc = ctx.maintenance;
      const window =
        doc && Array.isArray(doc.records) && region.maintenance_geo
          ? doc.records.find((item) => item.geo === region.maintenance_geo)
          : null;
      if (window) {
        const pair = windows.forRange(window, next.row.production_start_date, next.row.production_end_date);
        if (pair.paired) {
          lines.push(
            el("ul", { class: "ov-dark-hours" }, pair.windows.map((occ) => el("li", { text: windows.rangeText(occ, ctx.zone, ctx.locale) })))
          );
          lines.push(
            el("p", { class: "cell-note", text: `${window.geo} dark hours on that weekend (calculated from Microsoft's UTC times).` })
          );
        }
      }
      children.push(...lines);
    } else {
      children.push(el("p", { class: "muted", text: `No upcoming Station ${region.station} production windows in Microsoft's schedule.` }));
    }
    if (sandboxes.length) {
      children.push(
        el("p", { class: "ov-sub" }, [
          "Sandbox now: ",
          ...sandboxes.flatMap((item, index) => [index ? ", " : "", common.trainLink(item.row.pqu_id)]),
          ` (${sandboxes[0].sandbox.text.toLowerCase()})`
        ])
      );
    }
    return card("ov-region", "Your region", children, {
      link: { href: PQU.router.href("region", { region: region.region }), text: "All windows" }
    });
  }

  /* ---- Versions ---- */

  function versionsCard(ctx) {
    const doc = ctx.serviceUpdates;
    const records = doc && doc.state !== "not_configured" && Array.isArray(doc.records) ? doc.records : [];
    if (!records.length) {
      return card("ov-versions", "Service updates", [
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
        el("a", {
          class: "mono ov-version",
          href: PQU.router.href("versions", {}, { version: record.version }),
          text: record.version
        }),
        " ",
        el("span", { class: `phase-badge phase-badge-${assessment.state}`, text: assessment.label }),
        " ",
        el("span", { class: "muted ov-version-next" }, [visuallyHidden("Calculated: "), assessment.summary])
      ])
    );
    return card(
      "ov-versions",
      "Service updates",
      [
        rows.length
          ? el("ul", { class: "ov-list" }, rows)
          : el("p", { class: "muted", text: "No service update is in service today." }),
        el("p", { class: "ov-sub", id: "ov-find-build" }, [
          "Which train published your build? ",
          el("a", { href: PQU.router.href("versions"), text: "Find my build" })
        ])
      ],
      { link: { href: PQU.router.href("versions"), text: "Lifecycle" } }
    );
  }

  /* ---- Agenda ---- */

  function agendaSection(ctx) {
    const region = savedRegion(ctx);
    const station = region ? region.station : null;
    const list = agenda.upcoming(events(ctx), ctx.todayIso, {
      days: AGENDA_DAYS,
      station,
      // Running trains are listed under "In progress now"; only open station windows repeat here.
      ongoingKinds: ["sandbox_window", "production_window"]
    });
    const groups = agenda.byDay(list, ctx.todayIso);
    const heading = station ? `Next ${AGENDA_DAYS} days · Station ${station}` : `Next ${AGENDA_DAYS} days`;
    const note = station
      ? `Station windows for ${region.region} (Station ${station}), plus every cutoff, train, and service update date.`
      : "Every published date. Pick your region to see only your station's windows.";
    const body = groups.length
      ? el(
          "ol",
          { class: "agenda", id: "agenda" },
          groups.map((group) =>
            el("li", { class: ["agenda-day", group.day === ctx.todayIso ? "is-today" : null], dataset: { day: group.day } }, [
              el("p", { class: "agenda-date" }, [
                el("span", { text: dayLabel(group.day, ctx.todayIso) }),
                el("span", { class: "muted", text: group.day === ctx.todayIso ? "today" : dates.daysPhrase(dates.diffDays(ctx.todayIso, group.day)) })
              ]),
              el(
                "ul",
                {},
                group.events.map((event) =>
                  el("li", { class: `agenda-event kind-${event.kind}`, dataset: { event: event.id } }, [
                    el("span", { class: "agenda-kind", text: KIND_LABELS[event.kind] }),
                    " ",
                    event.pqu_id ? common.trainLink(event.pqu_id) : el("span", { class: "mono", text: event.application_version }),
                    event.station ? el("span", { class: "muted", text: ` · Station ${event.station}` }) : null,
                    event.end_date !== event.start_date
                      ? el("span", {
                          class: "muted",
                          text: event.ongoing
                            ? ` · ${agenda.whenText(event, ctx.todayIso)}`
                            : ` · ${dates.formatDateRange(event.start_date, event.end_date, { year: false })}`
                        })
                      : null,
                    event.warnings.length ? el("span", { class: "flag", title: "Source warning", text: " ⚑" }) : null
                  ])
                )
              )
            ])
          )
        )
      : el("p", { class: "muted", text: `No published dates in the next ${AGENDA_DAYS} days.` });
    const calendar = PQU.ui.calendar;
    const subscribe = el("details", { class: "calendar-details", id: "ov-calendar" }, [
      el("summary", { text: "Add to your calendar" }),
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
    return el("section", { class: "ov-agenda", id: "ov-agenda", "aria-labelledby": "ov-agenda-title" }, [
      el("div", { class: "ov-card-head" }, [el("h3", { id: "ov-agenda-title", text: heading })]),
      el("p", { class: "muted ov-agenda-note", text: note }),
      body,
      subscribe
    ]);
  }

  /* ---- Insights and sources ---- */

  function insightsStrip(ctx) {
    const doc = ctx.insights;
    if (!doc || !Array.isArray(doc.records) || !(doc.highlights || []).length) {
      return null;
    }
    const byId = Object.fromEntries(doc.records.map((record) => [record.id, record]));
    const items = doc.highlights.map((id) => byId[id]).filter(Boolean);
    return el("section", { class: "ov-insights", id: "ov-insights", "aria-labelledby": "ov-insights-title" }, [
      el("div", { class: "ov-card-head" }, [
        el("h3", { id: "ov-insights-title", text: "What the data says" }),
        el("a", { class: "ov-card-link", href: PQU.router.href("learn"), text: "More in Learn" })
      ]),
      el("ul", {}, items.map((record) => el("li", { dataset: { insight: record.id }, text: record.summary }))),
      common.calcNote("Calculated from Microsoft's published dates; Microsoft doesn't publish these figures.")
    ]);
  }

  function sourcesStrip(ctx) {
    const sources = (ctx.metadata && ctx.metadata.sources) || {};
    const entries = Object.values(sources).filter((entry) => entry && entry.source);
    if (!entries.length) {
      return null;
    }
    return el("section", { class: "ov-sources", id: "ov-sources", "aria-labelledby": "ov-sources-title" }, [
      el("h3", { id: "ov-sources-title", class: "visually-hidden", text: "Sources" }),
      el("p", {}, [
        "From Microsoft Learn: ",
        ...entries.flatMap((entry, index) => [
          index ? " · " : "",
          extLink(entry.article_url, entry.label),
          entry.source.markdown_date ? el("span", { class: "muted", text: ` (${dates.formatDate(entry.source.markdown_date)})` }) : null,
          entry.state === "stale" ? el("span", { class: "phase-note-inline", text: " last published copy" }) : null
        ])
      ])
    ]);
  }

  function render(container, ctx) {
    container.replaceChildren(
      el("div", { class: "overview" }, [
        el("div", { class: "section-head" }, [
          el("div", {}, [
            el("p", { class: "kicker", text: ctx.todayLabel }),
            el("h2", {
              id: "overview-heading",
              tabindex: "-1",
              dataset: { viewHeading: "" },
              text: "Proactive quality updates today"
            })
          ])
        ]),
        summary(ctx),
        common.calcNote(`Phases and countdowns are calculated from Microsoft's published dates for ${ctx.todayLabel} (${ctx.zoneName}).`),
        el("div", { class: "ov-grid" }, [runningCard(ctx), regionCard(ctx), nextDatesCard(ctx), versionsCard(ctx)]),
        agendaSection(ctx),
        insightsStrip(ctx),
        sourcesStrip(ctx)
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
