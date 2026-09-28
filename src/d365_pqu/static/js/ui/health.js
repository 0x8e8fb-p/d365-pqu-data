/* Header health pill and its disclosure panel. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};
  const { el, extLink } = PQU.ui.dom;
  const dates = PQU.dates;
  const health = PQU.health;

  const DOCUMENT_LABELS = {
    metadata: "dataset metadata",
    pqu: "train schedule",
    stations: "station schedules",
    regions: "region mapping",
    health: "check status",
    quality: "source warnings",
    learn: "Microsoft guidance text",
    service_updates: "service update schedule",
    maintenance: "maintenance windows",
    insights: "calculated figures",
    events: "key dates"
  };
  let wired = false;
  let lastAnnouncement = "";

  function panelRow(label, value) {
    return el("div", {}, [el("dt", { text: label }), el("dd", {}, [value])]);
  }

  function renderPanel(panel, result, ctx) {
    const metadata = ctx.metadata || {};
    const source = metadata.source || {};
    const zone = ctx.zone;
    const children = [el("h2", { class: "panel-title", text: "Data status" })];
    const checked = result.checkedAt
      ? el("span", {}, [
          dates.formatDateTime(result.checkedAt, zone, { locale: ctx.locale }),
          el("span", { class: "muted", text: ` · ${dates.relativeTime(result.checkedAt, ctx.now)}` })
        ])
      : "Unknown";
    const rows = [panelRow("Status", result.label), panelRow("Last check", checked)];
    if (result.state === "failed" && result.lastSuccessAt && result.lastSuccessAt !== result.checkedAt) {
      rows.push(
        panelRow(
          "Last successful check",
          el("span", {}, [
            dates.formatDateTime(result.lastSuccessAt, zone, { locale: ctx.locale }),
            el("span", { class: "muted", text: ` · ${dates.relativeTime(result.lastSuccessAt, ctx.now)}` })
          ])
        )
      );
    }
    const interval = health.formatInterval(result.intervalMinutes);
    if (interval) {
      rows.push(panelRow("Check schedule", interval));
    }
    if (result.lastChangeAt) {
      rows.push(
        panelRow(
          "Dataset last changed",
          el("span", {}, [
            dates.formatDateTime(result.lastChangeAt, zone, { locale: ctx.locale }),
            el("span", { class: "muted", text: ` · ${dates.relativeTime(result.lastChangeAt, ctx.now)}` }),
            " · ",
            el("a", { href: "#/changes", text: "See changes", on: { click: () => setOpen(false) } })
          ])
        )
      );
    }
    if (source.markdown_date) {
      rows.push(panelRow("Microsoft article updated", dates.formatDate(source.markdown_date)));
    }
    children.push(el("dl", { class: "panel-facts" }, rows));

    if (result.state === "unavailable") {
      children.push(
        el("p", {
          class: "panel-alert",
          text: "The published dataset could not be loaded. Reload the page to retry."
        })
      );
    } else if (result.state === "failed") {
      children.push(
        el("p", {
          class: "panel-alert",
          text: "The most recent check did not complete. The last valid dataset is still shown."
        })
      );
      if (result.error) {
        children.push(el("p", { class: "panel-error mono", text: result.error }));
      }
    } else if (result.state === "stale") {
      const expected = interval ? ` Checks are scheduled ${interval}.` : "";
      children.push(
        el("p", {
          class: "panel-alert",
          text: `No successful check in the last ${Math.floor(
            result.ageMinutes / 60
          )} hours.${expected} The data shown may be out of date.`
        })
      );
    }

    const optionalMissing = result.missing.filter((name) => name !== "pqu" && name !== "metadata");
    if (optionalMissing.length) {
      children.push(
        el("p", {
          class: "panel-alert",
          text: `Could not load: ${optionalMissing.map((name) => DOCUMENT_LABELS[name] || name).join(", ")}.`
        })
      );
    }

    if (result.warningCount > 0) {
      children.push(
        el("h3", {
          class: "panel-subtitle",
          text: `Source warnings (${result.warningCount})`
        })
      );
      if (!result.warningDetailsAvailable) {
        children.push(el("p", { class: "muted", text: "Warning details could not be loaded." }));
      } else {
        children.push(
          el(
            "ul",
            { class: "panel-list" },
            result.warnings.map((item) =>
              el("li", {}, [
                el("p", { text: health.describe(item, ctx.recordsById) }),
                item.pqu_id && ctx.recordsById[item.pqu_id]
                  ? el("a", {
                      class: "panel-link",
                      href: ctx.trainHref(item.pqu_id),
                      text: `Show ${item.pqu_id}`,
                      on: { click: () => setOpen(false) }
                    })
                  : null
              ])
            )
          )
        );
      }
    } else if (result.state === "healthy") {
      children.push(el("p", { class: "muted", text: "No source warnings in the published dataset." }));
    }

    if (source.article_url) {
      children.push(
        el("p", { class: "panel-foot" }, [
          extLink(source.article_url, "Microsoft source article"),
          source.commit ? el("span", { class: "muted mono", text: ` · ${source.commit.slice(0, 12)}` }) : null
        ])
      );
    }
    panel.replaceChildren(...children);
  }

  function setOpen(open) {
    const toggle = document.getElementById("health-toggle");
    const panel = document.getElementById("health-panel");
    if (!toggle || !panel) {
      return;
    }
    toggle.setAttribute("aria-expanded", open ? "true" : "false");
    panel.hidden = !open;
  }

  function wire() {
    if (wired) {
      return;
    }
    wired = true;
    const toggle = document.getElementById("health-toggle");
    const panel = document.getElementById("health-panel");
    toggle.addEventListener("click", () => {
      setOpen(toggle.getAttribute("aria-expanded") !== "true");
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !panel.hidden) {
        setOpen(false);
        toggle.focus();
      }
    });
    document.addEventListener("click", (event) => {
      if (!panel.hidden && !panel.contains(event.target) && !toggle.contains(event.target)) {
        setOpen(false);
      }
    });
  }

  /* ctx: { health, metadata, quality, errors, now, zone, locale, recordsById, trainHref } */
  function render(ctx) {
    wire();
    const result = health.assess(ctx);
    const pill = document.getElementById("health-toggle");
    pill.dataset.state = result.state;
    document.getElementById("sync-label").textContent = result.label;
    const time = document.getElementById("sync-time");
    if (result.checkedAt) {
      time.setAttribute("datetime", String(result.checkedAt));
      time.textContent = `checked ${dates.relativeTime(result.checkedAt, ctx.now)}`;
      time.title = dates.formatDateTime(result.checkedAt, ctx.zone, { locale: ctx.locale });
    } else {
      time.removeAttribute("datetime");
      time.textContent = "";
    }
    const panel = document.getElementById("health-panel");
    // Keep keyboard focus on the same control when the open panel is redrawn every minute.
    const controls = () => [...panel.querySelectorAll("a, button")];
    const focused = !panel.hidden && panel.contains(document.activeElement) ? controls().indexOf(document.activeElement) : -1;
    renderPanel(panel, result, ctx);
    if (focused >= 0 && controls()[focused]) {
      controls()[focused].focus({ preventScroll: true });
    }
    const announcement = `Data status: ${result.label}`;
    if (announcement !== lastAnnouncement) {
      lastAnnouncement = announcement;
      document.getElementById("health-status").textContent = announcement;
    }
    return result;
  }

  PQU.ui.health = { render, setOpen };
})(typeof globalThis !== "undefined" ? globalThis : this);
