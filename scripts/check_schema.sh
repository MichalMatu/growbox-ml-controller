#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
exec bash "${ROOT}/scripts/check_schema_v3.sh"
