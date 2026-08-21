#!/usr/bin/env bash
# Run scientific twin view with the project venv (absolute path — survives folder moves).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing $PY — create venv and: $PY -m pip install -e '.[twin]'" >&2
  exit 1
fi
exec "$PY" -m tools.ml.twin_view "$@"
