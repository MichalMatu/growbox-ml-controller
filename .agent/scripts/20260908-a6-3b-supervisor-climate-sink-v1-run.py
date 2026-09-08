import os
import subprocess
from pathlib import Path

EXPECTED = "7655dd505d14597b22d07302ae7a6cd7b2e9b116"
FILES = [
    "src/CMakeLists.txt",
    "src/climate/output/ClimateOutputSupervisorSink.cpp",
    "src/climate/output/ClimateOutputSupervisorSink.h",
    "test/host/CMakeLists.txt",
    "test/test_climate_output_supervisor_sink/test_main.cpp",
]

def run(command: str) -> None:
    subprocess.run(command, shell=True, check=True, executable="/bin/bash")

def out(command: str) -> str:
    return subprocess.check_output(command, shell=True, text=True, executable="/bin/bash").strip()

run("git fetch -q origin mvp/environment-controller")
assert out("git rev-parse HEAD") == EXPECTED
assert out("git rev-parse FETCH_HEAD") == EXPECTED
assert out("git status --porcelain") == ""
print("A6_3B_IDENTITY_PASS")

run("git fetch -q origin agent-control")
script = subprocess.check_output(
    ["git", "show", "FETCH_HEAD:.agent/scripts/20260908-a6-3b-supervisor-climate-sink-v1.py"],
    text=True,
)
edit_path = Path("/tmp/a6_3b_edit.py")
edit_path.write_text(script)
run(f"python3 {edit_path}")
run("git add -N " + " ".join(FILES))
run("git diff --check")

header = Path("src/climate/output/ClimateOutputSupervisorSink.h").read_text()
source = Path("src/climate/output/ClimateOutputSupervisorSink.cpp").read_text()
assert "class ClimateOutputSupervisorSink" in header
assert "resolver_.resolve" in source
assert "executor_.execute" in source
assert "last_successful_command" in source
assert "fail_safe_fallback_->applyFailSafeOff" in source
assert "ClimateV6RealInputRuntime.cpp" not in out("git diff --name-only")
assert not any(path.startswith("src/climate/rf433/") for path in out("git diff --name-only").splitlines())
print("A6_3B_STATIC_PASS")

build_dir = "build/host-tests-a6-3b-v1"
run(f"cmake -S test/host -B {build_dir}")
run(
    f"cmake --build {build_dir} --parallel --target "
    "climate_output_supervisor_sink_tests climate_control_loop_tests "
    "output_supervisor_resolver_tests output_supervisor_executor_tests"
)
run(
    f"ctest --test-dir {build_dir} -R "
    "'^(climate_output_supervisor_sink_tests|climate_control_loop_tests|"
    "output_supervisor_resolver_tests|output_supervisor_executor_tests)$' --output-on-failure"
)
print("A6_3B_FOCUSED_PASS")

env = os.environ.copy()
env.update(
    {
        "STAGE27C_BUILD_DIR": "build/idf-a6-3b-v1",
        "STAGE27C_SDKCONFIG": "build/idf-a6-3b-v1/sdkconfig",
        "GROWBOX_RF433_LOOPBACK_ENABLED": "1",
        "GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED": "1",
        "GROWBOX_RF433_LOOPBACK_AUTO_SMOKE": "0",
        "GROWBOX_RF433_REMOTE_CAPTURE_ENABLED": "0",
    }
)
subprocess.run(["bash", "scripts/stage27c_crowpanel.sh", "build"], check=True, env=env)
print("A6_3B_CANONICAL_RF_BUILD_PASS")

actual = sorted(out("git diff --name-only").splitlines())
assert actual == sorted(FILES), (actual, FILES)
run("git diff --check")
run("git add " + " ".join(FILES))
run("git diff --cached --check")
run("git commit -m 'Bridge climate sink to output supervisor'")
new_head = out("git rev-parse HEAD")
run("git push origin HEAD:mvp/environment-controller")
assert out("git status --porcelain") == ""
print(f"A6_3B_PASS commit={new_head}")
