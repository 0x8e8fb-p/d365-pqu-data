/* Theme preference: "system" follows the operating system; "light" and "dark" are explicit
 * choices, saved in localStorage. The inline script in index.html applies the saved or system
 * theme before the first paint, so the page never flashes the wrong one. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};

  const CHOICES = ["system", "light", "dark"];
  let media = null;
  let wired = false;

  function preference() {
    const stored = PQU.ui.prefs.read("theme");
    return stored === "light" || stored === "dark" ? stored : "system";
  }

  function systemTheme() {
    return media && media.matches ? "dark" : "light";
  }

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function applyTheme(choice, persist = true) {
    const value = CHOICES.includes(choice) ? choice : "system";
    document.documentElement.setAttribute("data-theme", value === "system" ? systemTheme() : value);
    const select = document.getElementById("theme-select");
    if (select && select.value !== value) {
      select.value = value;
    }
    if (persist) {
      PQU.ui.prefs.write("theme", value === "system" ? null : value);
    }
  }

  function wireTheme() {
    media = typeof root.matchMedia === "function" ? root.matchMedia("(prefers-color-scheme: dark)") : null;
    applyTheme(preference(), false);
    if (wired) {
      return;
    }
    wired = true;
    const select = document.getElementById("theme-select");
    if (select) {
      select.addEventListener("change", () => applyTheme(select.value));
    }
    if (media && typeof media.addEventListener === "function") {
      media.addEventListener("change", () => {
        if (preference() === "system") {
          applyTheme("system", false);
        }
      });
    }
  }

  PQU.ui.theme = { CHOICES, applyTheme, currentTheme, preference, wireTheme };
})(typeof globalThis !== "undefined" ? globalThis : this);
