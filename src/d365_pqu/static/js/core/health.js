/* Publication health derived only from published documents and load results. */
(function (root, factory) {
  "use strict";
  const api = factory(root);
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.PQU = root.PQU || {};
    root.PQU.health = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function (root) {
  "use strict";

  function load(name, file) {
    return typeof module === "object" && module.exports ? require(file) : root.PQU[name];
  }
  const dates = load("dates", "./dates.js");

  const STALE_MULTIPLIER = 3;
  const REQUIRED = ["metadata", "pqu"];

  function warningItems(quality) {
    const records = quality && Array.isArray(quality.records) ? quality.records : [];
    return records.filter((item) => item && item.severity === "warning");
  }

  function checkedAt(health, metadata) {
    return (
      (health && health.checked_at) ||
      (metadata && (metadata.last_published_at || metadata.generated_at)) ||
      null
    );
  }

  function intervalMinutes(health, metadata) {
    const value =
      (health && health.check_interval_minutes) || (metadata && metadata.check_interval_minutes);
    return Number.isFinite(value) && value > 0 ? value : null;
  }

  /*
   * States, most severe first: unavailable (a required document failed to load), failed (the last
   * published check failed), stale (no check within three intervals), warnings, healthy.
   */
  function assess({ health, metadata, quality, errors = {}, now = Date.now() }) {
    const missing = Object.keys(errors).filter((name) => errors[name]);
    const checked = checkedAt(health, metadata);
    const interval = intervalMinutes(health, metadata);
    const checkedDate = dates.toDate(checked);
    const ageMinutes = checkedDate ? Math.floor((now - checkedDate.getTime()) / 60000) : null;
    const staleAfter = interval ? interval * STALE_MULTIPLIER : null;
    const warnings = warningItems(quality);
    const warningCount = quality
      ? warnings.length
      : Number((health && health.warning_count) || 0);
    const result = {
      state: "healthy",
      label: "Up to date",
      checkedAt: checked,
      lastSuccessAt: (health && health.last_successful_check_at) || checked,
      lastChangeAt:
        (health && health.last_source_change_at) || (metadata && metadata.last_published_at) || null,
      checkedCommit: (health && health.checked_commit) || null,
      error: (health && health.error) || null,
      ageMinutes,
      intervalMinutes: interval,
      staleAfterMinutes: staleAfter,
      warnings,
      warningCount,
      warningDetailsAvailable: Boolean(quality),
      missing
    };
    if (REQUIRED.some((name) => errors[name])) {
      return { ...result, state: "unavailable", label: "Unavailable" };
    }
    if (health && health.status === "failed") {
      return { ...result, state: "failed", label: "Last check failed" };
    }
    if (staleAfter !== null && ageMinutes !== null && ageMinutes > staleAfter) {
      return { ...result, state: "stale", label: "Stale" };
    }
    if (warningCount > 0) {
      const noun = warningCount === 1 ? "source warning" : "source warnings";
      return { ...result, state: "warnings", label: `${warningCount} ${noun}` };
    }
    return result;
  }

  function formatInterval(minutes) {
    if (!minutes) {
      return null;
    }
    if (minutes % 60 === 0) {
      const hours = minutes / 60;
      return hours === 1 ? "every hour" : `every ${hours} hours`;
    }
    return `every ${minutes} minutes`;
  }

  /* Plain-language description of a quality finding, built from the published record values.
   * `options.asPublished: false` drops the note that the values are shown unchanged (for views
   * that leave the questioned dates out). */
  function describe(item, recordsById = {}, options = {}) {
    const record = item && item.pqu_id ? recordsById[item.pqu_id] : null;
    if (item && item.code === "cutoff-start-year-mismatch" && record) {
      return (
        `Microsoft lists the start as ${dates.formatDate(record.train_start_date)} ` +
        `and the change cutoff as ${dates.formatDate(record.change_cutoff_date)}; ` +
        "the years differ." +
        (options.asPublished === false ? "" : " Values are shown as published.")
      );
    }
    return item && item.message ? String(item.message) : "Source note";
  }

  function flagsByTrain(quality) {
    const byTrain = {};
    for (const item of warningItems(quality)) {
      if (item.pqu_id) {
        (byTrain[item.pqu_id] = byTrain[item.pqu_id] || []).push(item);
      }
    }
    return byTrain;
  }

  /* Warnings about a train's published dates and the date fields each makes unreliable. This
   * mirrors DATE_FLAG_FIELDS in the pipeline (insights.py); a test keeps the two in step. */
  const DATE_FLAG_FIELDS = {
    "cutoff-start-year-mismatch": ["change_cutoff_date", "train_start_date"],
    "invalid-train-duration": ["train_start_date", "train_end_date"],
    "end-before-start": ["train_start_date", "train_end_date"],
    "invalid-cutoff-date": ["change_cutoff_date"]
  };

  /* {pqu_id: Set(date fields)} questioned by source warnings. */
  function unreliableDates(quality) {
    const byTrain = {};
    for (const item of warningItems(quality)) {
      if (!item.pqu_id) {
        continue;
      }
      const fields = DATE_FLAG_FIELDS[item.code] || (item.field ? [item.field] : []);
      for (const field of fields) {
        (byTrain[item.pqu_id] = byTrain[item.pqu_id] || new Set()).add(field);
      }
    }
    return byTrain;
  }

  return {
    DATE_FLAG_FIELDS,
    STALE_MULTIPLIER,
    assess,
    describe,
    flagsByTrain,
    formatInterval,
    unreliableDates,
    warningItems
  };
});
