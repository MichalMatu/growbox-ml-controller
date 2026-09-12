from pathlib import Path

moves = {
    Path('src/climate/OutputBindings.cpp'): Path('src/climate/output/OutputBindings.cpp'),
    Path('src/climate/OutputBindings.h'): Path('src/climate/output/OutputBindings.h'),
    Path('src/climate/LampSafety.cpp'): Path('src/climate/output/LampSafety.cpp'),
    Path('src/climate/LampSafety.h'): Path('src/climate/output/LampSafety.h'),
}
for src, dst in moves.items():
    assert src.exists(), src
    assert not dst.exists(), dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    src.rename(dst)

replacements = {
    'climate/OutputBindings.h': 'climate/output/OutputBindings.h',
    'climate/LampSafety.h': 'climate/output/LampSafety.h',
    'climate/OutputBindings.cpp': 'climate/output/OutputBindings.cpp',
    'climate/LampSafety.cpp': 'climate/output/LampSafety.cpp',
    'src/climate/OutputBindings.cpp': 'src/climate/output/OutputBindings.cpp',
    'src/climate/LampSafety.cpp': 'src/climate/output/LampSafety.cpp',
}
roots = [Path('src'), Path('test'), Path('scripts')]
files = [Path('CMakeLists.txt')]
for root in roots:
    if root.exists():
        files.extend(p for p in root.rglob('*') if p.is_file() and p.suffix in {'.cpp', '.h', '.py', '.sh', '.txt'})
files.extend([Path('src/CMakeLists.txt'), Path('test/host/CMakeLists.txt')])
seen = set()
for path in files:
    if path in seen or not path.exists():
        continue
    seen.add(path)
    text = path.read_text()
    updated = text
    for old, new in replacements.items():
        updated = updated.replace(old, new)
    if updated != text:
        path.write_text(updated)
