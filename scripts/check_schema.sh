#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
exec "${ROOT}/.venv/bin/python" "${ROOT}/tools/schema/generate_environment_schema.py" --check
