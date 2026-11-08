#!/usr/bin/env bash
# Render the static site from the committed dataset for Netlify.
#
# This is a deploy-only adapter. It does NOT run sync, does NOT write to data/ or excel/,
# does NOT contact Microsoft, and does NOT change the GitHub Pages workflow. The output is
# the same build/site directory that .github/workflows/update-pqu.yml deploys to Pages.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

# Install runtime dependencies into a scratch directory so no system Python packages,
# editable install, or virtualenv activation is needed on the build host.
deps="$(mktemp -d "${TMPDIR:-/tmp}/d365-pqu-deps.XXXXXX")"
python3 -m pip install --quiet --disable-pip-version-check --no-input \
  --target "$deps" -r requirements/runtime.lock

PYTHONPATH="src:$deps" python3 -m d365_pqu build-site

# Netlify proxies /api/health.json to Pages at request time (see netlify.toml), so its
# "Last check" is always current. This optional setting is for static copies hosted elsewhere:
# the committed data/health.json only changes when the data changes, while GitHub Pages
# publishes a health document after every daily check. Set D365_PQU_HEALTH_URL to the Pages
# /api/health.json to bake the current check into the built file instead. Failure is non-fatal:
# the committed health document stays in place.
if [ -n "${D365_PQU_HEALTH_URL:-}" ]; then
  health_tmp="build/site/api/health.json.tmp"
  if curl -fsSL --max-time 20 "$D365_PQU_HEALTH_URL" -o "$health_tmp" \
    && python3 -c 'import json, sys; json.load(open(sys.argv[1], encoding="utf-8"))' "$health_tmp"; then
    mv "$health_tmp" "build/site/api/health.json"
    echo "Refreshed api/health.json from D365_PQU_HEALTH_URL."
  else
    echo "Could not refresh api/health.json; keeping the committed copy." >&2
    rm -f "$health_tmp"
  fi
fi

echo "Static site ready at build/site"
