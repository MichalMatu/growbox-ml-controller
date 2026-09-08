import subprocess
from pathlib import Path

SOURCE = '.agent/scripts/20260908-a11-3-honest-output-telemetry-v1-run.py'

subprocess.run(['git', 'fetch', '-q', 'origin', 'agent-control'], check=True)
source = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)

old = '''replace_once(\n    'src/climate/output/ClimateOutputSupervisorSink.cpp',\n    '''  last_resolution_ = {};\\n  last_report_ = {};\\n  if (!valid()) {\\n''',\n    '''  last_control_intent_ = {};\\n  last_resolution_ = {};\\n  last_report_ = {};\\n  if (!valid()) {\\n''',\n)\n'''
new = '''replace_once(\n    'src/climate/output/ClimateOutputSupervisorSink.cpp',\n    '''  using ::growbox::app::output::SafetyConstraint;\\n\\n  last_resolution_ = {};\\n  last_report_ = {};\\n  if (!valid()) {\\n''',\n    '''  using ::growbox::app::output::SafetyConstraint;\\n\\n  last_control_intent_ = {};\\n  last_resolution_ = {};\\n  last_report_ = {};\\n  if (!valid()) {\\n''',\n)\n'''

if source.count(old) != 1:
    raise SystemExit(f'A11_3_V2_PATCH_FAIL target count={source.count(old)}')
patched = source.replace(old, new, 1)
Path('/tmp/a11_3_v2_inner.py').write_text(patched)
subprocess.run(['python3', '/tmp/a11_3_v2_inner.py'], check=True)
