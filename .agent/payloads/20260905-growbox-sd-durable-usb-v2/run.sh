#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
BASE=/tmp/20260905-growbox-sd-durable-usb-v1-base.sh
RUN=/tmp/20260905-growbox-sd-durable-usb-v2-run.sh
git fetch -q origin agent-control
git show origin/agent-control:.agent/payloads/20260905-growbox-sd-durable-usb-v1/run.sh > "$BASE"
python3 - "$BASE" "$RUN" <<'PY'
from pathlib import Path
import sys
src = Path(sys.argv[1]).read_text()
old = '''    char path[80]{};\n    std::snprintf(path,sizeof(path),"%s/%s",kSdLogDirectory,entry->d_name);\n    struct stat st {};\n'''
new = '''    char path[64]{};\n    const int path_length =\n        std::snprintf(path, sizeof(path), "%s/%.11s", kSdLogDirectory, entry->d_name);\n    if (path_length <= 0 || static_cast<std::size_t>(path_length) >= sizeof(path)) continue;\n    struct stat st {};\n'''
if src.count(old) != 1:
    raise SystemExit(f'list path target count={src.count(old)}')
src = src.replace(old, new, 1)
old = '''  char path[80]{};\n  std::snprintf(path,sizeof(path),"%s/%s",kSdLogDirectory,command.filename.data());\n  std::FILE* file=std::fopen(path,"rb");\n'''
new = '''  char path[64]{};\n  const int path_length = std::snprintf(path, sizeof(path), "%s/%.11s", kSdLogDirectory,\n                                        command.filename.data());\n  if (path_length <= 0 || static_cast<std::size_t>(path_length) >= sizeof(path)) {\n    writeText("sdlog_error op=read reason=path\\r\\n");\n    return;\n  }\n  std::FILE* file=std::fopen(path,"rb");\n'''
if src.count(old) != 1:
    raise SystemExit(f'read path target count={src.count(old)}')
src = src.replace(old, new, 1)
Path(sys.argv[2]).write_text(src)
PY
bash -n "$RUN"
bash "$RUN"
