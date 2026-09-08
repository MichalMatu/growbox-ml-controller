import subprocess

SOURCE = ".agent/scripts/20260909-output-a13-2-software-preflight-v1-run.py"
OLD = '''namespace = runpy.run_path(str(root / "tests/test_output_supervisor_h.py"))
from tools.output_supervisor_h import replay_qualification

replay = replay_qualification(namespace["records"](), namespace["evidence"]())
if replay.qualified_sha != QUALIFIED:
    raise SystemExit(f"A13_2_REPLAY_FAIL sha={replay.qualified_sha}")
print(
    "A13_2_REPLAY_PASS "
    f"qualified_sha={replay.qualified_sha} "
    f"baseline_uptime_ms={replay.baseline_uptime_ms} "
    f"transition_uptime_ms={replay.transition_uptime_ms} "
    f"power_delta_w={replay.power_delta_w:.3f}",
    flush=True,
)
'''
NEW = '''replay_code = r\"\"\"
import runpy
from pathlib import Path
from tools.output_supervisor_h import replay_qualification

root = Path.cwd()
namespace = runpy.run_path(str(root / "tests/test_output_supervisor_h.py"))
replay = replay_qualification(namespace["records"](), namespace["evidence"]())
if replay.qualified_sha != "1c59f3cfa239abbfbae721247d01d65a39d4bdfc":
    raise SystemExit(f"A13_2_REPLAY_FAIL sha={replay.qualified_sha}")
print(
    "A13_2_REPLAY_PASS "
    f"qualified_sha={replay.qualified_sha} "
    f"baseline_uptime_ms={replay.baseline_uptime_ms} "
    f"transition_uptime_ms={replay.transition_uptime_ms} "
    f"power_delta_w={replay.power_delta_w:.3f}",
    flush=True,
)
\"\"\"
run([str(root / ".venv/bin/python"), "-c", replay_code], cwd=root)
'''

script = subprocess.check_output(["git", "show", f"FETCH_HEAD:{SOURCE}"], text=True)
if script.count(OLD) != 1:
    raise SystemExit(f"A13_2_V3_RUNNER_FAIL expected one replay block, found={script.count(OLD)}")
script = script.replace(OLD, NEW)
exec(compile(script, SOURCE, "exec"))
