#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PC="${ROOT}/.venv/bin/pre-commit"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

if [[ ! -x "$PC" ]]; then
  echo "pre-commit missing — run: make setup-dev" >&2
  exit 1
fi

echo "==> pre-commit (all files)"
"$PC" run --all-files

bash "${ROOT}/scripts/quality_gate_push.sh"

echo "quality gate: OK"
