/* Entry point. Runs after every module in the bundle has registered itself on PQU. */
(function (root) {
  "use strict";

  const PQU = root.PQU;
  try {
    PQU.app.start().catch((error) => PQU.app.showLoadError(error));
  } catch (error) {
    PQU.app.showLoadError(error);
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
