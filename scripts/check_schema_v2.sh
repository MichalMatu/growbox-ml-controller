#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
PY="${ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi
exec "$PY" "${ROOT}/tools/schema/generate_environment_schema.py" \
  --schema "${ROOT}/schemas/environment-controller-v2.json" \
  --output "${ROOT}/lib/environment_control/src/EnvironmentSchemaV2.h" \
  --check
