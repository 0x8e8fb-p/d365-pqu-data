/* Trains timeline (#/trains?view=timeline): one lane per application version and one bar per
 * train, linked to the train's page. Geometry comes from core/timeline.js; the dates and statuses
 * are Microsoft's, and trains whose dates can't be placed are listed instead of drawn. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};
  const { el } = PQU.ui.dom;
  const dates = PQU.dates;
  const text = PQU.text;

  function statusSlug(status) {
    return (
      String(status || "")
        .toLowerCase()
        .replace(/[^a-z]+/g, "-")
        .replace(/(^-|-$)/g, "") || "unknown"
    );
  }

  function laneId(version) {
    return `tl-lane-${String(version).replace(/[^0-9a-z]+/gi, "-")}`;
  }

  function flagged(ctx, pquId) {
    return (ctx.flags[pquId] || []).length > 0;
  }

  /* Accessible name and tooltip: Microsoft's values, then the calculated phase. */
  function describeBar(ctx, bar) {
    const record = bar.record;
    const parts = [text.trainLabel(record.pqu_id), record.status, dates.formatDateRange(bar.start, bar.end)];
    if (bar.cutoff && bar.cutoff !== bar.start) {
      parts.push(`change cutoff ${dates.formatDate(bar.cutoff)}`);
    }
    const phase = ctx.phases.get(record.pqu_id);
    if (phase && phase.text) {
      parts.push(`${phase.text} (calculated)`);
    }
    if (flagged(ctx, record.pqu_id)) {
      parts.push("source warning");
    }
    return parts;
  }

  /* "PQU-12" -> prefix "PQU-" and number "12": narrow bars drop the prefix (see styles.css). */
  function barText(record) {
    const label = record.pqu_train || text.trainLabel(record.pqu_id);
    const match = /^(.*?)(\d+)$/.exec(label);
    return match && match[1]
      ? [el("span", { class: "tl-prefix", text: match[1] }), el("span", { class: "tl-num", text: match[2] })]
      : [el("span", { class: "tl-num", text: label })];
  }

  function barItem(ctx, bar) {
    const parts = describeBar(ctx, bar);
    const warning = flagged(ctx, bar.pqu_id);
    return el("li", { class: "tl-item", vars: { "--row": String(bar.row) } }, [
      el(
        "a",
        {
          class: [
            "tl-bar",
            `status-${statusSlug(bar.record.status)}`,
            bar.clipStart ? "clip-start" : null,
            bar.clipEnd ? "clip-end" : null,
            warning ? "has-flag" : null
          ],
          href: PQU.ui.common.trainHref(bar.pqu_id),
          dataset: { pqu: bar.pqu_id },
          "aria-label": parts.join(", "),
          title: parts.join(" · "),
          vars: { "--left": `${bar.left}%`, "--width": `${bar.width}%` }
        },
        [
          warning ? el("span", { class: "tl-flag", "aria-hidden": "true", text: "!" }) : null,
          el("span", { class: "tl-label", "aria-hidden": "true" }, barText(bar.record))
        ]
      ),
      bar.cutoffLeft === null
        ? null
        : el("span", { class: "tl-cutoff", "aria-hidden": "true", vars: { "--left": `${bar.cutoffLeft}%` } })
    ]);
  }

  function lane(ctx, data) {
    return el("div", { class: "tl-lane", dataset: { version: data.version } }, [
      el("p", { class: "tl-lane-label", id: laneId(data.version), text: data.version }),
      el(
        "ul",
        { class: "tl-bars", "aria-labelledby": laneId(data.version), vars: { "--rows": String(data.rows) } },
        data.bars.map((bar) => barItem(ctx, bar))
      )
    ]);
  }

  function axis(layout) {
    return el("div", { class: "tl-axis", "aria-hidden": "true" }, [
      el("span", { class: "tl-lane-label" }),
      el(
        "div",
        { class: "tl-axis-track" },
        layout.months.map((month) =>
          el("span", { class: "tl-month-label", vars: { "--left": `${month.left}%` } }, [
            month.label,
            month.year ? [" ", el("small", { text: month.year })] : null
          ])
        )
      )
    ]);
  }

  function legend(layout) {
    const present = new Set();
    let cutoffs = false;
    for (const data of layout.lanes) {
      for (const bar of data.bars) {
        present.add(bar.record.status);
        cutoffs = cutoffs || bar.cutoffLeft !== null;
      }
    }
    const known = PQU.records.STATUS_ORDER.filter((status) => present.has(status));
    const other = [...present].filter((status) => !PQU.records.STATUS_ORDER.includes(status)).sort();
    return el("ul", { class: "legend tl-legend", "aria-label": "Timeline key" }, [
      ...[...known, ...other].map((status) =>
        el("li", {}, [
          el("span", { class: `legend-swatch tl-swatch status-${statusSlug(status)}`, "aria-hidden": "true" }),
          status
        ])
      ),
      cutoffs
        ? el("li", {}, [el("span", { class: "legend-cutoff", "aria-hidden": "true" }), "Change cutoff"])
        : null,
      layout.today === null
        ? null
        : el("li", {}, [el("span", { class: "legend-today", "aria-hidden": "true" }), "Today"])
    ]);
  }

  function figure(ctx, layout) {
    const range = dates.formatDateRange(layout.start, layout.end);
    return el(
      "figure",
      { class: ["timeline", `zoom-${layout.zoom}`], id: "timeline", "aria-labelledby": "timeline-caption" },
      [
        el("figcaption", {
          class: "visually-hidden",
          id: "timeline-caption",
          text:
            `Timeline of ${text.plural(layout.drawn, "train")} from ${range}, one lane per application ` +
            "version. Each bar links to the train's page."
        }),
        el("p", { class: "tl-range", id: "timeline-range", text: range }),
        el("div", { class: "tl-scroll" }, [
          el("div", { class: "tl-plot" }, [
            axis(layout),
            ...layout.months.map((month) =>
              el("span", { class: "tl-grid", "aria-hidden": "true", vars: { "--f": String(month.left / 100) } })
            ),
            ...layout.lanes.map((data) => lane(ctx, data)),
            layout.today === null
              ? null
              : el("span", { class: "tl-today", "aria-hidden": "true", vars: { "--f": String(layout.today / 100) } })
          ])
        ]),
        legend(layout)
      ]
    );
  }

  function showAll(onZoom) {
    return el("button", {
      class: "link-button",
      type: "button",
      id: "timeline-show-all",
      text: "Show all dates",
      on: { click: () => onZoom("all") }
    });
  }

  function notes(ctx, layout, onZoom) {
    const items = [];
    if (layout.drawn && layout.outside.length && layout.zoom !== "all") {
      const count = layout.outside.length;
      items.push(
        el("p", { class: "tl-note", id: "timeline-outside" }, [
          `${text.plural(count, "matching train")} ${count === 1 ? "falls" : "fall"} outside this range. `,
          showAll(onZoom)
        ])
      );
    }
    for (const entry of layout.unreliable) {
      const reasons = (ctx.flags[entry.record.pqu_id] || []).map((item) =>
        PQU.health.describe(item, ctx.recordsById, { asPublished: false })
      );
      items.push(
        el("p", { class: "tl-note tl-not-drawn", dataset: { pqu: entry.record.pqu_id } }, [
          el("span", { class: "flag", text: "Not drawn:" }),
          " ",
          PQU.ui.common.trainLink(entry.record.pqu_id),
          reasons.length ? `. ${reasons.join(" ")}` : ". A source warning questions its dates."
        ])
      );
    }
    if (layout.undated.length) {
      const count = layout.undated.length;
      items.push(
        el("p", {
          class: "tl-note",
          text: `${text.plural(count, "matching train")} ${count === 1 ? "has" : "have"} no published start date, so ${
            count === 1 ? "it is" : "they are"
          } not drawn.`
        })
      );
    }
    return items;
  }

  /* list: trains matching the filters; layout: core/timeline.js layout(list, ...). */
  function render(ctx, list, layout, { onZoom }) {
    const children = [];
    if (!list.length) {
      children.push(el("p", { class: "tl-empty", id: "timeline-empty", text: "No trains match these filters." }));
    } else if (!layout.drawn) {
      children.push(
        el("p", { class: "tl-empty", id: "timeline-empty" }, [
          layout.zoom === "all"
            ? "None of the matching trains can be drawn."
            : `None of the ${text.plural(list.length, "matching train")} fall in this range. `,
          layout.zoom === "all" ? null : showAll(onZoom)
        ])
      );
    } else {
      children.push(figure(ctx, layout));
    }
    children.push(...notes(ctx, layout, onZoom));
    children.push(
      PQU.ui.common.calcNote(
        "Bars use Microsoft's published change cutoff, start and end dates. The range and today's line " +
          `are calculated for ${ctx.todayLabel} (${ctx.zoneName}).`,
        { id: "timeline-calc-note" }
      )
    );
    return el("div", { class: "timeline-panel" }, children);
  }

  PQU.ui.timeline = { render, statusSlug };
})(typeof globalThis !== "undefined" ? globalThis : this);
