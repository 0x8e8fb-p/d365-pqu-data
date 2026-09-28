/* Layout helpers: on narrow screens the header's top row scrolls away and the tabs stay pinned.
 * The header heights are published as CSS variables so in-page jumps land below it. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};

  /* Measure now. Called before programmatic scrolls, because the header can change size in the
   * same task (for example when the tabs render) before a ResizeObserver callback runs. */
  function update() {
    const header = document.querySelector(".topbar");
    const row = document.querySelector(".topbar-inner");
    if (!header || !row) {
      return;
    }
    const style = document.documentElement.style;
    style.setProperty("--topbar-row", `${row.offsetHeight}px`);
    style.setProperty("--topbar-height", `${header.offsetHeight}px`);
  }

  function wire() {
    const header = document.querySelector(".topbar");
    const row = document.querySelector(".topbar-inner");
    if (!header || !row) {
      return;
    }
    update();
    if (typeof root.ResizeObserver === "function") {
      const observer = new root.ResizeObserver(update);
      observer.observe(row);
      observer.observe(header);
    } else {
      root.addEventListener("resize", update);
    }
  }

  PQU.ui.layout = { update, wire };
})(typeof globalThis !== "undefined" ? globalThis : this);
