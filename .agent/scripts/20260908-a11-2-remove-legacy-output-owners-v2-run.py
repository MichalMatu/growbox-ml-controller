import subprocess
from pathlib import Path

SOURCE = '.agent/scripts/20260908-a11-2-remove-legacy-output-owners-v1-run.py'

subprocess.run(['git', 'fetch', '-q', 'origin', 'agent-control'], check=True)
source = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)
lines = source.splitlines(keepends=True)
needle = "replace_once(runtime_path, '    fail_safe_output_driver.disableReal();\\n', '')"
matches = [index for index, line in enumerate(lines) if needle in line]
if len(matches) != 1:
    raise SystemExit(f'A11_2_V2_PATCH_FAIL disableReal source-line matches={matches!r}')
index = matches[0]
replacement = '''text = Path(runtime_path).read_text()\nlegacy_disable = '    fail_safe_output_driver.disableReal();\\n'\nif text.count(legacy_disable) != 3:\n    raise SystemExit(\n        f'{runtime_path}: expected three legacy disableReal calls, found {text.count(legacy_disable)}'\n    )\nPath(runtime_path).write_text(text.replace(legacy_disable, ''))\n'''
lines[index:index + 1] = [replacement]
patched = ''.join(lines)
Path('/tmp/a11_2_v2_inner.py').write_text(patched)
subprocess.run(['python3', '/tmp/a11_2_v2_inner.py'], check=True)
