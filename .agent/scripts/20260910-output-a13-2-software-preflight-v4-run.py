import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

CURRENT = "014610e40ecfef96e7caddf1ee98deced2a4d64f"
QUALIFIED = "02208d23f403bca3540dbbd652eb55703a044833"
EXPECTED_CHANGED = {
    "docs/ARCHITECTURE_HANDOFF.md",
    "docs/CURRENT_STATUS.md",
    "docs/STAGE28E_OUTPUT_SUPERVISOR_H_QUALIFICATION.md",
    "tools/output_supervisor_h.py",
}
EXPECTED_BIN_SIZE = 771920


def run(command, *, cwd=None, env=None):
    print(f"+ {' '.join(map(str, command))}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def output(command, *, cwd=None, env=None):
    print(f"+ {' '.join(map(str, command))}", flush=True)
    return subprocess.check_output(command, cwd=cwd, env=env, text=True).strip()


root = Path(output(["git", "rev-parse", "--show-toplevel"]))
run(["git", "fetch", "-q", "origin", "mvp/environment-controller", QUALIFIED], cwd=root)
head = output(["git", "rev-parse", "HEAD"], cwd=root)
remote = output(["git", "rev-parse", "origin/mvp/environment-controller"], cwd=root)
if head != CURRENT or remote != CURRENT:
    raise SystemExit(f"A13_2_IDENTITY_FAIL head={head} remote={remote} expected={CURRENT}")
if output(["git", "status", "--porcelain"], cwd=root):
    raise SystemExit("A13_2_IDENTITY_FAIL worktree is dirty")

changed = set(output(["git", "diff", "--name-only", f"{QUALIFIED}..{CURRENT}"], cwd=root).splitlines())
if changed != EXPECTED_CHANGED:
    raise SystemExit(f"A13_2_SCOPE_FAIL changed={sorted(changed)!r}")
run(
    [
        "git",
        "diff",
        "--quiet",
        f"{QUALIFIED}..{CURRENT}",
        "--",
        "src",
        "lib",
        "config",
        "scripts",
        "CMakeLists.txt",
        "CMakePresets.json",
    ],
    cwd=root,
)
print(f"A13_2_SCOPE_PASS current_sha={CURRENT} qualified_sha={QUALIFIED}", flush=True)

run(
    [
        str(root / ".venv/bin/pre-commit"),
        "run",
        "--files",
        "tools/output_supervisor_h.py",
        "tests/test_output_supervisor_h.py",
        "docs/STAGE28E_OUTPUT_SUPERVISOR_H_QUALIFICATION.md",
        "docs/CURRENT_STATUS.md",
        "docs/ARCHITECTURE_HANDOFF.md",
    ],
    cwd=root,
)
run([str(root / ".venv/bin/python"), "-m", "pytest", "-q", "tests/test_output_supervisor_h.py"], cwd=root)
run([str(root / ".venv/bin/python"), "-m", "py_compile", "tools/output_supervisor_h.py"], cwd=root)

replay_code = f'''\nimport runpy\nfrom pathlib import Path\nfrom tools.output_supervisor_h import replay_qualification\n\nroot = Path.cwd()\nnamespace = runpy.run_path(str(root / "tests/test_output_supervisor_h.py"))\nreplay = replay_qualification(namespace["records"](), namespace["evidence"]())\nif replay.qualified_sha != "{QUALIFIED}":\n    raise SystemExit(f"A13_2_REPLAY_FAIL sha={{replay.qualified_sha}}")\nprint(\n    "A13_2_REPLAY_PASS "\n    f"qualified_sha={{replay.qualified_sha}} "\n    f"baseline_uptime_ms={{replay.baseline_uptime_ms}} "\n    f"transition_uptime_ms={{replay.transition_uptime_ms}} "\n    f"power_delta_w={{replay.power_delta_w:.3f}}",\n    flush=True,\n)\n'''
run([str(root / ".venv/bin/python"), "-c", replay_code], cwd=root)

real_cmake = shutil.which("cmake")
real_ninja = shutil.which("ninja")
if not real_cmake:
    raise SystemExit("A13_2_BUILD_FAIL cmake not found")
wrapper_dir = Path(tempfile.mkdtemp(prefix="a13-2-bin-"))
cmake_wrapper = wrapper_dir / "cmake"
cmake_wrapper.write_text(
    "#!/usr/bin/env python3\n"
    "import os, sys\n"
    f"REAL = {real_cmake!r}\n"
    "args = sys.argv[1:]\n"
    "out = []\n"
    "i = 0\n"
    "while i < len(args):\n"
    "    arg = args[i]\n"
    "    out.append(arg)\n"
    "    if arg == '--parallel':\n"
    "        if i + 1 >= len(args) or args[i + 1].startswith('-') or not args[i + 1].isdigit():\n"
    "            out.append('2')\n"
    "    i += 1\n"
    "os.execv(REAL, [REAL, *out])\n"
)
cmake_wrapper.chmod(cmake_wrapper.stat().st_mode | stat.S_IXUSR)
if real_ninja:
    ninja_wrapper = wrapper_dir / "ninja"
    ninja_wrapper.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        f"REAL = {real_ninja!r}\n"
        "args = sys.argv[1:]\n"
        "has_jobs = any(a == '-j' or a.startswith('-j') or a == '--jobs' or a.startswith('--jobs=') for a in args)\n"
        "if not has_jobs:\n"
        "    args = ['-j2', *args]\n"
        "os.execv(REAL, [REAL, *args])\n"
    )
    ninja_wrapper.chmod(ninja_wrapper.stat().st_mode | stat.S_IXUSR)

