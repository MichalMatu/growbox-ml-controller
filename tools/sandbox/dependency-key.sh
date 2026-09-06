#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

hash_files() {
  local label="$1"
  shift
  {
    printf 'growbox-sandbox-key-v1\n'
    printf 'kind=%s\n' "$label"
    for path in "$@"; do
      printf 'file=%s\n' "$path"
      sha256sum "$path"
    done
  } | sha256sum | awk '{print $1}'
}

case "${1:-}" in
  host)
    hash_files host requirements-lock.txt requirements-dev.txt pyproject.toml .pre-commit-config.yaml
    ;;
  web)
    hash_files web web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml
    ;;
  idf)
    {
      printf 'growbox-sandbox-key-v1\n'
      printf 'kind=idf\n'
      printf 'esp-idf=5.5.4\n'
      printf 'target=esp32s3\n'
      printf 'esp-clang=managed-by-idf-tools\n'
      printf 'host=x86_64-linux\n'
    } | sha256sum | awk '{print $1}'
    ;;
  *)
    echo "usage: $0 {host|web|idf}" >&2
    exit 2
    ;;
esac
