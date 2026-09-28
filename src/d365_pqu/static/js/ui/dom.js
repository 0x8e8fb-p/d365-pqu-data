/* DOM builders. Content is always assigned as text; markup strings are never parsed. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};

  const BOOLEAN_PROPS = new Set(["hidden", "disabled", "checked", "selected", "open", "readOnly"]);
  const SAFE_URL = /^(#|\.{0,2}\/|https:\/\/|webcal:\/\/|mailto:)/i;

  function isSafeHref(value) {
    const href = String(value || "").trim();
    if (!href) {
      return false;
    }
    if (/^[a-z][a-z0-9+.-]*:/i.test(href)) {
      return SAFE_URL.test(href);
    }
    return true;
  }

  function el(tag, props = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
      if (value === null || value === undefined || value === false) {
        continue;
      }
      if (key === "style" || /^on[a-z]/i.test(key)) {
        throw new Error(`Refusing to set ${key} on <${tag}>`);
      }
      if (key === "class") {
        node.className = Array.isArray(value) ? value.filter(Boolean).join(" ") : String(value);
      } else if (key === "text") {
        node.textContent = String(value);
      } else if (key === "on") {
        for (const [event, handler] of Object.entries(value)) {
          node.addEventListener(event, handler);
        }
      } else if (key === "dataset") {
        for (const [name, data] of Object.entries(value)) {
          if (data !== null && data !== undefined) {
            node.dataset[name] = String(data);
          }
        }
      } else if (key === "vars") {
        for (const [name, data] of Object.entries(value)) {
          node.style.setProperty(name, String(data));
        }
      } else if (BOOLEAN_PROPS.has(key)) {
        node[key] = Boolean(value);
      } else if (key === "value") {
        node.value = String(value);
      } else if (key === "href" || key === "src") {
        if (isSafeHref(value)) {
          node.setAttribute(key, String(value));
        }
      } else {
        node.setAttribute(key, value === true ? "" : String(value));
      }
    }
    append(node, children);
    return node;
  }

  function append(node, children) {
    const list = Array.isArray(children) ? children : [children];
    for (const child of list) {
      if (child === null || child === undefined || child === false) {
        continue;
      }
      if (Array.isArray(child)) {
        append(node, child);
      } else {
        node.append(child instanceof Node ? child : String(child));
      }
    }
    return node;
  }

  function clear(node) {
    if (node) {
      node.replaceChildren();
    }
    return node;
  }

  function setText(target, value) {
    const node = typeof target === "string" ? document.getElementById(target) : target;
    if (node) {
      node.textContent =
        value === null || value === undefined || value === "" ? "—" : String(value);
    }
    return node;
  }

  /* External link: https only, never opens with access to this page. */
  function extLink(href, label, props = {}) {
    const url = String(href || "");
    if (!/^https:\/\//i.test(url)) {
      return el("span", { class: props.class || null, text: label });
    }
    return el("a", { ...props, href: url, rel: "noopener noreferrer", text: label });
  }

  function timeEl(value, label, props = {}) {
    return el("time", { ...props, datetime: value || null, text: label });
  }

  function visuallyHidden(textValue) {
    return el("span", { class: "visually-hidden", text: textValue });
  }

  function uid(prefix) {
    uid.counter = (uid.counter || 0) + 1;
    return `${prefix}-${uid.counter}`;
  }

  PQU.ui.dom = { append, clear, el, extLink, isSafeHref, setText, timeEl, uid, visuallyHidden };
})(typeof globalThis !== "undefined" ? globalThis : this);
