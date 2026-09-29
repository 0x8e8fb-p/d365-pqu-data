/* Building blocks shared by views: Microsoft's status as text, tags, train links, calculated
 * values (set in italics and announced as calculated), and page and section headings. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};
  const { el, visuallyHidden } = PQU.ui.dom;

  function slug(value) {
    return (
      String(value || "")
        .toLowerCase()
        .replace(/[^a-z]+/g, "-")
        .replace(/(^-|-$)/g, "") || "unknown"
    );
  }

  /* Microsoft's published status, shown exactly as published. */
  function statusText(status) {
    return el("span", { class: ["status", `status-${slug(status)}`], text: status });
  }

  function tag(label, kind, title) {
    return el("span", { class: ["tag", kind ? `tag-${kind}` : null], title: title || null, text: label });
  }

  function newTag(record) {
    return record && record.station_schedule_new
      ? tag("New", "new", "Microsoft marks this detailed station schedule as [NEW]")
      : null;
  }

  /* Where a train is shown in full. */
  function trainHref(pquId) {
    return PQU.router.href("train", { id: pquId });
  }

  function trainLink(pquId, props = {}) {
    return el("a", { ...props, href: trainHref(pquId), text: PQU.text.trainLabel(pquId) });
  }

  /* A value calculated from Microsoft's data, set in italics. `announce` also tells screen reader
   * users, for the main calculated line of an item (a phase or a state). */
  function calc(content, props = {}) {
    const { class: extra, announce, ...rest } = props;
    return el("span", { class: ["calc", extra], ...rest }, [announce ? visuallyHidden("Calculated: ") : null, content]);
  }

  /* A sentence about calculated values; one per view explains the italics. */
  function calcNote(content, props = {}) {
    return el("p", { class: "calc-note", ...props }, Array.isArray(content) ? content : [content]);
  }

  function italicNote(ctx, extra, props = {}) {
    return calcNote(
      [
        el("i", { text: "Italic" }),
        ` values are calculated from Microsoft's published dates for ${ctx.todayLabel} (${ctx.zoneName}).`,
        extra ? ` ${extra}` : ""
      ],
      props
    );
  }

  function content(value) {
    if (value === null || value === undefined) {
      return [];
    }
    if (typeof value === "string") {
      return [el("p", { text: value })];
    }
    return Array.isArray(value) ? value : [value];
  }

  /* The view's h1, focused after navigation, with an optional line below and a note beside it. */
  function pageHead({ id, title, sub, aside, before }) {
    return el("header", { class: "page-head" }, [
      el("div", {}, [
        before || null,
        el("h1", { id, tabindex: "-1", dataset: { viewHeading: "" }, text: title }),
        sub ? el("div", { class: "page-sub" }, content(sub)) : null
      ]),
      aside ? el("div", { class: "page-aside" }, content(aside)) : null
    ]);
  }

  /* A section under a ruled h2, with an optional link at the right of the heading. */
  function block(id, title, children, options = {}) {
    const headingId = options.headingId || `${id}-title`;
    return el("section", { class: ["block", options.class], id, "aria-labelledby": headingId }, [
      el("div", { class: "block-head" }, [
        el(
          "h2",
          {
            id: headingId,
            class: options.headingClass || null,
            tabindex: options.focusable ? "-1" : null
          },
          Array.isArray(title) ? title : [title]
        ),
        options.link ? el("a", { class: "block-link", href: options.link.href, text: options.link.text }) : null
      ]),
      ...children
    ]);
  }

  PQU.ui.common = {
    block,
    calc,
    calcNote,
    italicNote,
    newTag,
    pageHead,
    slug,
    statusText,
    tag,
    trainHref,
    trainLink
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
