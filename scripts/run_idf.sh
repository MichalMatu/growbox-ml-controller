#!/usr/bin/env bash
# Run idf.py with ESP-IDF on PATH (sources scripts/source_idf.sh when needed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# shellcheck disable=SC1091
source "$ROOT/scripts/source_idf.sh"

exec idf.py "$@"
