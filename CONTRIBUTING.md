# Contributing

## Local checks

Install the locked dependencies, the editable package, and Playwright's Chromium, then run:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python -m pytest
.venv/bin/python -m d365_pqu verify
```

`pytest` includes the JavaScript unit tests in `tests/js/` (run with Node in several time zones) and the browser tests in `tests/e2e/` (Playwright Chromium against sites built from fixtures). Without Node or Chromium those tests are skipped locally; CI requires them.

## Dashboard changes

- Logic that needs no DOM goes in `src/d365_pqu/static/js/core/` and gets a Node unit test in `tests/js/` that mentions the module (`core/<name>.js`); a test enforces this.
- Every script must be listed in `JS_BUNDLE` in `site.py`, in load order.
- Build DOM with `PQU.ui.dom.el`. Do not use `innerHTML`, inline styles, inline event handlers, `eval`, or anything from another origin; the Content-Security-Policy blocks them and a test checks the scripts.
- Label every calculated value as calculated, and show Microsoft's values as published.
- Check new colours with `tests/test_contrast.py` and new views with the accessibility audit in `tests/e2e/test_e2e_a11y.py`.
- Playwright predicates must be functions (`"() => ..."`); expression strings need `eval`, which the policy blocks.

## Parser changes

1. Add or update a focused fixture under `tests/fixtures/`.
2. Add a test for the new Microsoft structure and a failure case.
3. Keep fatal structural changes fail-closed.
4. Do not weaken validation merely to make a malformed source publish.
5. Run a live dry run and inspect the quality report before opening a pull request.

## Generated files

Do not manually edit `data/`, `excel/`, or `build/site/`. They are generated from the source and are replaced transactionally by the sync pipeline.

## Dependencies

Runtime and development dependencies are declared in `requirements/*.in` and locked in `requirements/*.lock`. Dependabot opens weekly update pull requests for Python and GitHub Actions dependencies.
