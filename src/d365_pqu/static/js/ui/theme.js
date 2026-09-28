/* Dark/light theme toggle. The initial theme is applied by the inline script in index.html. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};

  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
  }

  function applyTheme(theme, persist = true) {
    const next = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    const toggle = document.getElementById("theme-toggle");
    const moon = document.getElementById("theme-icon-moon");
    const sun = document.getElementById("theme-icon-sun");
    if (toggle) {
      // A toggle button keeps one name ("Light theme"); aria-pressed says whether it is on.
      toggle.setAttribute("aria-pressed", next === "light" ? "true" : "false");
      toggle.title = next === "light" ? "Switch to the dark theme" : "Switch to the light theme";
    }
    if (moon) {
      moon.toggleAttribute("hidden", next === "light");
    }
    if (sun) {
      sun.toggleAttribute("hidden", next !== "light");
    }
    if (persist) {
      PQU.ui.prefs.write("theme", next);
    }
  }

  function wireTheme() {
    applyTheme(currentTheme(), false);
    const toggle = document.getElementById("theme-toggle");
    if (toggle) {
      toggle.addEventListener("click", () => {
        applyTheme(currentTheme() === "dark" ? "light" : "dark");
      });
    }
  }

  PQU.ui.theme = { applyTheme, currentTheme, wireTheme };
})(typeof globalThis !== "undefined" ? globalThis : this);
