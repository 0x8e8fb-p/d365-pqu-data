/* My region: the station for an Azure region, its published sandbox and production windows, and
 * the dark-hours maintenance windows around each production weekend. Pairing a production
 * weekend with dark hours is a calculation; Microsoft publishes the two separately. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.views = PQU.views || {};
  const { el, visuallyHidden } = PQU.ui.dom;
  const dates = PQU.dates;
  const text = PQU.text;
  const windows = PQU.windows;
  const common = PQU.ui.common;
  const prefs = PQU.ui.prefs;

  const UNSCHEDULED_LIMIT = 3;
  let currentTitle = "My region";
  let shownRegion = null;

  function realRegions(ctx) {
    return ctx.regions.filter((row) => row.is_region);
  }

  function findRegion(ctx, name) {
    if (!name) {
      return null;
    }
    const list = realRegions(ctx);
    const wanted = text.normalizeSearch(name);
    return (
      list.find((row) => row.region === name) ||
      list.find((row) => text.normalizeSearch(row.region) === wanted) ||
      null
    );
  }

  function maintenanceDoc(ctx) {
    const doc = ctx.maintenance;
    if (!doc || !Array.isArray(doc.records)) {
      return null;
    }
    return doc.state === "current" || doc.state === "stale" ? doc : null;
  }

  function geoWindow(ctx, region) {
    const doc = maintenanceDoc(ctx);
    if (!doc || !region.maintenance_geo) {
      return null;
    }
    return doc.records.find((window) => window.geo === region.maintenance_geo) || null;
  }

  function missingWindowMessage(ctx, region) {
    if (!maintenanceDoc(ctx)) {
      return "Microsoft's maintenance windows are not available in this dataset.";
    }
    const finding = ctx.quality.find(
      (item) => item.field === `region.${region.region}` && String(item.code).startsWith("maintenance-geo-")
    );
    if (finding && finding.code === "maintenance-geo-unmapped") {
      return "Microsoft's planned maintenance table doesn't list a window for this cloud.";
    }
    return "No geography in Microsoft's planned maintenance table matches this region name.";
  }

  function yearFor(iso, todayIso) {
    return String(iso || "").slice(0, 4) !== String(todayIso).slice(0, 4);
  }

  function rangeText(startIso, endIso, todayIso) {
    return dates.formatDateRange(startIso, endIso, { weekday: true, year: yearFor(startIso, todayIso) });
  }

  /* "Sat 3 Oct 03:30 – 09:30 IST (Fri 2 Oct 22:00 UTC)": the viewer's time first, Microsoft's UTC
   * time after it. */
  function occurrenceText(ctx, occurrence) {
    const local = windows.rangeText(occurrence, ctx.zone, ctx.locale);
    const described = windows.describe(occurrence, ctx.zone, ctx.locale);
    return described.local ? `${local} (${described.utc})` : local;
  }

  /* ---- Picker ---- */

  function picker(ctx, selected) {
    const stationNumbers = [...new Set(ctx.regions.map((row) => row.station))].sort((a, b) => a - b);
    const input = el("input", {
      id: "region-search",
      type: "search",
      autocomplete: "off",
      placeholder: "For example North Europe",
      "aria-describedby": "region-search-status"
    });
    const status = el("p", { id: "region-search-status", class: "picker-status", "aria-live": "polite" });
    const cards = stationNumbers.map((station) => {
      const rows = ctx.regions.filter((row) => row.station === station);
      const regions = rows.filter((row) => row.is_region).sort((a, b) => a.region.localeCompare(b.region));
      const notes = rows.filter((row) => !row.is_region);
      return el(
        "section",
        { class: "station-card", dataset: { station: String(station) }, "aria-labelledby": `station-card-${station}` },
        [
          el("h3", { id: `station-card-${station}`, text: `Station ${station}` }),
          notes.map((row) => el("p", { class: "station-note", text: row.region })),
          regions.length
            ? el(
                "ul",
                { class: "region-links" },
                regions.map((row) =>
                  el("li", { dataset: { name: text.normalizeSearch(row.region) } }, [
                    el("a", {
                      href: PQU.router.href("region", { region: row.region }),
                      "aria-current": selected && selected.region === row.region ? "true" : null,
                      text: row.region,
                      on: { click: () => prefs.write("region", row.region) }
                    })
                  ])
                )
              )
            : null
        ]
      );
    });

    function filter() {
      const query = text.normalizeSearch(input.value);
      let count = 0;
      let last = null;
      for (const card of cards) {
        let visible = 0;
        for (const item of card.querySelectorAll("li")) {
          const show = !query || item.dataset.name.includes(query);
          item.hidden = !show;
          if (show) {
            visible += 1;
            last = item;
          }
        }
        card.hidden = Boolean(query) && visible === 0;
        count += visible;
      }
      status.textContent = !query
        ? ""
        : count === 0
          ? "No region matches."
          : `${text.plural(count, "matching region")}.`;
      return { count, last };
    }

    input.addEventListener("input", filter);
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        const { count, last } = filter();
        if (count === 1 && last) {
          event.preventDefault();
          last.querySelector("a").click();
        }
      }
    });

    const body = [
      el("label", { class: "field picker-field" }, [el("span", { text: "Find your Azure region" }), input]),
      status,
      el("div", { class: "station-grid", id: "station-grid" }, cards)
    ];
    if (selected) {
      return el("details", { class: "rules region-change", id: "region-change" }, [
        el("summary", {}, [el("span", { class: "rules-title", text: "Change region" })]),
        el("div", { class: "rules-body" }, body)
      ]);
    }
    return common.block("region-picker", "Regions by station", body);
  }

  /* ---- Selected region ---- */

  function saveLine(region) {
    const line = el("p", { class: "save-line", id: "region-save" });
    const draw = () => {
      if (prefs.read("region") === region.region) {
        line.replaceChildren(
          "Saved as your region. ",
          el("button", {
            type: "button",
            class: "button small",
            text: "Forget",
            on: {
              click: () => {
                prefs.write("region", null);
                draw();
              }
            }
          })
        );
      } else {
        line.replaceChildren(
          el("button", {
            type: "button",
            class: "button small",
            text: "Save as my region",
            on: {
              click: () => {
                prefs.write("region", region.region);
                draw();
              }
            }
          })
        );
      }
    };
    draw();
    return line;
  }

  function fact(label, value) {
    return el("div", {}, [el("dt", { text: label }), el("dd", {}, Array.isArray(value) ? value : [value])]);
  }

  function facts(ctx, region) {
    const peers = realRegions(ctx)
      .filter((row) => row.station === region.station && row.region !== region.region)
      .map((row) => row.region)
      .sort((a, b) => a.localeCompare(b));
    const window = geoWindow(ctx, region);
    let maintenance;
    if (window) {
      const next = windows.nextOccurrences(window, ctx.now, 1)[0];
      maintenance = [
        el("span", { text: `${window.geo} · ${windows.ruleText(window)}` }),
        el("span", { class: "fact-note", text: "Geography matched from the region name." }),
        next ? common.calc(`Next: ${occurrenceText(ctx, next)}`, { class: "fact-note" }) : null
      ];
    } else {
      maintenance = [el("span", { class: "muted", text: missingWindowMessage(ctx, region) })];
    }
    return el("dl", { class: "facts region-facts", id: "region-facts" }, [
      fact("Station", `Station ${region.station}`),
      fact(`Also on Station ${region.station}`, peers.length ? text.joinList(peers) : "No other regions"),
      fact("Maintenance window (dark hours)", maintenance)
    ]);
  }

  function windowCell(label, startIso, endIso, state, todayIso) {
    return el("td", { dataset: { kind: label.toLowerCase() }, "data-label": label }, [
      el("span", {
        class: "window-dates",
        text: startIso ? rangeText(startIso, endIso, todayIso) : "N/A in Microsoft's schedule"
      }),
      state
        ? el("span", { class: ["window-state", `state-${state.state}`] }, [visuallyHidden("Calculated: "), state.text])
        : null
    ]);
  }

  function darkHoursCell(ctx, window, row) {
    const label = `${window.geo} dark hours`;
    if (!row.production_start_date) {
      return el("td", { class: "muted", "data-label": label, text: "No production window" });
    }
    const pair = windows.forRange(window, row.production_start_date, row.production_end_date);
    if (!pair.paired) {
      return el("td", { "data-label": label }, [
        el("p", { class: "dark-hours-rule", text: `${window.geo} maintenance window: ${windows.ruleText(window)}` })
      ]);
    }
    return el("td", { "data-label": label }, [
      el(
        "ul",
        { class: "dark-hours calc" },
        pair.windows.map((occurrence) => {
          const state = windows.occurrenceState(occurrence, ctx.now);
          return el("li", { class: ["occ", `occ-${state}`] }, [
            occurrenceText(ctx, occurrence),
            state === "now" ? [" ", common.tag("Now", "now")] : null,
            state === "done" ? visuallyHidden(" (passed)") : null
          ]);
        })
      )
    ]);
  }

  function windowRow(ctx, region, item) {
    const record = ctx.recordsById[item.row.pqu_id] || { pqu_id: item.row.pqu_id };
    const current =
      (item.sandbox && item.sandbox.state === "current") ||
      (item.production && item.production.state === "current");
    const window = geoWindow(ctx, region);
    return el("tr", { class: ["window-row", current ? "is-current" : null], dataset: { pqu: record.pqu_id } }, [
      el("th", { scope: "row", class: "window-train" }, [
        common.trainLink(record.pqu_id),
        record.status ? [" ", common.statusText(record.status)] : null,
        common.newTag(record),
        record.application_build ? el("span", { class: "build", text: `Build ${record.application_build}` }) : null
      ]),
      windowCell("Sandbox", item.row.sandbox_start_date, item.row.sandbox_end_date, item.sandbox, ctx.todayIso),
      windowCell(
        "Production",
        item.row.production_start_date,
        item.row.production_end_date,
        item.production,
        ctx.todayIso
      ),
      window ? darkHoursCell(ctx, window, item.row) : null
    ]);
  }

  function windowTable(ctx, region, items, id, caption) {
    const window = geoWindow(ctx, region);
    return el("div", { class: "table-scroll" }, [
      el("table", { class: "window-table stack-table", id }, [
        el("caption", { class: "visually-hidden", text: caption }),
        el("thead", {}, [
          el("tr", {}, [
            el("th", { scope: "col", text: "Train" }),
            el("th", { scope: "col", text: "Sandbox" }),
            el("th", { scope: "col", text: "Production" }),
            window ? el("th", { scope: "col", text: `${window.geo} dark hours that weekend` }) : null
          ])
        ]),
        el(
          "tbody",
          {},
          items.map((item) => windowRow(ctx, region, item))
        )
      ])
    ]);
  }

  function unscheduled(ctx) {
    const list = ctx.records
      .filter(
        (record) =>
          !record.station_schedule_available &&
          (record.status === "Not Started" || record.status === "In-Progress") &&
          dates.isIsoDate(record.train_start_date)
      )
      .sort(
        (a, b) =>
          a.train_start_date.localeCompare(b.train_start_date) ||
          PQU.versions.compareVersions(a.application_version, b.application_version)
      );
    if (!list.length) {
      return null;
    }
    const notStarted = ctx.records.filter((record) => record.status === "Not Started").length;
    return common.block("region-unscheduled", "Detailed schedule not published yet", [
      el("p", {
        class: "note",
        text: "Microsoft publishes station windows shortly before a train starts. These trains come next."
      }),
      el(
        "ul",
        { class: "ruled-list", id: "unscheduled" },
        list.slice(0, UNSCHEDULED_LIMIT).map((record) =>
          el("li", {}, [
            common.trainLink(record.pqu_id),
            " ",
            common.statusText(record.status),
            ` · train starts ${dates.formatDate(record.train_start_date, {
              weekday: true,
              year: yearFor(record.train_start_date, ctx.todayIso)
            })}, `,
            common.calc(dates.daysPhrase(dates.diffDays(ctx.todayIso, record.train_start_date)))
          ])
        )
      ),
      list.length > UNSCHEDULED_LIMIT && notStarted
        ? el("p", {}, [
            el("a", {
              href: PQU.router.href("trains", {}, { status: "Not Started" }),
              text: `All ${text.plural(notStarted, "Not Started train")}`
            })
          ])
        : null
    ]);
  }

  function introBlocks(ctx) {
    const article = PQU.ui.rich.article(ctx.learn, "schedule");
    const intro = article && article.sections.find((section) => section.id === "intro");
    return intro ? intro.blocks.filter((block) => block.type === "paragraph") : [];
  }

  function introNote(ctx) {
    const article = PQU.ui.rich.article(ctx.learn, "schedule");
    const blocks = introBlocks(ctx);
    if (!article || !blocks.length) {
      return null;
    }
    return el("figure", { class: "excerpt", id: "region-intro" }, [
      el("blockquote", { class: "prose", cite: article.url }, PQU.ui.rich.blocks(blocks)),
      el("figcaption", {}, [PQU.ui.guidance.sourceLine(article, { class: "source-line" })])
    ]);
  }

  function rulesPanel(ctx, { includeIntro = true } = {}) {
    const rich = PQU.ui.rich;
    const article = rich.article(ctx.learn, "schedule");
    if (!article) {
      return null;
    }
    const callouts = rich.callouts(article).map(({ block }) => block);
    return PQU.ui.guidance.panel({
      id: "region-rules",
      title: includeIntro ? "How Microsoft schedules your updates" : "Microsoft's rollout rules",
      article,
      blocks: [...(includeIntro ? introBlocks(ctx) : []), ...callouts],
      summaryNote: "Microsoft Learn"
    });
  }

  function stationSection(ctx, region) {
    const rows = ctx.stations.filter((row) => row.station === region.station);
    const plan = windows.stationSchedule(rows, ctx.todayIso);
    const window = geoWindow(ctx, region);
    const children = [];
    if (ctx.errors.stations) {
      children.push(el("p", { class: "inline-alert", text: "Station schedules could not be loaded." }));
    } else if (!plan.active.length) {
      children.push(
        el("p", {
          class: "muted",
          text: `No current or upcoming Station ${region.station} windows in Microsoft's schedule.`
        })
      );
    } else {
      children.push(
        windowTable(
          ctx,
          region,
          plan.active,
          "window-list",
          `Current and upcoming Station ${region.station} windows, with the dark hours of each production weekend`
        )
      );
    }
    if (window && plan.active.length) {
      children.push(
        common.calcNote(
          `Dark hours pair Microsoft's production dates with its ${window.geo} maintenance window, in ${ctx.zoneName} ` +
            "and UTC. Microsoft doesn't say which of these windows updates a given environment."
        )
      );
    }
    if (plan.past.length) {
      children.push(
        el("details", { class: "rules past-windows", id: "past-windows" }, [
          el("summary", {}, [
            el("span", { class: "rules-title", text: "Earlier windows" }),
            el("span", { class: "muted", text: ` · ${plan.past.length}` })
          ]),
          el("div", { class: "rules-body" }, [
            windowTable(ctx, region, plan.past, "past-window-list", `Earlier Station ${region.station} windows`)
          ])
        ])
      );
    }
    return common.block("station-windows", `Station ${region.station} windows`, children);
  }

  function calendarSection(ctx, region) {
    const calendar = PQU.ui.calendar;
    return common.block(
      "region-calendar",
      "Add to your calendar",
      [
        el("div", { class: "calendar-blocks" }, [
          calendar.stationBlock(ctx, region.station, "region-calendar"),
          calendar.milestonesBlock(ctx, "region-calendar")
        ]),
        calendar.help()
      ],
      { class: "calendar-section" }
    );
  }

  function render(container, ctx, route) {
    let name = route && route.params ? route.params.region : null;
    if (!name) {
      const saved = findRegion(ctx, prefs.read("region"));
      if (saved) {
        name = saved.region;
        try {
          root.history.replaceState(root.history.state, "", PQU.router.href("region", { region: name }));
        } catch (error) {
          /* The page still shows the saved region; only the address bar is not updated. */
        }
      }
    }
    const region = findRegion(ctx, name);
    shownRegion = region;
    const notices = [];
    if (ctx.errors.regions) {
      notices.push(el("p", { class: "inline-alert", text: "The region mapping could not be loaded." }));
    }
    if (name && !region && !ctx.errors.regions) {
      notices.push(
        el("p", {
          class: "inline-alert",
          text: `${name} is not in Microsoft's station-to-region mapping. Choose a region below.`
        })
      );
    }
    if (!region) {
      currentTitle = "My region";
      container.replaceChildren(
        el("div", { class: "page region" }, [
          common.pageHead({
            id: "region-heading",
            title: "Find your update windows",
            sub: "Microsoft updates Azure regions in groups called stations. Pick your region to see its station's sandbox and production windows and the dark hours around them."
          }),
          ...notices,
          introNote(ctx),
          picker(ctx, null),
          rulesPanel(ctx, { includeIntro: false })
        ])
      );
      return;
    }
    currentTitle = `${region.region} · My region`;
    container.replaceChildren(
      el("div", { class: "page region" }, [
        common.pageHead({ id: "region-heading", title: region.region, aside: saveLine(region) }),
        ...notices,
        facts(ctx, region),
        common.italicNote(ctx),
        stationSection(ctx, region),
        calendarSection(ctx, region),
        unscheduled(ctx),
        el("p", { class: "region-links-line" }, [
          el("a", {
            href: PQU.router.href("trains", {}, { region: region.region }),
            text: `All trains with Station ${region.station} windows`
          })
        ]),
        rulesPanel(ctx),
        picker(ctx, region)
      ])
    );
  }

  PQU.views.region = {
    name: "region",
    label: "My region",
    documents: ["stations", "regions", "maintenance", "learn", "events"],
    title: () => currentTitle,
    // Dark-hours windows are marked as running or passed, so the page changes when one starts
    // or ends.
    nextChange: (ctx) => {
      const window = shownRegion ? geoWindow(ctx, shownRegion) : null;
      return window ? windows.nextBoundary(window, ctx.now) : null;
    },
    render
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
