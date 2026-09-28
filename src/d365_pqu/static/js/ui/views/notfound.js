/* Shown for links that do not match any view. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.views = PQU.views || {};
  const { el } = PQU.ui.dom;

  function render(container, ctx, route) {
    const path = route && route.path ? `#/${route.path.replace(/^\/+/, "")}` : "this link";
    container.replaceChildren(
      el("section", { class: "section standalone-view", "aria-labelledby": "not-found-heading" }, [
        el("p", { class: "kicker", text: "Not found" }),
        el("h2", {
          id: "not-found-heading",
          tabindex: "-1",
          dataset: { viewHeading: "" },
          text: "Page not found"
        }),
        el("p", { class: "section-note", text: `There is no page at ${path}.` }),
        el("p", {}, [el("a", { href: "#/", text: "Go to the overview" })])
      ])
    );
  }

  PQU.views.notFound = {
    name: "not-found",
    label: null,
    documents: [],
    title: () => "Page not found",
    render
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
