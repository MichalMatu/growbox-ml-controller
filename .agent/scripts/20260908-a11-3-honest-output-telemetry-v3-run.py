import subprocess
from pathlib import Path

SOURCE = '.agent/scripts/20260908-a11-3-honest-output-telemetry-v1-run.py'

subprocess.run(['git', 'fetch', '-q', 'origin', 'agent-control'], check=True)
source = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)

old = r"""replace_once(
    'src/climate/output/ClimateOutputSupervisorSink.cpp',
    '''  last_resolution_ = {};\n  last_report_ = {};\n  if (!valid()) {\n''',
    '''  last_control_intent_ = {};\n  last_resolution_ = {};\n  last_report_ = {};\n  if (!valid()) {\n''',
)
"""
new = r"""replace_once(
    'src/climate/output/ClimateOutputSupervisorSink.cpp',
    '''  using ::growbox::app::output::SafetyConstraint;\n\n  last_resolution_ = {};\n  last_report_ = {};\n  if (!valid()) {\n''',
    '''  using ::growbox::app::output::SafetyConstraint;\n\n  last_control_intent_ = {};\n  last_resolution_ = {};\n  last_report_ = {};\n  if (!valid()) {\n''',
)
"""

count = source.count(old)
if count != 1:
    raise SystemExit(f'A11_3_V3_PATCH_FAIL target count={count}')
patched = source.replace(old, new, 1)
Path('/tmp/a11_3_v3_inner.py').write_text(patched)
subprocess.run(['python3', '/tmp/a11_3_v3_inner.py'], check=True)
