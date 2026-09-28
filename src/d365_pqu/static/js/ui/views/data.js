/* Data & API view (#/data): every published file, read from api/index.json, with the dataset's
 * counts and Microsoft provenance from metadata.json. Names, descriptions, counts and links all
 * come from the same build as the files they describe. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.views = PQU.views || {};
  const { el, extLink, visuallyHidden } = PQU.ui.dom;
  const dates = PQU.dates;
  const text = PQU.text;

  const STATE_LABELS = {
    current: "Current",
    stale: "Last good copy",
    unavailable: "Unavailable",
    not_configured: "Not used"
  };
  const STATE_NOTES = {
    stale: "The latest version could not be read; the last good copy is published.",
    unavailable: "Could not be read; values from this article are left out."
  };

  /* index.json paths are relative to api/; links on this page are relative to the page. */
  function pagePath(path) {
    const value = String(path || "");
    if (value.startsWith("./../")) {
      return `./${value.slice(5)}`;
    }
    if (value.startsWith("./")) {
      return `./api/${value.slice(2)}`;
    }
    return value;
  }

  function absolute(path) {
    return new URL(pagePath(path), document.baseURI).href;
  }

  function formatLabel(path) {
    const match = /\.([a-z]+)$/i.exec(String(path || ""));
    const extension = match ? match[1].toLowerCase() : "";
    return { json: "JSON", csv: "CSV", xml: "Atom", ics: "iCalendar", txt: "Text" }[extension] || "File";
  }

  function commitUrl(source) {
    const repository = source && source.repository;
    const commit = String((source && source.commit) || "");
    if (!repository || !/^[\w.-]+\/[\w.-]+$/.test(repository) || !/^[0-9a-f]{7,40}$/i.test(commit)) {
      return null;
    }
    return `https://github.com/${repository}/commit/${commit}`;
  }

  function fact(label, value, note) {
    return el("div", {}, [
      el("dt", { text: label }),
      el("dd", {}, [value, note ? [" ", el("span", { class: "fact-note", text: note })] : null])
    ]);
  }

  function facts(ctx) {
    const metadata = ctx.metadata || {};
    const interval = PQU.health.formatInterval(metadata.check_interval_minutes);
    return el("dl", { class: "stat-strip data-facts", id: "data-facts" }, [
      fact(
        "Generated",
        dates.formatDateTime(metadata.generated_at, ctx.zone, { locale: ctx.locale }),
        interval ? `Microsoft's articles are checked ${interval}` : null
      ),
      fact(
        "Records",
        `${text.plural(metadata.record_count || 0, "train")} · ${text.plural(
          metadata.station_schedule_count || 0,
          "station window row"
        )}`,
        `${text.plural(metadata.region_count || 0, "region row")} · ${text.plural(
          metadata.service_update_count || 0,
          "service update"
        )} · ${text.plural(metadata.maintenance_window_count || 0, "maintenance window")}`
      ),
      fact("Schema version", el("span", { class: "mono", text: metadata.schema_version || "—" }), null),
      fact("Pipeline revision", el("span", { class: "mono", text: metadata.pipeline_revision || "—" }), null)
    ]);
  }

  function sourcesTable(ctx) {
    const sources = Object.entries((ctx.metadata || {}).sources || {});
    if (!sources.length) {
      return null;
    }
    const rows = sources.map(([key, entry]) => {
      const source = entry.source || null;
      const url = commitUrl(source);
      return el("tr", { dataset: { source: key } }, [
        el("th", { scope: "row" }, [
          extLink(entry.article_url, entry.label || key),
          entry.required ? el("span", { class: "fact-note", text: " · required" }) : null
        ]),
        el("td", {}, [
          el("span", { class: `source-state state-${entry.state}`, text: STATE_LABELS[entry.state] || entry.state }),
          STATE_NOTES[entry.state] ? el("span", { class: "fact-note", text: STATE_NOTES[entry.state] }) : null
        ]),
        el("td", {}, [
          source && source.commit
            ? url
              ? extLink(url, String(source.commit).slice(0, 7), { class: "mono" })
              : el("span", { class: "mono", text: String(source.commit).slice(0, 7) })
            : "—",
          source && source.raw_url ? [" · ", extLink(source.raw_url, "Markdown")] : null
        ]),
        el("td", { text: source && source.markdown_date ? dates.formatDate(source.markdown_date) : "—" }),
        el("td", {
          class: "col-optional",
          text: source && source.retrieved_at ? dates.formatDateTime(source.retrieved_at, ctx.zone, { locale: ctx.locale }) : "—"
        })
      ]);
    });
    return el("section", { class: "data-section", "aria-labelledby": "data-sources-heading" }, [
      el("h3", { id: "data-sources-heading", text: "Microsoft sources" }),
      el("p", {
        class: "section-lead",
        text:
          "Each article is read at one commit of Microsoft's documentation repository. Every file below records the " +
          "commit and checksum it came from."
      }),
      el("div", { class: "table-panel" }, [
        el("div", { class: "table-scroll" }, [
          el("table", { id: "data-sources" }, [
            el("caption", { class: "visually-hidden", text: "Microsoft Learn articles used by this dataset" }),
            el("thead", {}, [
              el("tr", {}, [
                ...["Article", "State", "Microsoft commit", "Article date"].map((label) =>
                  el("th", { scope: "col", text: label })
                ),
                el("th", { scope: "col", class: "col-optional", text: "Retrieved" })
              ])
            ]),
            el("tbody", {}, rows)
          ])
        ])
      ])
    ]);
  }

  function fileLink(path, label, name) {
    return el("a", { href: pagePath(path), "aria-label": `${name} (${label})`, text: label });
  }

  function fileItem(endpoint) {
    const links = [fileLink(endpoint.path, formatLabel(endpoint.path), endpoint.name)];
    if (endpoint.csv) {
      links.push(fileLink(endpoint.csv, "CSV", endpoint.name));
    }
    if (endpoint.schema) {
      links.push(fileLink(endpoint.schema, "Schema", endpoint.name));
    }
    return el("li", { class: "data-file", dataset: { path: endpoint.path } }, [
      el("h4", { text: endpoint.name }),
      el("p", { class: "data-desc", text: endpoint.description }),
      el("p", { class: "data-links" }, links.flatMap((link, index) => (index ? [" · ", link] : [link]))),
      el("p", { class: "data-address" }, [visuallyHidden("Address: "), el("code", { text: absolute(endpoint.path) })])
    ]);
  }

  function filesSection(index) {
    return el("section", { class: "data-section", "aria-labelledby": "data-files-heading" }, [
      el("h3", { id: "data-files-heading", text: "Files" }),
      el("p", {
        class: "section-lead",
        text: "Static files: no key or sign-in. JSON and CSV hold the same records; each JSON file has a JSON Schema."
      }),
      el("ul", { class: "data-files", id: "data-files" }, index.endpoints.map(fileItem))
    ]);
  }

  function calendarsSection(index) {
    const calendars = index.calendars || [];
    if (!calendars.length) {
      return null;
    }
    return el("section", { class: "data-section", "aria-labelledby": "data-calendars-heading" }, [
      el("h3", { id: "data-calendars-heading", text: "Calendars" }),
      el(
        "ul",
        { class: "data-calendars", id: "data-calendars" },
        calendars.map((calendar) => {
          const address = absolute(calendar.path);
          return el("li", { dataset: { path: calendar.path } }, [
            el("span", { class: "data-calendar-name", text: calendar.name }),
            el("span", { class: "muted", text: ` · ${text.plural(calendar.events, "event")} · ` }),
            el("a", {
              href: PQU.ui.calendar.webcal(address),
              "aria-label": `Subscribe to ${calendar.name}`,
              text: "Subscribe"
            }),
            " · ",
            el("a", {
              href: pagePath(calendar.path),
              download: `d365-pqu-${String(calendar.path).split("/").pop()}`,
              "aria-label": `Download .ics for ${calendar.name}`,
              text: "Download"
            })
          ]);
        })
      )
    ]);
  }

  function moreSection(ctx, index) {
    const links = (ctx.metadata || {}).links || {};
    const items = [
      el("li", {}, [el("a", { href: pagePath(index.workbook), download: true, text: "Excel workbook" })]),
      el("li", {}, [el("a", { href: "./api/index.json", text: "API index (JSON)" })]),
      index.llms ? el("li", {}, [el("a", { href: pagePath(index.llms), text: "llms.txt" }), " · a summary of these files for AI tools"]) : null,
      index.schema_source ? el("li", {}, [extLink(index.schema_source, "JSON Schemas on GitHub")]) : null,
      links.raw_pqu ? el("li", {}, [extLink(links.raw_pqu, "pqu.json on raw GitHub"), " · the committed copy"]) : null,
      index.repository ? el("li", {}, [extLink(index.repository, "Source repository")]) : null,
      index.notice ? el("li", {}, [extLink(index.notice, "License and attribution (NOTICE.md)")]) : null
    ];
    return el("section", { class: "data-section", "aria-labelledby": "data-more-heading" }, [
      el("h3", { id: "data-more-heading", text: "More" }),
      el("ul", { class: "data-more", id: "data-more" }, items)
    ]);
  }

  function render(container, ctx) {
    const index = ctx.index;
    const indexUsable = index && Array.isArray(index.endpoints);
    container.replaceChildren(
      el("section", { class: "section data-view", "aria-labelledby": "data-heading" }, [
        el("div", { class: "section-head" }, [
          el("div", {}, [
            el("p", { class: "kicker", text: "Open data" }),
            el("h2", { id: "data-heading", tabindex: "-1", dataset: { viewHeading: "" }, text: "Data & API" })
          ])
        ]),
        el("p", {
          class: "section-lead",
          text:
            "Everything on this dashboard comes from these files. Values are Microsoft's; calculated figures say so " +
            "in their descriptions."
        }),
        facts(ctx),
        sourcesTable(ctx),
        indexUsable
          ? [filesSection(index), calendarsSection(index), moreSection(ctx, index)]
          : el("p", { class: "inline-alert", id: "data-error", text: "The API index could not be loaded." })
      ])
    );
  }

  PQU.views.data = {
    name: "data",
    label: "Data & API",
    documents: ["index"],
    title: () => "Data & API",
    render
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
