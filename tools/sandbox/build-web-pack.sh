#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

OUT="${1:-$ROOT/build/sandbox-web-pack}"
KEY="$(tools/sandbox/dependency-key.sh web)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
STAGE="$TMP/stage"
mkdir -p "$STAGE/pnpm" "$STAGE/store" "$STAGE/meta"

node -e 'const m=+process.versions.node.split(".")[0]; if (m !== 22) process.exit(1)'
npm install --prefix "$STAGE/pnpm" --no-audit --no-fund --ignore-scripts pnpm@11.10.0
PNPM=(node "$STAGE/pnpm/node_modules/pnpm/bin/pnpm.cjs")

"${PNPM[@]}" --version | grep -Fx '11.10.0'
"${PNPM[@]}" --dir web fetch --frozen-lockfile --store-dir "$STAGE/store"

cp web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml "$STAGE/meta/"
printf '22\n' > "$STAGE/meta/node-major.txt"
printf '11.10.0\n' > "$STAGE/meta/pnpm-version.txt"

tools/sandbox/finalize-pack.sh "$STAGE" growbox-web "$KEY" "$OUT"
