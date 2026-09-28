/* Versions view: each service update's lifecycle phase today, from Microsoft's published dates,
 * alongside the PQU trains published for that version. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.views = PQU.views || {};
  const { el, extLink } = PQU.ui.dom;
  const dates = PQU.dates;
  const lifecycle = PQU.lifecycle;
  const records = PQU.records;
  const text = PQU.text;

  const LEGEND = ["preview", "available", "autoupdate", "supported"];

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

  function lifecycleBar(entry, assessment, todayIso) {
    const geometry = lifecycle.bar(entry.lifecycle, todayIso);
    if (!geometry) {
      return null;
    }
    const label =
      `Lifecycle from ${dates.formatDate(geometry.start)} to ${dates.formatDate(geometry.end)}. ` +
      (geometry.today === null
        ? "Today is outside this range."
        : `Today falls in the ${assessment.label} phase.`);
    return el("div", { class: "lifecycle-bar", role: "img", "aria-label": label }, [
      el(
        "div",
        { class: "lifecycle-track" },
        geometry.segments.map((segment) =>
          el("span", {
            class: `lifecycle-seg seg-${segment.state}`,
            title: `${segment.label}: ${dates.formatDateRange(segment.startDate, segment.endDate)}`,
            vars: { "--left": `${segment.left}%`, "--width": `${segment.width}%` }
          })
        )
      ),
      geometry.today === null
        ? null
        : el("span", { class: "lifecycle-today", vars: { "--at": `${geometry.today}%` } })
    ]);
  }

  function milestoneList(assessment, todayIso) {
    if (!assessment.milestones.length) {
      return null;
    }
    return el(
      "dl",
      { class: "milestones" },
      assessment.milestones.map((milestone) =>
        el(
          "div",
          {
            class: [
              "milestone",
              assessment.next && assessment.next.field === milestone.field ? "is-next" : null,
              milestone.date <= todayIso ? "is-reached" : null
            ]
          },
          [el("dt", { text: milestone.label }), el("dd", { text: dates.formatDate(milestone.date) })]
        )
      )
    );
  }

  function trainLine(entry) {
    const summary = lifecycle.trainSummary(entry.trains);
    if (!summary.total) {
      return el("p", { class: "version-trains muted", text: "No PQU trains in the current schedule." });
    }
    const counts = records.STATUS_ORDER.filter((status) => summary.counts[status]).map(
      (status) => `${summary.counts[status]} ${status}`
    );
    const parts = [`${text.plural(summary.total, "PQU train")}: ${counts.join(" · ")}.`];
    if (summary.latest) {
      parts.push(
        ` Latest published build ${summary.latest.application_build} ` +
          `(platform ${summary.latest.platform_build || "—"}, ${text.trainLabel(summary.latest.pqu_id)}).`
      );
    } else {
      parts.push(" No build published yet.");
    }
    return el("p", { class: "version-trains" }, [
      ...parts,
      " ",
      el("a", {
        href: PQU.router.href("trains", {}, { version: entry.version }),
        text: `Show ${entry.version} trains`
      })
    ]);
  }

  function versionCard(entry, todayIso, focusVersion) {
    const id = slug(entry.version);
    const record = entry.lifecycle;
    const assessment = record ? lifecycle.assess(record, todayIso) : null;
    const targeted = focusVersion === entry.version;
    const meta = [];
    if (record && record.release_label) {
      meta.push(el("span", { class: "mono", text: record.release_label }));
    }
    if (record && record.is_major) {
      meta.push(el("span", { class: "chip chip-major", text: "Major release" }));
    }
    return el(
      "article",
      {
        class: ["version-card", assessment ? `phase-${assessment.state}` : "phase-unknown", targeted ? "is-target" : null],
        id,
        "aria-labelledby": `${id}-title`
      },
      [
        el("div", { class: "version-head" }, [
          el("div", {}, [
            el("h3", {
              id: `${id}-title`,
              class: "mono",
              tabindex: targeted ? "-1" : null,
              dataset: targeted ? { focusTarget: "" } : {},
              text: entry.version
            }),
            meta.length ? el("p", { class: "version-meta" }, meta) : null
          ]),
          el(
            "div",
            { class: "version-state" },
            assessment
              ? [
                  el("span", { class: `phase-badge phase-badge-${assessment.state}`, text: assessment.label }),
                  el("p", { class: "version-next" }, [
                    PQU.ui.dom.visuallyHidden("Calculated from published dates: "),
                    assessment.summary
                  ])
                ]
              : [el("span", { class: "phase-badge phase-badge-unknown", text: "No lifecycle dates" })]
          )
        ]),
        assessment ? lifecycleBar(entry, assessment, todayIso) : null,
        assessment ? milestoneList(assessment, todayIso) : null,
        record
          ? null
          : el("p", {
              class: "muted version-missing",
              text: "This version is not in Microsoft's current service update schedule."
            }),
        trainLine(entry)
      ]
    );
  }

  function statStrip(entries, todayIso) {
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
      { class: "stat-strip", id: "version-stats" },
      stats.map((stat) => el("div", {}, [el("dt", { text: stat.label }), el("dd", { text: stat.value })]))
    );
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

  function legend() {
    return el(
      "ul",
      { class: "legend", "aria-label": "Lifecycle phases" },
      LEGEND.map((state) =>
        el("li", {}, [
          el("span", { class: `legend-swatch seg-${state}`, "aria-hidden": "true" }),
          lifecycle.STATE_LABELS[state]
        ])
      )
    );
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
    return [
      el("span", { class: "mono", text: record[field] }),
      " (",
      PQU.ui.common.trainLink(record.pqu_id),
      ")"
    ];
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
        el("p", { class: "build-headline", text: `No train in Microsoft's schedule uses build line ${PQU.builds.lineOf(result.input)}` }),
        known.length
          ? detail([`The schedule lists application builds for ${text.joinList(known)}.`])
          : null
      ];
    }
    const other = result.field === "application_build" ? "platform_build" : "application_build";
    const otherLabel = other === "application_build" ? "Application build" : "Platform build";
    let headline;
    let lines;
    switch (result.kind) {
      case "exact":
        headline = [PQU.ui.common.trainLink(result.match.pqu_id), ` · ${newerText(result.newerCount)}`];
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
          newerText(result.newerCount)
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
        headline = [`Older than every ${result.version} build listed · ${newerText(result.newerCount)}`];
        lines = [detail([`The earliest ${result.version} build in Microsoft's schedule is `, ...trainRef(result.newer, result.field), "."])];
        break;
      default:
        headline = [`Newer than every ${result.version} build listed`];
        lines = [detail([`The newest ${result.version} build in Microsoft's schedule is `, ...trainRef(result.older, result.field), "."])];
    }
    const state = versionState(ctx, result.version);
    return [
      el("p", { class: "build-headline" }, headline),
      ...lines,
      state
        ? detail([
            state,
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
        el("button", { class: "button primary small", type: "submit", text: "Find" })
      ]
    );
    show(route.query.build);
    return el("section", { class: "build-finder", id: "build-finder", "aria-labelledby": "build-finder-heading" }, [
      el("h3", { id: "build-finder-heading", text: "Find my build" }),
      el("p", {
        class: "section-lead",
        text: "See which PQU train published a build and how many newer builds Microsoft lists for its version."
      }),
      form,
      result,
      PQU.ui.common.calcNote("Calculated by comparing the number with the PQU builds in Microsoft's schedule.")
    ]);
  }

  function render(container, ctx, route) {
    const document = serviceDocument(ctx);
    const serviceRecords = document && document.state !== "not_configured" ? document.records : [];
    const entries = lifecycle.mergeVersions(serviceRecords, ctx.records);
    const source = document && document.source ? document.source : null;
    const focusVersion = (route && route.query.version) || null;
    container.replaceChildren(
      el("section", { class: "section", "aria-labelledby": "versions-heading" }, [
        el("div", { class: "section-head" }, [
          el("div", {}, [
            el("p", { class: "kicker", text: "Lifecycle" }),
            el("h2", {
              id: "versions-heading",
              tabindex: "-1",
              dataset: { viewHeading: "" },
              text: "Service update versions"
            })
          ]),
          source
            ? el("p", { class: "section-note" }, [
                "Dates from ",
                extLink(source.article_url, "Service update availability"),
                source.markdown_date ? ` · updated ${dates.formatDate(source.markdown_date)}` : ""
              ])
            : null
        ]),
        sourceNotice(ctx),
        statStrip(entries, ctx.todayIso),
        buildFinder(ctx, route || { query: {} }),
        scheduleNotes(ctx),
        el("p", { class: "calc-note" }, [
          el("span", { class: "calc-mark", "aria-hidden": "true", text: "↳" }),
          ` Phases and countdowns are calculated from Microsoft's published dates for ${ctx.todayLabel} (${ctx.zoneName}).`
        ]),
        entries.some((entry) => entry.lifecycle) ? legend() : null,
        el(
          "div",
          { class: "version-list" },
          entries.map((entry) => versionCard(entry, ctx.todayIso, focusVersion))
        )
      ])
    );
  }

  PQU.views.versions = {
    name: "versions",
    label: "Versions",
    documents: ["service_updates", "learn"],
    title: () => "Service update versions",
    render
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
