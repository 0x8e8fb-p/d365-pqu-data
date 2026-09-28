/* Plain-language descriptions of change-history records (api/changes.json).
 *
 * A change says what differs between two published snapshots of Microsoft's articles. The
 * wording only restates the recorded values; it never guesses why something changed. */
(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.changes = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  function load(name, file) {
    return typeof module === "object" && module.exports ? require(file) : root.PQU[name];
  }
  const dates = load("dates", "./dates.js");
  const text = load("text", "./text.js");
  const lifecycle = load("lifecycle", "./lifecycle.js");
  const router = load("router", "./router.js");

  const PQU_FIELDS = {
    application_version: "Application version",
    pqu_train: "Train",
    release_number: "Release number",
    change_cutoff_date: "Change cutoff",
    train_start_date: "Train start",
    train_end_date: "Train end",
    status: "Status",
    application_build: "Application build",
    platform_build: "Platform build",
    uep_version: "UEP version",
    station_schedule_available: "Station schedule",
    status_note: "Microsoft's status note"
  };
  const STATION_FIELDS = {
    sandbox_start_date: "sandbox start",
    sandbox_end_date: "sandbox end",
    production_start_date: "production start",
    production_end_date: "production end"
  };
  const SERVICE_UPDATE_FIELDS = {
    release_label: "release label",
    is_major: "major release"
  };
  for (const milestone of lifecycle.MILESTONES) {
    SERVICE_UPDATE_FIELDS[milestone.field] = milestone.label.toLowerCase();
  }
  const MAINTENANCE_FIELDS = {
    start_time_utc: "start time (UTC)",
    days: "days",
    duration_hours: "duration (hours)",
    duration_text: "duration"
  };
  const ENTITY_LABELS = {
    pqu: "Trains",
    station: "Station schedules",
    region: "Regions",
    guidance: "Microsoft guidance",
    service_update: "Service updates",
    maintenance_window: "Maintenance windows"
  };
  const TYPE_LABELS = { added: "Added", removed: "Removed", modified: "Changed" };

  function value(item, field) {
    if (item === null || item === undefined || item === "") {
      if (field === "station_schedule_available") {
        return "not published";
      }
      return "none";
    }
    if (field === "station_schedule_available") {
      return item ? "published" : "not published";
    }
    if (typeof item === "boolean") {
      return item ? "yes" : "no";
    }
    if (Array.isArray(item)) {
      return text.joinList(item.map(String));
    }
    if (typeof item === "string" && dates.isIsoDate(item)) {
      return dates.formatDate(item);
    }
    return String(item);
  }

  function changed(label, change, field) {
    const oldValue = change.old_value;
    const newValue = change.new_value;
    const blank = (item) => item === null || item === undefined || item === "";
    if (field !== "station_schedule_available" && blank(oldValue) && !blank(newValue)) {
      return `${label} published: ${value(newValue, field)}`;
    }
    if (field !== "station_schedule_available" && !blank(oldValue) && blank(newValue)) {
      return `${label} removed (was ${value(oldValue, field)})`;
    }
    return `${label} changed from ${value(oldValue, field)} to ${value(newValue, field)}`;
  }

  function windowsText(row) {
    if (!row || typeof row !== "object") {
      return "";
    }
    const parts = [];
    if (row.sandbox_start_date) {
      parts.push(`sandbox ${dates.formatDateRange(row.sandbox_start_date, row.sandbox_end_date)}`);
    }
    if (row.production_start_date) {
      parts.push(`production ${dates.formatDateRange(row.production_start_date, row.production_end_date)}`);
    }
    return parts.join(", ");
  }

  /* "station.4" or "station.4.sandbox_start_date" -> {station: 4, field}. */
  function stationField(field) {
    const match = /^station\.(\d+)(?:\.([a-z_]+))?$/.exec(String(field || ""));
    return match ? { station: Number(match[1]), field: match[2] || null } : { station: null, field: null };
  }

  /* "10.0.49#general_availability_date" -> {name, field}. */
  function keyedField(field) {
    const textValue = String(field || "");
    const index = textValue.indexOf("#");
    return index === -1
      ? { name: textValue, field: null }
      : { name: textValue.slice(0, index), field: textValue.slice(index + 1) };
  }

  function describePqu(change) {
    const label = text.trainLabel(change.pqu_id);
    if (change.change_type === "added") {
      const status = (change.new_value || {}).status;
      return { subject: label, text: status ? `Added to Microsoft's schedule as ${status}` : "Added to Microsoft's schedule" };
    }
    if (change.change_type === "removed") {
      const status = (change.old_value || {}).status;
      return {
        subject: label,
        text: status ? `Removed from Microsoft's schedule (was ${status})` : "Removed from Microsoft's schedule"
      };
    }
    const fieldLabel = PQU_FIELDS[change.field] || change.field;
    return { subject: label, text: changed(fieldLabel, change, change.field) };
  }

  function describeStation(change) {
    const label = text.trainLabel(change.pqu_id);
    const parsed = stationField(change.field);
    const station = parsed.station === null ? "A station" : `Station ${parsed.station}`;
    if (change.change_type === "added") {
      const windows = windowsText(change.new_value);
      return { subject: label, text: `${station} schedule published${windows ? `: ${windows}` : ""}` };
    }
    if (change.change_type === "removed") {
      return { subject: label, text: `${station} schedule removed` };
    }
    const fieldLabel = STATION_FIELDS[parsed.field] || parsed.field || "window";
    return { subject: label, text: changed(`${station} ${fieldLabel}`, change, parsed.field) };
  }

  function describeRegion(change) {
    const name = String(change.field || "").replace(/^region\./, "");
    const row = change.new_value || change.old_value || {};
    const station = row.station === undefined || row.station === null ? "" : ` Station ${row.station}`;
    if (change.change_type === "added") {
      return { subject: name, text: `Added to${station || " the region list"}` };
    }
    if (change.change_type === "removed") {
      return { subject: name, text: `Removed from${station || " the region list"}` };
    }
    const oldRow = change.old_value || {};
    const newRow = change.new_value || {};
    const parts = Object.keys(oldRow)
      .filter((key) => JSON.stringify(oldRow[key]) !== JSON.stringify(newRow[key]))
      .map((key) => `${key.replace(/_/g, " ")} ${value(oldRow[key], key)} → ${value(newRow[key], key)}`);
    return { subject: name, text: `Region details changed${parts.length ? `: ${parts.join("; ")}` : ""}` };
  }

  function describeGuidance(change, options) {
    const { name } = keyedField(change.field);
    const article = options.sourceLabel ? options.sourceLabel(name) : null;
    const title = (change.new_value || change.old_value || {}).title;
    const subject = article || "Microsoft guidance";
    if (change.change_type === "added") {
      return { subject, text: title ? `New section “${title}”` : "New section" };
    }
    if (change.change_type === "removed") {
      return { subject, text: title ? `Section “${title}” removed` : "A section was removed" };
    }
    return {
      subject,
      text: title ? `Microsoft updated the text of “${title}”` : "Microsoft updated the text of a section"
    };
  }

  function describeKeyed(change, labels, noun, list) {
    const { name, field } = keyedField(change.field);
    if (change.change_type === "added") {
      return { subject: name, text: `Added to ${list}` };
    }
    if (change.change_type === "removed") {
      return { subject: name, text: `Removed from ${list}` };
    }
    const label = labels[field] || field;
    return { subject: name, text: text.capitalize(changed(`${noun} ${label}`.trim(), change, field)) };
  }

  /*
   * {subject, text, entity, type} for one change. `options.sourceLabel(key)` names the Microsoft
   * article of a guidance change.
   */
  function describe(change, options = {}) {
    let result;
    switch (change.entity) {
      case "pqu":
        result = describePqu(change);
        break;
      case "station":
        result = describeStation(change);
        break;
      case "region":
        result = describeRegion(change);
        break;
      case "guidance":
        result = describeGuidance(change, options);
        break;
      case "service_update":
        result = describeKeyed(change, SERVICE_UPDATE_FIELDS, "", "Microsoft's service update schedule");
        break;
      case "maintenance_window":
        result = describeKeyed(change, MAINTENANCE_FIELDS, "Maintenance window", "Microsoft's maintenance windows");
        break;
      default:
        result = { subject: change.pqu_id || "", text: `${TYPE_LABELS[change.change_type] || "Changed"} ${change.field || ""}`.trim() };
    }
    return { ...result, entity: change.entity, type: change.change_type };
  }

  /* Changes that belong to one train, newest first. */
  function forTrain(changes, pquId) {
    return (changes || [])
      .filter((change) => change.pqu_id === pquId && (change.entity === "pqu" || change.entity === "station"))
      .sort((a, b) => String(b.changed_at).localeCompare(String(a.changed_at)));
  }

  /*
   * Where the dashboard shows a change's subject: a hash route, the https Microsoft Learn URL of
   * a guidance section, or null (for example a region that was removed).
   */
  function hrefFor(change) {
    switch (change.entity) {
      case "pqu":
      case "station":
        return router.href("train", { id: change.pqu_id });
      case "service_update":
        return router.href("versions", {}, { version: keyedField(change.field).name });
      case "region":
        return change.change_type === "removed"
          ? null
          : router.href("region", { region: String(change.field || "").replace(/^region\./, "") });
      case "maintenance_window":
        return router.href("learn");
      case "guidance": {
        const url = String((change.new_value || change.old_value || {}).url || "");
        return /^https:\/\//i.test(url) ? url : null;
      }
      default:
        return null;
    }
  }

  /* Distinct Microsoft commits of a list of changes, in order of first appearance. */
  function commitsOf(list) {
    return [...new Set((list || []).map((change) => change.source_commit).filter(Boolean))];
  }

  /* Group changes recorded by the same sync: [{changed_at, changes[]}] newest first. */
  function bySync(changes) {
    const groups = new Map();
    for (const change of changes || []) {
      if (!groups.has(change.changed_at)) {
        groups.set(change.changed_at, []);
      }
      groups.get(change.changed_at).push(change);
    }
    return [...groups.entries()]
      .sort((a, b) => String(b[0]).localeCompare(String(a[0])))
      .map(([changedAt, list]) => ({ changed_at: changedAt, changes: list }));
  }

  /* Checks grouped by calendar day in `zone`: [{day, syncs: [{changed_at, changes}]}] newest first. */
  function byDay(changes, zone) {
    const days = [];
    const index = new Map();
    for (const group of bySync(changes)) {
      const parts = dates.zonedParts(group.changed_at, zone);
      const day = parts ? parts.iso : String(group.changed_at).slice(0, 10);
      if (!index.has(day)) {
        const entry = { day, syncs: [] };
        index.set(day, entry);
        days.push(entry);
      }
      index.get(day).syncs.push(group);
    }
    return days;
  }

  /*
   * Display lines for a list of changes: one per change, except that station schedules
   * published or removed for the same train in the same sync become one line.
   * Each line: {subject, text, entity, type, ids[], href, commits[], pquId, field}.
   */
  function lines(list, options = {}) {
    const entries = [];
    const merged = new Map();
    for (const change of list || []) {
      const station =
        change.entity === "station" && change.change_type !== "modified" ? stationField(change.field).station : null;
      if (station === null) {
        entries.push({ changes: [change], stations: null });
        continue;
      }
      const key = `${change.changed_at}|${change.pqu_id}|${change.change_type}`;
      if (merged.has(key)) {
        merged.get(key).changes.push(change);
        merged.get(key).stations.push(station);
        continue;
      }
      const entry = { changes: [change], stations: [station] };
      merged.set(key, entry);
      entries.push(entry);
    }
    return entries.map((entry) => {
      const first = entry.changes[0];
      const extra = {
        ids: entry.changes.map((change) => change.change_id),
        href: hrefFor(first),
        commits: commitsOf(entry.changes),
        pquId: first.pqu_id,
        field: first.field || ""
      };
      if (!entry.stations || entry.stations.length === 1) {
        return { ...describe(first, options), ...extra };
      }
      const verb = first.change_type === "added" ? "published" : "removed";
      return {
        subject: text.trainLabel(first.pqu_id),
        text: `Schedules ${verb} for ${text.stationList(entry.stations)}`,
        entity: "station",
        type: first.change_type,
        ...extra
      };
    });
  }

  return {
    ENTITY_LABELS,
    TYPE_LABELS,
    byDay,
    bySync,
    commitsOf,
    describe,
    forTrain,
    hrefFor,
    keyedField,
    lines,
    stationField
  };
});
