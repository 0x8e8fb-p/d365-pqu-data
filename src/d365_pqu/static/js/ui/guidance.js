/* Microsoft guidance panels built from learn.json articles, with attribution. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};
  const { el, extLink } = PQU.ui.dom;
  const dates = PQU.dates;

  /* "Source: <article> (Microsoft Learn, CC BY 4.0) · updated 21 Sep 2026" */
  function sourceLine(article, options = {}) {
    if (!article || !article.url) {
      return null;
    }
    const updated = article.markdown_date ? ` · updated ${dates.formatDate(article.markdown_date)}` : "";
    return el("p", { class: options.class || "rules-source" }, [
      "Source: ",
      extLink(article.url, article.title || "Microsoft Learn"),
      ` (Microsoft Learn, CC BY 4.0)${updated}`
    ]);
  }

  /* Collapsible panel of rich blocks with the article's attribution. */
  function panel({ id, title, article, blocks, summaryNote, open = false }) {
    const rendered = PQU.ui.rich.blocks(blocks || []);
    if (!article || rendered.length === 0) {
      return null;
    }
    const updated = article.markdown_date ? ` · updated ${dates.formatDate(article.markdown_date)}` : "";
    return el("details", { class: "rules", id, open }, [
      el("summary", {}, [
        el("span", { class: "rules-title", text: title }),
        el("span", { class: "muted", text: ` · ${summaryNote || ""}${updated}`.replace(" · · ", " · ") })
      ]),
      el("div", { class: "rules-body prose" }, rendered),
      sourceLine(article)
    ]);
  }

  /* Blocks of the section that holds a dataset placeholder, split around the placeholder. */
  function datasetContext(article, name) {
    const section = PQU.ui.rich.sectionWithDataset(article, name);
    if (!section) {
      return { section: null, before: [], after: [] };
    }
    const index = section.blocks.findIndex((block) => block.type === "dataset" && block.name === name);
    return {
      section,
      before: section.blocks.slice(0, index),
      after: section.blocks.slice(index + 1)
    };
  }

  PQU.ui.guidance = { datasetContext, panel, sourceLine };
})(typeof globalThis !== "undefined" ? globalThis : this);
