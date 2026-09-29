/* Shown for links that do not match any view. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.views = PQU.views || {};
  const { el } = PQU.ui.dom;

  function render(container, ctx, route) {
    const path = route && route.path ? `#/${route.path.replace(/^\/+/, "")}` : "this link";
    container.replaceChildren(
      el("div", { class: "page" }, [
        PQU.ui.common.pageHead({
          id: "not-found-heading",
          title: "Page not found",
          sub: `There is no page at ${path}.`
        }),
        el("ul", { class: "not-found-links" }, [
          el("li", {}, [el("a", { href: "#/", text: "Overview" })]),
          el("li", {}, [el("a", { href: PQU.router.href("trains"), text: "PQU trains" })]),
          el("li", {}, [el("a", { href: PQU.router.href("data"), text: "Data & API" })])
        ])
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
