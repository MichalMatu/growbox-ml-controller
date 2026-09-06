#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <sandbox-root> [--host PACK] [--web PACK] [--idf PACK]" >&2
  exit 2
fi

SANDBOX_ROOT="$(realpath -m "$1")"
shift
HOST_PACK=""
WEB_PACK=""
IDF_PACK=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST_PACK="$2"; shift 2 ;;
    --web) WEB_PACK="$2"; shift 2 ;;
    --idf) IDF_PACK="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$SANDBOX_ROOT/packs" "$SANDBOX_ROOT/bin"
ENV_FILE="$SANDBOX_ROOT/env.sh"
: > "$ENV_FILE"
cat >> "$ENV_FILE" <<EOF
export GROWBOX_SANDBOX_ROOT='$SANDBOX_ROOT'
export GROWBOX_SOURCE_ROOT='$ROOT'
export PYTHONNOUSERSITE=1
EOF

expected_key() {
  local kind="$1"
  local meta="$ROOT/.sandbox-snapshot/${kind}-key.txt"
  if [[ -f "$meta" ]]; then
    cat "$meta"
  else
    "$ROOT/tools/sandbox/dependency-key.sh" "$kind"
  fi
}

load_pack() {
  local kind="$1" pack="$2"
  local expected actual dest
  expected="$(expected_key "$kind")"
  actual="$(cat "$pack/manifest/dependency-key.txt")"
  [[ "$actual" == "$expected" ]] || {
    echo "$kind pack key mismatch: source expects $expected, pack has $actual" >&2
    exit 1
  }
  dest="$SANDBOX_ROOT/packs/${kind}-${actual}"
  if [[ ! -f "$dest/.dependency-key" ]] || [[ "$(cat "$dest/.dependency-key")" != "$actual" ]]; then
    "$ROOT/tools/sandbox/unpack-pack.sh" "$pack" "$dest" >/dev/null
  fi
  printf '%s' "$dest"
}

if [[ -n "$HOST_PACK" ]]; then
  HOST_DIR="$(load_pack host "$(realpath "$HOST_PACK")")"
  PY="$HOST_DIR/python/bin/python3.11"
  "$PY" -m venv --copies --clear "$SANDBOX_ROOT/venv"
  "$SANDBOX_ROOT/venv/bin/python" -m ensurepip --upgrade >/dev/null
  "$SANDBOX_ROOT/venv/bin/python" -m pip install \
    --no-index --find-links "$HOST_DIR/wheelhouse" \
    -r requirements-lock.txt -r requirements-dev.txt \
    'clang-format==19.1.5' 'PyYAML==6.0.2' >/dev/null
  cat >> "$ENV_FILE" <<EOF
export GROWBOX_SANDBOX_HOST_PACK='$HOST_DIR'
export PATH='$SANDBOX_ROOT/venv/bin:$HOST_DIR/llvm/bin':"\$PATH"
export VIRTUAL_ENV='$SANDBOX_ROOT/venv'
EOF
fi

if [[ -n "$WEB_PACK" ]]; then
  WEB_DIR="$(load_pack web "$(realpath "$WEB_PACK")")"
  NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
  [[ "$NODE_MAJOR" == "22" ]] || { echo "Node.js 22 required, got $(node --version)" >&2; exit 1; }
  cat > "$SANDBOX_ROOT/bin/pnpm" <<EOF
#!/usr/bin/env bash
exec node '$WEB_DIR/pnpm/node_modules/pnpm/bin/pnpm.cjs' "\$@"
EOF
  chmod +x "$SANDBOX_ROOT/bin/pnpm"
  "$SANDBOX_ROOT/bin/pnpm" --dir web install \
    --frozen-lockfile --offline --store-dir "$WEB_DIR/store"
  cat >> "$ENV_FILE" <<EOF
export GROWBOX_SANDBOX_WEB_PACK='$WEB_DIR'
export PATH='$SANDBOX_ROOT/bin':"\$PATH"
EOF
fi

if [[ -n "$IDF_PACK" ]]; then
  [[ -n "${HOST_DIR:-}" ]] || { echo "--idf requires --host because ESP-IDF Python is recreated with the packed Python 3.11 runtime" >&2; exit 1; }
  IDF_DIR="$(load_pack idf "$(realpath "$IDF_PACK")")"
  "$HOST_DIR/python/bin/python3.11" -m venv --copies --clear "$SANDBOX_ROOT/idf-python"
  "$SANDBOX_ROOT/idf-python/bin/python" -m ensurepip --upgrade >/dev/null
  "$SANDBOX_ROOT/idf-python/bin/python" -m pip install \
    --no-index --find-links "$IDF_DIR/wheelhouse" \
    -r "$IDF_DIR/meta/idf-python-requirements.txt" >/dev/null

  cat >> "$ENV_FILE" <<EOF
export GROWBOX_SANDBOX_IDF_PACK='$IDF_DIR'
export IDF_PATH='$IDF_DIR/esp-idf'
export IDF_TOOLS_PATH='$IDF_DIR/idf-tools'
export IDF_PYTHON_ENV_PATH='$SANDBOX_ROOT/idf-python'
export IDF_EXPORT_SH='$SANDBOX_ROOT/idf-export.sh'
EOF
  cat > "$SANDBOX_ROOT/idf-export.sh" <<EOF
#!/usr/bin/env bash
export IDF_PATH='$IDF_DIR/esp-idf'
export IDF_TOOLS_PATH='$IDF_DIR/idf-tools'
export IDF_PYTHON_ENV_PATH='$SANDBOX_ROOT/idf-python'
export PATH='$SANDBOX_ROOT/idf-python/bin:$IDF_DIR/esp-idf/tools':"\$PATH"
eval "\$('$SANDBOX_ROOT/idf-python/bin/python' '$IDF_DIR/esp-idf/tools/idf_tools.py' export --format key-value)"
EOF
  chmod +x "$SANDBOX_ROOT/idf-export.sh"
fi

echo "Wrote $ENV_FILE"
echo "Run: source '$ENV_FILE'"
