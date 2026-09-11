#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "src/CMakeLists.txt"
text = path.read_text()

legacy_line = '      "demo/protocol/HeapDiagnostics.cpp"\n'
assert text.count(legacy_line) == 1
text = text.replace(legacy_line, "", 1)

common_anchor = '    "main.cpp"\n'
assert text.count(common_anchor) == 1
text = text.replace(common_anchor, common_anchor + '    "demo/protocol/HeapDiagnostics.cpp"\n', 1)

path.write_text(text)
