#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

hash_files() {
  local label="$1"
  shift
  {
    printf 'growbox-sandbox-key-v2\n'
    printf 'kind=%s\n' "$label"
    for path in "$@"; do
      printf 'file=%s\n' "$path"
      sha256sum "$path"
    done
  } | sha256sum | awk '{print $1}'
}

case "${1:-}" in
  host)
    hash_files host \
      requirements-lock.txt \
      requirements-dev.txt \
      pyproject.toml \
      .pre-commit-config.yaml \
      tools/sandbox/build-host-pack.sh \
      tools/sandbox/finalize-pack.sh
    ;;
  web)
    hash_files web \
      web/package.json \
      web/pnpm-lock.yaml \
      web/pnpm-workspace.yaml \
      tools/sandbox/build-web-pack.sh \
      tools/sandbox/finalize-pack.sh
    ;;
  idf)
    {
      printf 'growbox-sandbox-key-v2\n'
      printf 'kind=idf\n'
      printf 'esp-idf=5.5.4\n'
      printf 'target=esp32s3\n'
      printf 'esp-clang=managed-by-idf-tools\n'
      printf 'host=x86_64-linux\n'
      printf 'file=tools/sandbox/build-idf-pack.sh\n'
      sha256sum tools/sandbox/build-idf-pack.sh
      printf 'file=tools/sandbox/finalize-pack.sh\n'
      sha256sum tools/sandbox/finalize-pack.sh
    } | sha256sum | awk '{print $1}'
    ;;
  *)
    echo "usage: $0 {host|web|idf}" >&2
    exit 2
    ;;
esac
