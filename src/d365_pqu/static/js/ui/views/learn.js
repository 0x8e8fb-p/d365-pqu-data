/* Learn: Microsoft's own explanation of PQUs, rollouts and maintenance, next to the published
 * data it describes. Every text block is Microsoft Learn content with attribution; schedules and
 * windows come from the published datasets; states and figures are calculated (in italics). */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.views = PQU.views || {};
  const { el, extLink, visuallyHidden } = PQU.ui.dom;
  const dates = PQU.dates;
  const text = PQU.text;
  const windows = PQU.windows;
  const rich = PQU.ui.rich;
  const guidance = PQU.ui.guidance;
  const common = PQU.ui.common;
  const prefs = PQU.ui.prefs;

  let currentTitle = "Learn";
  let rolloutTrain = null;
  let faqQuery = "";

  /* ---- Shared pieces ---- */

  function sourceEntry(ctx, key) {
    const sources = (ctx.metadata && ctx.metadata.sources) || {};
    return sources[key] || null;
  }

  function staleNotice(ctx, key) {
    const entry = sourceEntry(ctx, key);
    if (!entry || entry.state !== "stale" || !entry.source) {
      return null;
    }
    const retrieved = String(entry.source.retrieved_at || "").slice(0, 10);
    return el("p", {
      class: "inline-alert",
      text:
        `The latest copy of “${entry.label}” could not be read. ` +
        `Showing the copy retrieved ${dates.formatDate(retrieved)}.`
    });
  }

  function missingArticle(ctx, key) {
    if (ctx.errors.learn) {
      return el("p", { class: "muted", text: "Microsoft's text for this part is not available." });
    }
    const entry = sourceEntry(ctx, key);
    const label = entry ? entry.label : "This Microsoft article";
    if (entry && entry.state === "unavailable") {
      return el("p", {
        class: "inline-alert",
        text: `“${label}” could not be retrieved from Microsoft, so this part is not shown.`
      });
    }
    return el("p", { class: "muted", text: `“${label}” is not part of this dataset.` });
  }

  function introBlocks(article) {
    const intro = article && article.sections.find((section) => section.id === "intro");
    return intro ? intro.blocks.filter((block) => block.type !== "dataset") : [];
  }

  /* Microsoft's words, quoted with their source. */
  function excerpt(article, blocks, props = {}) {
    const rendered = rich.blocks(blocks);
    if (!article || !rendered.length) {
      return null;
    }
    return el("figure", { class: "excerpt", ...props }, [
      el("blockquote", { class: "prose", cite: article.url }, rendered),
      el("figcaption", {}, [guidance.sourceLine(article, { class: "source-line" })])
    ]);
  }

  function section(id, title, children) {
    return el("section", { class: "learn-section", id, "aria-labelledby": `${id}-heading` }, [
      el("div", { class: "block-head" }, [el("h2", { id: `${id}-heading`, tabindex: "-1", text: title })]),
      ...children
    ]);
  }

  /* Nest deeper headings under the section before them (h3 under h2). */
  function groupSections(sections) {
    const groups = [];
    let parent = null;
    for (const item of sections) {
      if (parent && item.level > parent.level) {
        parent.children.push(item);
      } else {
        parent = { ...item, children: [] };
        groups.push(parent);
      }
    }
    return groups;
  }

  function searchText(group) {
    return text.normalizeSearch(
      [
        group.title,
        rich.plainText(group.blocks),
        ...group.children.map((child) => `${child.title} ${rich.plainText(child.blocks)}`)
      ].join(" ")
    );
  }

  function qaItem(group, options = {}) {
    const summary = el("summary", { dataset: options.focus ? { focusTarget: "" } : null }, [
      el("span", { class: "qa-question", text: group.title })
    ]);
    const links = [];
    if (options.faq) {
      links.push(el("a", { href: PQU.router.href("learn", { faq: group.id }), text: "Link to this answer" }));
      links.push(" · ");
    }
    links.push(extLink(group.url, "Open on Microsoft Learn"));
    const details = el(
      "details",
      {
        class: "qa-item",
        id: `${options.prefix || "qa"}-${group.id}`,
        open: Boolean(options.open),
        dataset: { slug: group.id, search: searchText(group) }
      },
      [
        summary,
        el("div", { class: "qa-answer prose" }, [
          ...rich.blocks(group.blocks),
          ...group.children.map((child) =>
            el("section", { class: "qa-sub", "aria-label": child.title }, [
              el(options.subHeading || "h4", { text: child.title }),
              ...rich.blocks(child.blocks)
            ])
          ),
          el("p", { class: "qa-links" }, links)
        ])
      ]
    );
    if (options.faq) {
      details.addEventListener("toggle", () => onFaqToggle(details, group));
    }
    return details;
  }

  /* Opening an answer puts its link in the address bar; closing it restores the page link. */
  function onFaqToggle(details, group) {
    if (PQU.app.isRestoring(details)) {
      return;
    }
    const answer = PQU.router.href("learn", { faq: group.id });
    const page = PQU.router.href("learn");
    if (details.open && root.location.hash !== answer) {
      PQU.app.replaceHash(answer);
      currentTitle = `${group.title} · Learn`;
    } else if (!details.open && root.location.hash === answer) {
      PQU.app.replaceHash(page);
      currentTitle = "Learn";
    } else {
      return;
    }
    PQU.app.setTitle(currentTitle);
  }

  /* ---- PQUs in brief ---- */

  function briefSection(ctx) {
    const article = rich.article(ctx.learn, "pqu_overview");
    const children = [staleNotice(ctx, "pqu_overview")];
    if (!article) {
      children.push(missingArticle(ctx, "pqu_overview"));
    } else {
      const items = article.sections
        .filter((item) => item.id !== "intro" && item.blocks.length)
        .map((item) =>
          el("article", { class: "brief-item", "aria-labelledby": `brief-${item.id}` }, [
            el("h3", { id: `brief-${item.id}`, text: item.title }),
            el("div", { class: "prose" }, rich.blocks(item.blocks)),
            el("p", { class: "card-link" }, [extLink(item.url, "Read on Microsoft Learn")])
          ])
        );
      children.push(el("div", { class: "brief", id: "brief-cards" }, items));
      children.push(guidance.sourceLine(article, { class: "source-line" }));
    }
    return section("learn-brief", "PQUs in brief", children);
  }

  /* ---- How a rollout works ---- */

  function yearNeeded(iso, todayIso) {
    return String(iso || "").slice(0, 4) !== String(todayIso).slice(0, 4);
  }

  function windowLine(ctx, label, startIso, endIso) {
    const state = windows.rangeState(startIso, endIso, ctx.todayIso);
    return el("p", { class: "step-window" }, [
      el("span", { class: "window-kind", text: label }),
      " ",
      el("span", {
        class: "window-dates",
        text: startIso ? dates.formatDateRange(startIso, endIso, { year: yearNeeded(startIso, ctx.todayIso) }) : "N/A"
      }),
      state
        ? [" ", el("span", { class: ["window-state", `state-${state.state}`] }, [visuallyHidden("Calculated: "), state.text])]
        : null
    ]);
  }

  /* Whether the selected train has reached, is at, or has passed a station today. */
  function stopState(ctx, row) {
    if (!row) {
      return null;
    }
    const states = ["sandbox", "production"]
      .map((kind) => windows.rangeState(row[`${kind}_start_date`], row[`${kind}_end_date`], ctx.todayIso))
      .filter(Boolean);
    if (states.some((state) => state.state === "current")) {
      return "is-current";
    }
    return states.length && states.every((state) => state.state === "done") ? "is-done" : null;
  }

  function rolloutStep(ctx, station, pquId, savedRegion) {
    const rows = ctx.regions.filter((row) => row.station === station);
    const regions = rows.filter((row) => row.is_region).sort((a, b) => a.region.localeCompare(b.region));
    const notes = rows.filter((row) => !row.is_region).map((row) => row.region);
    const yours = Boolean(savedRegion && savedRegion.station === station);
    const windowRow = (ctx.stationsByTrain[pquId] || []).find((row) => row.station === station);
    return el(
      "li",
      { class: ["step", yours ? "is-yours" : null, stopState(ctx, windowRow)], dataset: { station: String(station) } },
      [
        el("div", { class: "step-head" }, [
          el("h3", { text: `Station ${station}` }),
          yours ? common.tag("Your station", "yours") : null
        ]),
        notes.map((note) => el("p", { class: "step-note", text: note })),
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
          : null,
        windowRow
          ? el("div", { class: "step-windows" }, [
              windowLine(ctx, "Sandbox", windowRow.sandbox_start_date, windowRow.sandbox_end_date),
              windowLine(ctx, "Production", windowRow.production_start_date, windowRow.production_end_date)
            ])
          : el("p", { class: "muted step-window", text: "Not in this train's schedule." })
      ]
    );
  }

  function rolloutSection(ctx) {
    const schedule = rich.article(ctx.learn, "schedule");
    const stationNumbers = [
      ...new Set([...ctx.regions.map((row) => row.station), ...ctx.stations.map((row) => row.station)])
    ].sort((a, b) => a - b);
    const trains = ctx.records
      .filter((record) => (ctx.stationsByTrain[record.pqu_id] || []).length)
      .sort(
        (a, b) =>
          String(b.train_start_date || "").localeCompare(String(a.train_start_date || "")) ||
          PQU.versions.compareVersions(b.application_version, a.application_version)
      );
    const latest = ctx.metadata && ctx.metadata.latest_pqu_id;
    if (!trains.some((record) => record.pqu_id === rolloutTrain)) {
      rolloutTrain = trains.some((record) => record.pqu_id === latest)
        ? latest
        : trains.length
          ? trains[0].pqu_id
          : null;
    }
    const saved = prefs.read("region");
    const savedRegion = ctx.regions.find((row) => row.is_region && row.region === saved) || null;
    const steps = el("ol", {
      class: "station-line",
      id: "rollout-steps",
      "aria-label": "Stations in rollout order"
    });
    const draw = () =>
      steps.replaceChildren(...stationNumbers.map((station) => rolloutStep(ctx, station, rolloutTrain, savedRegion)));
    draw();

    const children = [];
    if (schedule) {
      children.push(excerpt(schedule, introBlocks(schedule), { id: "rollout-intro" }));
    } else {
      children.push(missingArticle(ctx, "schedule"));
    }
    if (trains.length) {
      const select = el(
        "select",
        {
          id: "rollout-train",
          on: {
            change: (event) => {
              rolloutTrain = event.target.value;
              draw();
            }
          }
        },
        trains.map((record) =>
          el("option", {
            value: record.pqu_id,
            selected: record.pqu_id === rolloutTrain,
            text: `${text.trainLabel(record.pqu_id)} · ${record.status}`
          })
        )
      );
      children.push(
        el("div", { class: "rollout-controls" }, [
          el("label", { class: "field" }, [el("span", { text: "Follow a train through the stations" }), select]),
          savedRegion
            ? el("p", { class: "muted", text: `Your region: ${savedRegion.region} (Station ${savedRegion.station}).` })
            : el("p", { class: "muted" }, [
                el("a", { href: PQU.router.href("region"), text: "Pick your region" }),
                " to mark your station."
              ])
        ])
      );
    }
    children.push(steps);
    children.push(
      common.calcNote([
        el("i", { text: "Italic" }),
        ` states are calculated from Microsoft's published dates for ${ctx.todayLabel} (${ctx.zoneName}). Filled stops have finished; the highlighted stop is in progress today.`
      ])
    );
    if (schedule) {
      const callouts = rich.callouts(schedule).map(({ block }) => block);
      if (callouts.length) {
        children.push(el("h3", { class: "subhead", text: "Microsoft's rollout rules" }));
        children.push(
          el("div", { class: "rollout-rules prose", id: "rollout-rules" }, [
            ...rich.blocks(callouts),
            guidance.sourceLine(schedule, { class: "source-line" })
          ])
        );
      }
    }
    return section("learn-rollout", "How a rollout works", children);
  }

  /* ---- Maintenance windows ---- */

  function maintenanceDoc(ctx) {
    const doc = ctx.maintenance;
    return doc && Array.isArray(doc.records) && (doc.state === "current" || doc.state === "stale") ? doc : null;
  }

  function maintenanceTable(ctx, doc) {
    const saved = prefs.read("region");
    const savedRegion = ctx.regions.find((row) => row.is_region && row.region === saved) || null;
    const regionsByGeo = {};
    for (const row of ctx.regions) {
      if (row.maintenance_geo) {
        (regionsByGeo[row.maintenance_geo] = regionsByGeo[row.maintenance_geo] || []).push(row.region);
      }
    }
    const rows = doc.records.map((window) => {
      const next = windows.nextOccurrences(window, ctx.now, 2);
      const yours = Boolean(savedRegion && savedRegion.maintenance_geo === window.geo);
      const matched = (regionsByGeo[window.geo] || []).slice().sort((a, b) => a.localeCompare(b));
      return el("tr", { class: yours ? "is-yours" : null, dataset: { geo: window.geo } }, [
        el("th", { scope: "row" }, [window.geo, yours ? common.tag("Your region", "yours") : null]),
        el("td", { text: text.joinList(window.days || []) }),
        el("td", { class: "nowrap", text: window.start_time_utc }),
        el("td", { class: "nowrap", text: window.duration_text || "—" }),
        el(
          "td",
          { class: "next-windows calc" },
          next.length
            ? el(
                "ul",
                {},
                next.map((occurrence) =>
                  el("li", {
                    class: `occ-${windows.occurrenceState(occurrence, ctx.now)}`,
                    text: windows.rangeText(occurrence, ctx.zone, ctx.locale)
                  })
                )
              )
            : "—"
        ),
        el("td", { class: "muted", text: matched.length ? matched.join(", ") : "—" })
      ]);
    });
    const headers = [
      "Geography",
      "Days (UTC)",
      "Start (UTC)",
      "Length",
      `Next windows (${ctx.zoneName})`,
      "Azure regions (matched by name)"
    ];
    return el("div", { class: "table-scroll" }, [
      el("table", { id: "maintenance-table", class: "maint-table" }, [
        el("caption", {
          class: "visually-hidden",
          text: `Microsoft's planned maintenance windows by geography in UTC, with the next two windows in ${ctx.zoneName}.`
        }),
        el("thead", {}, [el("tr", {}, headers.map((label) => el("th", { scope: "col", text: label })))]),
        el("tbody", {}, rows)
      ])
    ]);
  }

  function maintenanceSection(ctx) {
    const article = rich.article(ctx.learn, "maintenance");
    const doc = maintenanceDoc(ctx);
    const children = [staleNotice(ctx, "maintenance")];
    if (article) {
      children.push(excerpt(article, introBlocks(article), { id: "maintenance-intro" }));
    }
    const context = article
      ? guidance.datasetContext(article, "maintenance_windows")
      : { section: null, before: [], after: [] };
    if (context.before.length) {
      children.push(el("div", { class: "prose section-lead" }, rich.blocks(context.before)));
    }
    if (doc && doc.records.length) {
      children.push(maintenanceTable(ctx, doc));
      children.push(
        common.calcNote(
          "Next windows are calculated from Microsoft's UTC times for your time zone; regions are matched to geographies by name."
        )
      );
    } else {
      children.push(el("p", { class: "muted", text: "Microsoft's maintenance windows are not available in this dataset." }));
    }
    if (context.after.length) {
      children.push(el("div", { class: "prose" }, rich.blocks(context.after)));
    }
    if (article) {
      const rest = article.sections.filter((item) => item.id !== "intro" && item !== context.section);
      const groups = groupSections(rest);
      if (groups.length) {
        children.push(el("h3", { class: "subhead", text: "Questions about maintenance" }));
        children.push(
          el(
            "div",
            { class: "qa-list", id: "maintenance-qa" },
            groups.map((group) => qaItem(group, { prefix: "maintenance", subHeading: "h4" }))
          )
        );
      }
      children.push(guidance.sourceLine(article, { class: "source-line" }));
    } else {
      children.push(missingArticle(ctx, "maintenance"));
    }
    return section("learn-maintenance", "Maintenance windows (dark hours)", children);
  }

  /* ---- What the data says ---- */

  function valueText(record) {
    const value = Number.isInteger(record.value) ? String(record.value) : Number(record.value).toFixed(1);
    const unit = record.value === 1 ? String(record.unit).replace(/s$/, "") : record.unit;
    return `${value} ${unit}`;
  }

  /* "16 intervals, 14–21 days" for medians; nothing for counts. */
  function basisText(record, metric) {
    if (record.statistic !== "median" || !metric || !metric.sample_unit) {
      return "";
    }
    const unit = record.sample_size === 1 ? metric.sample_unit.replace(/s$/, "") : metric.sample_unit;
    const range = record.min !== record.max ? `, ${record.min}\u2013${record.max} ${record.unit}` : "";
    return `${record.sample_size} ${unit}${range}`;
  }

  function joinNodes(parts) {
    const nodes = [];
    parts.forEach((part, index) => {
      if (index > 0) {
        nodes.push(index === parts.length - 1 ? " and " : ", ");
      }
      nodes.push(...part);
    });
    return nodes;
  }

  function sourcesLine(ctx, keys) {
    const sources = (ctx.metadata && ctx.metadata.sources) || {};
    const parts = keys
      .map((key) => sources[key])
      .filter(Boolean)
      .map((entry) => {
        const updated =
          entry.source && entry.source.markdown_date ? ` (updated ${dates.formatDate(entry.source.markdown_date)})` : "";
        const stale = entry.state === "stale" ? ", last published copy" : "";
        return [extLink(entry.article_url, entry.label), `${updated}${stale}`];
      });
    return parts.length ? el("p", { class: "source-line" }, ["Calculated from ", ...joinNodes(parts), "."]) : null;
  }

  function leftOut(metric, records) {
    const seen = new Set();
    const items = [];
    for (const entry of [...(metric.excluded || []), ...records.flatMap((record) => record.excluded || [])]) {
      const key = `${entry.item}\u0000${entry.reason}`;
      if (!seen.has(key)) {
        seen.add(key);
        items.push(entry);
      }
    }
    return items;
  }

  function methodDetails(metrics, recordsByMetric) {
    return el("details", { class: "insight-method" }, [
      el("summary", { text: "How these figures are calculated" }),
      el(
        "div",
        { class: "prose" },
        metrics.map((metric) => {
          const items = leftOut(metric, recordsByMetric[metric.id]);
          return el("div", { class: "method-item" }, [
            el("p", {}, [el("strong", { text: `${metric.title}. ` }), metric.method]),
            items.length
              ? el("ul", { class: "left-out" }, items.map((entry) => el("li", { text: `Left out ${entry.item}: ${entry.reason}` })))
              : null
          ]);
        })
      )
    ]);
  }

  function insightTable(category, metrics, recordsByMetric) {
    const groups = [];
    const seen = new Set();
    for (const metric of metrics) {
      for (const record of recordsByMetric[metric.id]) {
        if (record.group !== "all" && !seen.has(record.group)) {
          seen.add(record.group);
          groups.push({ group: record.group, label: record.label });
        }
      }
    }
    const cell = (metric, group) => {
      const record = recordsByMetric[metric.id].find((item) => item.group === group);
      if (!record) {
        return el("td", { class: "muted", text: "—" });
      }
      const basis = basisText(record, metric);
      return el("td", { class: "calc", title: record.summary }, [
        el("span", { class: "cell-value", text: valueText(record) }),
        basis ? el("span", { class: "cell-note", text: basis }) : null
      ]);
    };
    return el("div", { class: "table-scroll" }, [
      el("table", { class: "insight-table", id: `insight-table-${category.id}` }, [
        el("caption", { class: "visually-hidden", text: `${category.title}: calculated from Microsoft's published dates` }),
        el("thead", {}, [
          el("tr", {}, [
            el("th", { scope: "col", text: category.group_label }),
            ...metrics.map((metric) => el("th", { scope: "col", text: metric.title }))
          ])
        ]),
        el(
          "tbody",
          {},
          groups.map((item) =>
            el("tr", { dataset: { group: item.group } }, [
              el("th", { scope: "row", text: item.label }),
              ...metrics.map((metric) => cell(metric, item.group))
            ])
          )
        )
      ])
    ]);
  }

  function insightBlock(ctx, doc, category) {
    const metrics = doc.metrics.filter((metric) => metric.category === category.id);
    const recordsByMetric = {};
    for (const metric of metrics) {
      recordsByMetric[metric.id] = doc.records.filter((record) => record.metric === metric.id);
    }
    const shown = metrics.filter((metric) => recordsByMetric[metric.id].length);
    if (!shown.length) {
      return null;
    }
    const overall = shown.flatMap((metric) => recordsByMetric[metric.id].filter((record) => record.group === "all"));
    const grouped = shown.filter((metric) => recordsByMetric[metric.id].some((record) => record.group !== "all"));
    const children = [el("h3", { id: `insights-${category.id}-title`, text: category.title })];
    if (grouped.length) {
      children.push(...overall.map((record) => el("p", { class: "insight-lead calc", text: record.summary })));
      children.push(insightTable(category, grouped, recordsByMetric));
    } else {
      const metricsById = Object.fromEntries(shown.map((metric) => [metric.id, metric]));
      children.push(
        el(
          "dl",
          { class: "insight-list" },
          overall.map((record) =>
            el("div", { dataset: { insight: record.id } }, [
              el("dt", { text: metricsById[record.metric].title }),
              el("dd", { class: "calc" }, [
                el("span", { class: "cell-value", text: valueText(record) }),
                el("span", { class: "cell-note", text: basisText(record, metricsById[record.metric]) })
              ])
            ])
          )
        )
      );
    }
    children.push(methodDetails(shown, recordsByMetric));
    children.push(sourcesLine(ctx, [...new Set(shown.flatMap((metric) => metric.sources || []))]));
    return el(
      "section",
      { class: "insight", id: `insights-${category.id}`, "aria-labelledby": `insights-${category.id}-title` },
      children
    );
  }

  function insightsSection(ctx) {
    const doc = ctx.insights;
    if (!doc || !Array.isArray(doc.records)) {
      return section("learn-insights", "What the data says", [
        el("p", {
          class: ctx.errors.insights ? "inline-alert" : "muted",
          text: ctx.errors.insights ? "The calculated figures could not be loaded." : "No calculated figures are available."
        })
      ]);
    }
    if (!doc.records.length) {
      return section("learn-insights", "What the data says", [
        el("p", { class: "muted", text: "There is not enough published data to calculate figures." })
      ]);
    }
    const metricsById = Object.fromEntries(doc.metrics.map((metric) => [metric.id, metric]));
    const recordsById = Object.fromEntries(doc.records.map((record) => [record.id, record]));
    const figures = (doc.highlights || [])
      .map((id) => recordsById[id])
      .filter(Boolean)
      .map((record) => {
        const metric = metricsById[record.metric] || { title: record.metric };
        return el("li", { class: "figure-item", dataset: { insight: record.id } }, [
          el("p", { class: "figure-value calc", text: valueText(record) }),
          el("p", {
            class: "figure-title",
            text: record.group === "all" ? metric.title : `${metric.title} · ${record.label}`
          }),
          el("p", { class: "figure-summary", text: record.summary })
        ]);
      });
    return section("learn-insights", "What the data says", [
      common.calcNote(
        "These figures are calculated from Microsoft's published dates. Microsoft doesn't publish them; each part says how it is calculated and what was left out."
      ),
      figures.length ? el("ul", { class: "figures", id: "insight-highlights" }, figures) : null,
      ...(doc.categories || []).map((category) => insightBlock(ctx, doc, category)).filter(Boolean)
    ]);
  }

  /* ---- FAQ ---- */

  function faqSection(ctx, route) {
    const article = rich.article(ctx.learn, "pqu_faq");
    const children = [staleNotice(ctx, "pqu_faq")];
    if (!article) {
      children.push(missingArticle(ctx, "pqu_faq"));
      return { node: section("learn-faq", "Frequently asked questions", children), found: null };
    }
    const wanted = route && route.params ? route.params.faq : null;
    const groups = groupSections(article.sections.filter((item) => item.id !== "intro"));
    const questions = groups.filter((group) => group.title.trim().endsWith("?"));
    const others = groups.filter((group) => !questions.includes(group));
    const found = wanted ? questions.find((group) => group.id === wanted || group.aliases.includes(wanted)) : null;
    if (wanted && !found) {
      children.push(el("p", { class: "inline-alert", text: "That question is not in Microsoft's current FAQ." }));
    }
    children.push(excerpt(article, introBlocks(article), { id: "faq-intro" }));

    const status = el("p", { class: "faq-status", id: "faq-status", "aria-live": "polite" });
    const list = el(
      "div",
      { class: "qa-list", id: "faq-list" },
      questions.map((group) =>
        qaItem(group, { prefix: "faq", faq: true, open: group === found, focus: group === found, subHeading: "h3" })
      )
    );
    const filter = () => {
      const query = text.normalizeSearch(faqQuery);
      let shown = 0;
      for (const item of list.children) {
        const match = !query || item.dataset.search.includes(query);
        item.hidden = !match;
        if (match) {
          shown += 1;
        }
      }
      status.textContent = !query
        ? `${text.plural(questions.length, "question")} from Microsoft's FAQ.`
        : shown
          ? `${shown} of ${text.plural(questions.length, "question")} match.`
          : "No questions match.";
    };
    const search = el("input", {
      id: "faq-search",
      type: "search",
      autocomplete: "off",
      placeholder: "For example weekday, Station 1, or rollback",
      value: faqQuery,
      on: {
        input: (event) => {
          faqQuery = event.target.value;
          filter();
        }
      }
    });
    if (found) {
      faqQuery = "";
      search.value = "";
    }
    filter();
    children.push(
      el("div", { class: "faq-tools" }, [
        el("label", { class: "field" }, [el("span", { text: "Search the questions" }), search]),
        status
      ])
    );
    children.push(list);
    for (const group of others) {
      children.push(
        el("div", { class: "faq-extra prose" }, [el("h3", { text: group.title }), ...rich.blocks(group.blocks)])
      );
    }
    children.push(guidance.sourceLine(article, { class: "source-line" }));
    return { node: section("learn-faq", "Frequently asked questions", children), found };
  }

  /* ---- Page ---- */

  function jumpNav(parts) {
    return el("nav", { class: "jump-nav", "aria-label": "On this page" }, [
      el("p", { class: "jump-title", text: "On this page" }),
      el(
        "ul",
        {},
        parts.map((part) =>
          el("li", {}, [
            el("button", {
              type: "button",
              class: "link-button",
              text: part.label,
              on: {
                click: () => {
                  const target = document.getElementById(part.id);
                  if (target) {
                    target.scrollIntoView({ block: "start", behavior: "instant" });
                    const heading = target.querySelector("h2");
                    if (heading) {
                      heading.focus({ preventScroll: true });
                    }
                  }
                }
              }
            })
          ])
        )
      )
    ]);
  }

  function licenseNote(ctx) {
    const license = ctx.learn && ctx.learn.license;
    if (!license) {
      return null;
    }
    return el("p", { class: "license-note", id: "learn-license" }, [
      `${license.attribution} ${license.changes} Licensed under `,
      extLink(license.url, license.name),
      "."
    ]);
  }

  function render(container, ctx, route) {
    const faq = faqSection(ctx, route);
    const parts = [
      { id: "learn-brief", label: "In brief", node: briefSection(ctx) },
      { id: "learn-rollout", label: "Rollouts", node: rolloutSection(ctx) },
      { id: "learn-maintenance", label: "Maintenance windows", node: maintenanceSection(ctx) },
      { id: "learn-insights", label: "What the data says", node: insightsSection(ctx) },
      { id: "learn-faq", label: "FAQ", node: faq.node }
    ];
    currentTitle = faq.found ? `${faq.found.title} · Learn` : "Learn";
    container.replaceChildren(
      el("div", { class: "page learn" }, [
        common.pageHead({
          id: "learn-heading",
          title: "How proactive quality updates work",
          sub: "Microsoft's own explanations, next to the live schedule they describe. Text from Microsoft Learn is quoted with its source."
        }),
        ctx.errors.learn
          ? el("p", {
              class: "inline-alert",
              id: "learn-error",
              text: "Microsoft's Learn content could not be loaded. Schedules and windows from the dataset are still shown."
            })
          : null,
        el("div", { class: "learn-layout" }, [
          jumpNav(parts),
          el("div", { class: "learn-body" }, [...parts.map((part) => part.node), licenseNote(ctx)])
        ])
      ])
    );
  }

  /* The maintenance table marks windows as running or passed, so it changes when one starts or
   * ends. */
  function nextChange(ctx) {
    const doc = maintenanceDoc(ctx);
    let next = null;
    for (const window of doc ? doc.records : []) {
      const boundary = windows.nextBoundary(window, ctx.now);
      if (boundary !== null && (next === null || boundary < next)) {
        next = boundary;
      }
    }
    return next;
  }

  PQU.views.learn = {
    name: "learn",
    label: "Learn",
    documents: ["learn", "stations", "regions", "maintenance", "insights"],
    title: () => currentTitle,
    nextChange,
    render
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