worktree = Path(tempfile.mkdtemp(prefix="growbox-a13-2-qualified-"))
worktree.rmdir()
try:
    run(["git", "worktree", "add", "--detach", str(worktree), QUALIFIED], cwd=root)
    if output(["git", "rev-parse", "HEAD"], cwd=worktree) != QUALIFIED:
        raise SystemExit("A13_2_BUILD_FAIL detached worktree identity mismatch")
    if output(["git", "status", "--porcelain"], cwd=worktree):
        raise SystemExit("A13_2_BUILD_FAIL detached worktree is dirty before build")

    env = os.environ.copy()
    env["PATH"] = str(wrapper_dir) + os.pathsep + env.get("PATH", "")
    env["CMAKE_BUILD_PARALLEL_LEVEL"] = "2"
    env["NINJAFLAGS"] = "-j2"
    env["GROWBOX_FIRMWARE_GIT_SHA"] = QUALIFIED
    env["GROWBOX_RF433_LOOPBACK_ENABLED"] = "1"
    env["GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED"] = "1"
    env["GROWBOX_RF433_LOOPBACK_AUTO_SMOKE"] = "0"
    env["GROWBOX_RF433_REMOTE_CAPTURE_ENABLED"] = "0"
    env["GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED"] = "0"
    env["GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST"] = "0"
    env.pop("PORT", None)
    env.pop("GROWBOX_BOARD_PORT", None)
    build_dir = worktree / "build/idf-a13-2-qualified-real"
    env["STAGE27C_BUILD_DIR"] = str(build_dir)
    run(["bash", "scripts/stage27c_crowpanel.sh", "build"], cwd=worktree, env=env)

    elf_files = list(build_dir.glob("*.elf"))
    bin_files = [path for path in build_dir.glob("*.bin") if path.name not in {"bootloader.bin", "partition-table.bin"}]
    if len(elf_files) != 1:
        raise SystemExit(f"A13_2_BUILD_FAIL expected one ELF, found={elf_files!r}")
    if not bin_files:
        raise SystemExit("A13_2_BUILD_FAIL application BIN not found")
    elf = elf_files[0]
    firmware = max(bin_files, key=lambda path: path.stat().st_size)
    marker = QUALIFIED.encode()
    if marker not in elf.read_bytes():
        raise SystemExit("A13_2_BUILD_FAIL qualified SHA not embedded in ELF")
    if marker not in firmware.read_bytes():
        raise SystemExit("A13_2_BUILD_FAIL qualified SHA not embedded in firmware BIN")
    firmware_size = firmware.stat().st_size
    if firmware_size != EXPECTED_BIN_SIZE:
        raise SystemExit(f"A13_2_BUILD_FAIL firmware size={firmware_size} expected={EXPECTED_BIN_SIZE}")
    print(
        "A13_2_QUALIFIED_BUILD_PASS "
        f"sha={QUALIFIED} firmware_bin={firmware_size} "
        "real_outputs=1 rf_enabled=1 serial=0 flash=0",
        flush=True,
    )
finally:
    subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=root, check=False)
    shutil.rmtree(wrapper_dir, ignore_errors=True)

run(["git", "diff", "--check"], cwd=root)
if output(["git", "status", "--porcelain"], cwd=root):
    raise SystemExit("A13_2_FINAL_FAIL current worktree became dirty")
print(
    "A13_2_SOFTWARE_PREFLIGHT_PASS "
    f"current_sha={CURRENT} qualified_sha={QUALIFIED} "
    "scope=PASS contract_tests=PASS replay=PASS qualified_build=PASS "
    "serial_started=0 flash_started=0 rf_started=0 hardware_started=0",
    flush=True,
)
