# Contributing

## Local checks

Install the locked dependencies and editable package, then run:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python -m pytest
.venv/bin/python -m d365_pqu verify
```

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
