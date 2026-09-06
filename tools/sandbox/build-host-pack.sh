#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

OUT="${1:-$ROOT/build/sandbox-host-pack}"
KEY="$(tools/sandbox/dependency-key.sh host)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
STAGE="$TMP/stage"
mkdir -p "$STAGE/python" "$STAGE/wheelhouse" "$STAGE/llvm/bin" "$STAGE/llvm/lib" "$STAGE/meta"

PYTHON_BIN="${SANDBOX_PACK_PYTHON:-$(command -v python3.11 || true)}"
[[ -n "$PYTHON_BIN" ]] || { echo "Python 3.11 is required to build host pack" >&2; exit 1; }
"$PYTHON_BIN" - <<'PY'
import sys
assert sys.version_info[:2] == (3, 11), sys.version
PY

PY_PREFIX="$("$PYTHON_BIN" -c 'import sys; print(sys.prefix)')"
cp -a "$PY_PREFIX"/. "$STAGE/python/"
"$STAGE/python/bin/python3.11" - <<'PY'
import sys
assert sys.version_info[:2] == (3, 11), sys.version
print(sys.version)
PY

"$PYTHON_BIN" -m pip download \
  --dest "$STAGE/wheelhouse" \
  -r requirements-lock.txt \
  -r requirements-dev.txt \
  'clang-format==19.1.5' \
  'PyYAML==6.0.2' \
  'pip==26.1.2' \
  'setuptools>=75,<82' \
  'wheel>=0.45,<1'

CLANG_TIDY="$(command -v clang-tidy || command -v clang-tidy-18 || true)"
[[ -n "$CLANG_TIDY" ]] || { echo "clang-tidy is required to build host pack" >&2; exit 1; }
CLANG_TIDY="$(readlink -f "$CLANG_TIDY")"
cp "$CLANG_TIDY" "$STAGE/llvm/bin/clang-tidy.real"

while read -r lib; do
  [[ -f "$lib" ]] || continue
  case "$(basename "$lib")" in
    libc.so.*|libm.so.*|libpthread.so.*|libdl.so.*|librt.so.*|libgcc_s.so.*|libstdc++.so.*|ld-linux*.so.*)
      continue
      ;;
  esac
  cp -L "$lib" "$STAGE/llvm/lib/$(basename "$lib")"
done < <(ldd "$CLANG_TIDY" | awk '/=> \// {print $3} /^\// {print $1}')

cat > "$STAGE/llvm/bin/clang-tidy" <<'EOF'
#!/usr/bin/env bash
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export LD_LIBRARY_PATH="$HERE/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$HERE/bin/clang-tidy.real" "$@"
EOF
chmod +x "$STAGE/llvm/bin/clang-tidy"

cp requirements-lock.txt requirements-dev.txt pyproject.toml "$STAGE/meta/"
printf '3.11\n' > "$STAGE/meta/python-version.txt"
printf '19.1.5\n' > "$STAGE/meta/clang-format-version.txt"
"$STAGE/llvm/bin/clang-tidy" --version > "$STAGE/meta/clang-tidy-version.txt"

tools/sandbox/finalize-pack.sh "$STAGE" growbox-host "$KEY" "$OUT"
