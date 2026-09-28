/* Calendar subscriptions. calendar/station-N.ics and calendar/milestones.ics are built with the
 * site from events.json (see ics.py); these blocks link to them. The event counts are taken from
 * the same events, so they match the files. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};
  const { el } = PQU.ui.dom;
  const text = PQU.text;

  const STATION_KINDS = ["sandbox_window", "production_window"];
  const MILESTONE_KINDS = [
    "change_cutoff",
    "preview",
    "preview_latest_update",
    "general_availability",
    "autoupdate_first",
    "autoupdate_second",
    "end_of_service"
  ];

  function count(ctx, keep) {
    const list = ctx.events && Array.isArray(ctx.events.records) ? ctx.events.records : null;
    return list ? list.filter(keep).length : null;
  }

  /* Resolved against this page, so the address points to wherever this dashboard is published. */
  function address(file) {
    return new URL(`calendar/${file}`, document.baseURI).href;
  }

  function webcal(url) {
    return url.replace(/^https?:\/\//i, "webcal://");
  }

  function block({ id, file, title, summary, events }) {
    const url = address(file);
    return el("div", { class: "calendar-block", id, dataset: { calendar: file } }, [
      el("p", { class: "calendar-title" }, [
        el("span", { text: title }),
        events === null ? null : el("span", { class: "muted", text: ` · ${text.plural(events, "event")}` })
      ]),
      el("p", { class: "calendar-desc", text: summary }),
      el("div", { class: "calendar-actions" }, [
        el("a", {
          class: "button small primary calendar-subscribe",
          href: webcal(url),
          "aria-label": `Subscribe to ${title}`,
          text: "Subscribe"
        }),
        el("a", {
          class: "button small calendar-download",
          href: `./calendar/${file}`,
          download: `d365-pqu-${file}`,
          type: "text/calendar",
          "aria-label": `Download .ics for ${title}`,
          text: "Download .ics"
        })
      ]),
      el("label", { class: "field calendar-address" }, [
        el("span", { text: "Calendar address" }),
        el("input", {
          id: `${id}-address`,
          type: "url",
          readOnly: true,
          spellcheck: "false",
          value: url,
          on: { focus: (event) => event.target.select() }
        })
      ])
    ]);
  }

  function stationBlock(ctx, station, idPrefix) {
    return block({
      id: `${idPrefix}-station`,
      file: `station-${station}.ics`,
      title: `Station ${station} windows`,
      summary: `Sandbox and production windows for Station ${station}, as all-day events.`,
      events: count(ctx, (event) => STATION_KINDS.includes(event.kind) && event.station === station)
    });
  }

  function milestonesBlock(ctx, idPrefix) {
    return block({
      id: `${idPrefix}-milestones`,
      file: "milestones.ics",
      title: "Change cutoffs and service updates",
      summary: "Every change cutoff, plus preview, general availability, autoupdate and end-of-service dates.",
      events: count(ctx, (event) => MILESTONE_KINDS.includes(event.kind))
    });
  }

  function help() {
    return el("p", {
      class: "calendar-help muted",
      text:
        "Subscribe opens your calendar app, or paste the address where your app asks for a calendar URL. " +
        "Events are all-day and don't mark you as busy; calendar apps refresh subscriptions on their own schedule."
    });
  }

  PQU.ui.calendar = { address, help, milestonesBlock, stationBlock, webcal };
})(typeof globalThis !== "undefined" ? globalThis : this);
