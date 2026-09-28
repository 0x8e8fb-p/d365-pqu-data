/* Hash routes: "#/trains?status=On-Going", "#/train/10.0.48-PQU-6", "#/region/North%20Europe". */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.router = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const ROUTES = [
    { name: "overview", pattern: [] },
    { name: "region", pattern: ["region"] },
    { name: "region", pattern: ["region", ":region"] },
    { name: "trains", pattern: ["trains"] },
    { name: "train", pattern: ["train", ":id"] },
    { name: "versions", pattern: ["versions"] },
    { name: "learn", pattern: ["learn"] },
    { name: "learn", pattern: ["learn", "faq", ":faq"] },
    { name: "changes", pattern: ["changes"] },
    { name: "data", pattern: ["data"] }
  ];

  function decode(value) {
    try {
      return decodeURIComponent(value.replace(/\+/g, " "));
    } catch (error) {
      return null;
    }
  }

  function parseQuery(text) {
    const query = {};
    for (const pair of String(text || "").split("&")) {
      if (!pair) {
        continue;
      }
      const index = pair.indexOf("=");
      const key = decode(index === -1 ? pair : pair.slice(0, index));
      const value = decode(index === -1 ? "" : pair.slice(index + 1));
      if (key !== null && value !== null && key !== "") {
        query[key] = value;
      }
    }
    return query;
  }

  function parse(hash) {
    let text = String(hash || "");
    if (text.startsWith("#")) {
      text = text.slice(1);
    }
    const queryIndex = text.indexOf("?");
    const pathText = queryIndex === -1 ? text : text.slice(0, queryIndex);
    const query = parseQuery(queryIndex === -1 ? "" : text.slice(queryIndex + 1));
    const rawSegments = pathText.split("/").filter((segment) => segment !== "");
    const segments = rawSegments.map(decode);
    if (segments.includes(null)) {
      return { name: "not-found", params: {}, query, path: pathText };
    }
    for (const route of ROUTES) {
      if (route.pattern.length !== segments.length) {
        continue;
      }
      const params = {};
      let matched = true;
      route.pattern.forEach((part, index) => {
        if (part.startsWith(":")) {
          params[part.slice(1)] = segments[index];
        } else if (part !== segments[index]) {
          matched = false;
        }
      });
      if (matched) {
        return { name: route.name, params, query, path: pathText };
      }
    }
    return { name: "not-found", params: {}, query, path: pathText };
  }

  function encodeQuery(query) {
    const pairs = [];
    for (const [key, value] of Object.entries(query || {})) {
      if (value === null || value === undefined || value === "" || value === false) {
        continue;
      }
      pairs.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
    }
    return pairs.length ? `?${pairs.join("&")}` : "";
  }

  function href(name, params = {}, query = {}) {
    let path;
    switch (name) {
      case "overview":
        path = "";
        break;
      case "region":
        path = params.region ? `region/${encodeURIComponent(params.region)}` : "region";
        break;
      case "train":
        path = `train/${encodeURIComponent(params.id)}`;
        break;
      case "learn":
        path = params.faq ? `learn/faq/${encodeURIComponent(params.faq)}` : "learn";
        break;
      default:
        path = name;
    }
    return `#/${path}${encodeQuery(query)}`;
  }

  return { ROUTES, encodeQuery, href, parse, parseQuery };
});
