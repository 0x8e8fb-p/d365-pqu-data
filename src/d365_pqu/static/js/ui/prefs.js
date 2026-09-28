/* Viewer preferences persisted in localStorage. Storage failures fall back to defaults. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};

  const KEYS = {
    theme: "d365-pqu-theme",
    zone: "d365-pqu-zone",
    region: "d365-pqu-region"
  };

  function read(name) {
    try {
      return root.localStorage.getItem(KEYS[name]);
    } catch (error) {
      return null;
    }
  }

  function write(name, value) {
    try {
      if (value === null || value === undefined || value === "") {
        root.localStorage.removeItem(KEYS[name]);
      } else {
        root.localStorage.setItem(KEYS[name], String(value));
      }
    } catch (error) {
      /* Storage may be unavailable (private mode); the in-memory value still applies. */
    }
  }

  PQU.ui.prefs = { KEYS, read, write };
})(typeof globalThis !== "undefined" ? globalThis : this);
