/* Viewer time-zone preference: "auto" follows the browser; otherwise an IANA zone name. */
(function (root) {
  "use strict";

  const PQU = (root.PQU = root.PQU || {});
  PQU.ui = PQU.ui || {};
  const { el } = PQU.ui.dom;
  const dates = PQU.dates;

  const AUTO = "auto";
  let current = null;
  let wired = false;

  function resolve(setting) {
    if (setting && setting !== AUTO && dates.isValidZone(setting)) {
      return { setting, zone: setting };
    }
    return { setting: AUTO, zone: dates.detectZone() };
  }

  function get() {
    if (!current) {
      current = resolve(PQU.ui.prefs.read("zone"));
    }
    return current;
  }

  function set(setting) {
    current = resolve(setting);
    PQU.ui.prefs.write("zone", current.setting === AUTO ? null : current.setting);
    return current;
  }

  function locale() {
    const nav = root.navigator || {};
    return (nav.languages && nav.languages[0]) || nav.language || "en-US";
  }

  function zoneOptions(selected, detected) {
    const zones = new Set(dates.supportedZones());
    zones.delete("UTC");
    for (const zone of [selected, detected]) {
      if (zone && zone !== "UTC" && zone !== AUTO) {
        zones.add(zone);
      }
    }
    const byName = new Map();
    for (const zone of zones) {
      const name = dates.displayZone(zone);
      if (!byName.has(name) || zone === selected) {
        byName.set(name, zone);
      }
    }
    const groups = new Map();
    for (const name of [...byName.keys()].sort((a, b) => a.localeCompare(b))) {
      const area = name.includes("/") ? name.split("/")[0] : "Other";
      if (!groups.has(area)) {
        groups.set(area, []);
      }
      groups.get(area).push({ name, zone: byName.get(name) });
    }
    return [...groups.entries()].map(([area, list]) =>
      el(
        "optgroup",
        { label: area },
        list.map((item) => el("option", { value: item.zone, text: item.name }))
      )
    );
  }

  function renderPicker(onChange) {
    const select = document.getElementById("zone-select");
    if (!select) {
      return;
    }
    const { setting } = get();
    const detected = dates.detectZone();
    select.replaceChildren(
      el("option", { value: AUTO, text: `Auto (${dates.displayZone(detected)})` }),
      el("option", { value: "UTC", text: "UTC" }),
      ...zoneOptions(setting, detected)
    );
    select.value = setting;
    if (!wired) {
      wired = true;
      select.addEventListener("change", () => {
        set(select.value);
        onChange(get());
      });
    }
  }

  PQU.ui.zone = { AUTO, get, locale, renderPicker, set };
})(typeof globalThis !== "undefined" ? globalThis : this);
