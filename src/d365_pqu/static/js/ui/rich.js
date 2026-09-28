/* Renders learn.json blocks (paragraph, list, callout, quote, table, dataset) with DOM builders. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};
  const { el } = PQU.ui.dom;

  const CALLOUT_LABELS = {
    note: "Note",
    important: "Important",
    tip: "Tip",
    warning: "Warning",
    caution: "Caution"
  };

  function runNode(run) {
    let node = run.code ? el("code", { text: run.text }) : document.createTextNode(String(run.text));
    if (run.em) {
      node = el("em", {}, [node]);
    }
    if (run.strong) {
      node = el("strong", {}, [node]);
    }
    if (run.href && /^https:\/\//i.test(run.href)) {
      node = el("a", { href: run.href, rel: "noopener noreferrer" }, [node]);
    }
    return node;
  }

  function runs(list) {
    return (list || []).filter((run) => run && run.text).map(runNode);
  }

  function block(item, options) {
    if (!item || typeof item !== "object") {
      return null;
    }
    switch (item.type) {
      case "paragraph":
        return el("p", {}, runs(item.runs));
      case "list": {
        const tag = item.ordered ? "ol" : "ul";
        return el(
          tag,
          { start: item.ordered && item.start && item.start !== 1 ? String(item.start) : null },
          (item.items || []).map((entry) => el("li", {}, blocks(entry, options)))
        );
      }
      case "callout": {
        const label = CALLOUT_LABELS[item.kind] || "Note";
        return el("div", { class: `callout callout-${item.kind || "note"}`, role: "note" }, [
          el("p", { class: "callout-label", text: label }),
          ...blocks(item.blocks, options)
        ]);
      }
      case "quote":
        return el("blockquote", {}, blocks(item.blocks, options));
      case "table":
        return el("div", { class: "table-scroll rich-table" }, [
          el("table", {}, [
            el("thead", {}, [el("tr", {}, (item.header || []).map((cell) => el("th", { scope: "col" }, runs(cell))))]),
            el(
              "tbody",
              {},
              (item.rows || []).map((row) => el("tr", {}, row.map((cell) => el("td", {}, runs(cell)))))
            )
          ])
        ]);
      case "dataset": {
        const render = options && options.datasets ? options.datasets[item.name] : null;
        return typeof render === "function" ? render() : null;
      }
      default:
        return null;
    }
  }

  function blocks(list, options = {}) {
    return (list || []).map((item) => block(item, options)).filter(Boolean);
  }

  function plainText(list) {
    const parts = [];
    for (const item of list || []) {
      if (item.type === "paragraph") {
        parts.push((item.runs || []).map((run) => run.text).join(""));
      } else if (item.type === "list") {
        for (const entry of item.items || []) {
          parts.push(plainText(entry));
        }
      } else if (item.type === "callout" || item.type === "quote") {
        parts.push(plainText(item.blocks));
      } else if (item.type === "table") {
        for (const row of [item.header || [], ...(item.rows || [])]) {
          parts.push(row.map((cell) => cell.map((run) => run.text).join("")).join(" "));
        }
      }
    }
    return parts.join(" ");
  }

  /* Learn helpers: find an article by key and the section holding a dataset placeholder. */
  function article(learn, key) {
    const articles = (learn && learn.articles) || [];
    return articles.find((entry) => entry.key === key) || null;
  }

  function sectionWithDataset(entry, name) {
    return ((entry && entry.sections) || []).find((section) =>
      (section.blocks || []).some((item) => item.type === "dataset" && item.name === name)
    ) || null;
  }

  function callouts(entry) {
    const found = [];
    for (const section of (entry && entry.sections) || []) {
      for (const item of section.blocks || []) {
        if (item.type === "callout") {
          found.push({ section, block: item });
        }
      }
    }
    return found;
  }

  PQU.ui.rich = { CALLOUT_LABELS, article, blocks, callouts, plainText, runs, sectionWithDataset };
})(typeof globalThis !== "undefined" ? globalThis : this);
