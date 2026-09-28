/* Small building blocks shared by views: Microsoft status badges, markers, and train links. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};
  const { el } = PQU.ui.dom;

  function statusClass(status) {
    return (
      "badge " +
      String(status)
        .toLowerCase()
        .replace(/[^a-z]+/g, "-")
        .replace(/(^-|-$)/g, "")
    );
  }

  /* Microsoft's published status, shown exactly as published. */
  function statusBadge(status) {
    return el("span", { class: statusClass(status), text: status });
  }

  function newChip(record) {
    return record && record.station_schedule_new
      ? el("span", {
          class: "chip chip-new",
          title: "Microsoft marks this detailed station schedule as [NEW]",
          text: "New"
        })
      : null;
  }

  /* Where a train is shown in full. */
  function trainHref(pquId) {
    return PQU.router.href("train", { id: pquId });
  }

  function trainLink(pquId, props = {}) {
    return el("a", { ...props, href: trainHref(pquId), text: PQU.text.trainLabel(pquId) });
  }

  /* "Calculated" marker for values derived from published data. */
  function calcNote(textValue, props = {}) {
    return el("p", { class: "calc-note", ...props }, [
      el("span", { class: "calc-mark", "aria-hidden": "true", text: "↳" }),
      ` ${textValue}`
    ]);
  }

  PQU.ui.common = { calcNote, newChip, statusBadge, statusClass, trainHref, trainLink };
})(typeof globalThis !== "undefined" ? globalThis : this);
