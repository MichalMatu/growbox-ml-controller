import json
import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import urllib.request
from pathlib import Path

CURRENT = "d9383a693f66851f5151a96f0341fd4eeaaf746d"
QUALIFIED = "1c59f3cfa239abbfbae721247d01d65a39d4bdfc"
PORT = "/dev/cu.usbserial-1130"
FORBIDDEN = "/dev/cu.usbserial-10"
EXPECTED_BIN_SIZE = 771888
SHELLY_URL = "http://192.168.0.16/rpc/Switch.GetStatus?id=0"


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
    raise SystemExit(f"HW_PREFLIGHT_IDENTITY_FAIL head={head} remote={remote} expected={CURRENT}")
if output(["git", "status", "--porcelain"], cwd=root):
    raise SystemExit("HW_PREFLIGHT_IDENTITY_FAIL worktree_dirty=1")
if not Path(PORT).exists():
    raise SystemExit(f"HW_PREFLIGHT_PORT_FAIL missing={PORT} forbidden_port_untouched={FORBIDDEN}")

real_cmake = shutil.which("cmake")
real_ninja = shutil.which("ninja")
if not real_cmake:
    raise SystemExit("HW_PREFLIGHT_BUILD_FAIL cmake_not_found=1")
wrapper_dir = Path(tempfile.mkdtemp(prefix="growbox-hw-preflight-bin-"))
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

worktree = Path(tempfile.mkdtemp(prefix="growbox-hw-preflight-qualified-"))
worktree.rmdir()
try:
    run(["git", "worktree", "add", "--detach", str(worktree), QUALIFIED], cwd=root)
    if output(["git", "rev-parse", "HEAD"], cwd=worktree) != QUALIFIED:
        raise SystemExit("HW_PREFLIGHT_BUILD_FAIL detached_identity=0")

    env = os.environ.copy()
    env["PATH"] = str(wrapper_dir) + os.pathsep + env.get("PATH", "")
    env["CMAKE_BUILD_PARALLEL_LEVEL"] = "2"
    env["NINJAFLAGS"] = "-j2"
    env["GROWBOX_FIRMWARE_GIT_SHA"] = QUALIFIED
    env["GROWBOX_RF433_LOOPBACK_ENABLED"] = "1"
    env["GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED"] = "1"
    env["GROWBOX_RF433_REMOTE_CAPTURE_ENABLED"] = "0"
    env["GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED"] = "0"
    env["GROWBOX_STAGE28E_BREADCRUMB_RESTART_SELFTEST"] = "0"
    env["PORT"] = PORT
    build_dir = worktree / "build/idf-hw-preflight-qualified-real"
    env["STAGE27C_BUILD_DIR"] = str(build_dir)

    run(["bash", "scripts/stage27c_crowpanel.sh", "build"], cwd=worktree, env=env)
    firmware = build_dir / "growbox_ml_controller.bin"
    elf = build_dir / "growbox_ml_controller.elf"
    if not firmware.exists() or not elf.exists():
        raise SystemExit("HW_PREFLIGHT_BUILD_FAIL firmware_artifacts_missing=1")
    marker = QUALIFIED.encode()
    if marker not in firmware.read_bytes() or marker not in elf.read_bytes():
        raise SystemExit("HW_PREFLIGHT_BUILD_FAIL embedded_sha=0")
    if firmware.stat().st_size != EXPECTED_BIN_SIZE:
        raise SystemExit(
            f"HW_PREFLIGHT_BUILD_FAIL firmware_size={firmware.stat().st_size} expected={EXPECTED_BIN_SIZE}"
        )
    print(
        f"HW_PREFLIGHT_BUILD_PASS sha={QUALIFIED} firmware_bin={firmware.stat().st_size} "
        f"port={PORT} forbidden_port_untouched={FORBIDDEN}",
        flush=True,
    )

    print(f"HW_PREFLIGHT_FLASH_START sha={QUALIFIED} port={PORT}", flush=True)
    run(["bash", "scripts/stage27c_crowpanel.sh", "flash"], cwd=worktree, env=env)
    print(f"HW_PREFLIGHT_FLASH_PASS sha={QUALIFIED} port={PORT}", flush=True)

    serial_code = textwrap.dedent(
        f'''\
        import re
        import time
        import serial

        PORT = {PORT!r}
        QUALIFIED = {QUALIFIED!r}
        FORBIDDEN = {FORBIDDEN!r}

        ser = serial.Serial(port=None, baudrate=115200, timeout=0.2, write_timeout=1)
        ser.dtr = False
        ser.rts = False
        ser.port = PORT
        ser.open()
        status_ok = False
        soak_ok = False
        sd_ok = False
        sensors_ok = False
        automation_disabled = False
        off_requested = False
        boot_ids = set()
        lines = []
        started = time.monotonic()
        next_command = 0.0
        try:
            while time.monotonic() - started < 120.0:
                now = time.monotonic()
                raw = ser.readline()
                if raw:
                    line = raw.decode(errors="replace").strip()
                    lines.append(line)
                    print(line, flush=True)
                    if "status firmware_sha=" in line:
                        m = re.search(r"status firmware_sha=([^ ]+).*?boot_id=([^ ]+).*?outputs=([^ ]+).*?rf_ready=([01])", line)
                        if m and m.group(1) == QUALIFIED and m.group(3) == "real-bounded" and m.group(4) == "1":
                            status_ok = True
                            boot_ids.add(m.group(2))
                    if "soak_v=3 firmware_sha=" in line:
                        if f"firmware_sha={{QUALIFIED}}" in line and "output_v=2" in line:
                            soak_ok = True
                        if "storage_sd_mounted=1" in line:
                            sd_ok = True
                        if "tp_sample=1" in line and "xiaomi_sample=1" in line:
                            sensors_ok = True
                    if "automation mode=Automatic" in line and not off_requested:
                        ser.write(b"automation off\\n")
                        ser.flush()
                        off_requested = True
                        print("HW_PREFLIGHT_AUTOMATION_OFF_REQUESTED supervisor_owned=1", flush=True)
                    if "automation mode=Disabled requested=off transition_active=0 request_pending=0" in line:
                        automation_disabled = True
                if now >= next_command:
                    ser.write(b"status\\n")
                    ser.write(b"sensors\\n")
                    ser.write(b"sdlog status\\n")
                    ser.write(b"automation status\\n")
                    ser.flush()
                    next_command = now + 4.0
                if status_ok and soak_ok and sd_ok and sensors_ok and automation_disabled and len(boot_ids) == 1:
                    break
                time.sleep(0.01)
        finally:
            ser.close()

        if not status_ok:
            raise SystemExit("HW_PREFLIGHT_RUNTIME_FAIL qualified_real_status=0")
        if not soak_ok:
            raise SystemExit("HW_PREFLIGHT_RUNTIME_FAIL output_v2=0")
        if not sd_ok:
            raise SystemExit("HW_PREFLIGHT_RUNTIME_FAIL sd_mounted=0")
        if not sensors_ok:
            raise SystemExit("HW_PREFLIGHT_RUNTIME_FAIL tp_xiaomi_samples=0")
        if not automation_disabled:
            raise SystemExit("HW_PREFLIGHT_RECOVERY_FAIL automation_disabled=0")
        if len(boot_ids) != 1:
            raise SystemExit(f"HW_PREFLIGHT_RUNTIME_FAIL boot_ids={{sorted(boot_ids)}}")
        print(
            f"HW_PREFLIGHT_RUNTIME_PASS sha={{QUALIFIED}} port={{PORT}} output_v=2 outputs=real-bounded "
            f"sd=PASS sensors=PASS automation_final=Disabled forbidden_port_untouched={{FORBIDDEN}}",
            flush=True,
        )
        '''
    )
    run([str(root / ".venv/bin/python"), "-c", serial_code], cwd=root)

    try:
        with urllib.request.urlopen(SHELLY_URL, timeout=5) as response:
            shelly = json.load(response)
        master_on = bool(shelly.get("output", False))
        power_w = float(shelly.get("apower", 0.0))
        voltage_v = float(shelly.get("voltage", 0.0))
        if not master_on:
            raise SystemExit("HW_PREFLIGHT_SHELLY_FAIL master_on=0")
        print(
            f"HW_PREFLIGHT_SHELLY_PASS master_on=1 power_w={power_w:.2f} voltage_v={voltage_v:.2f} read_only=1",
            flush=True,
        )
    except Exception as exc:
        raise SystemExit(f"HW_PREFLIGHT_SHELLY_FAIL error={type(exc).__name__}:{exc}") from exc

    print(
        f"OUTPUT_SUPERVISOR_HW_PREFLIGHT_PASS sha={QUALIFIED} port={PORT} flash=PASS runtime=PASS "
        f"output_v2=PASS sd=PASS sensors=PASS shelly=PASS final_mode=Disabled raw_rf=0 "
        f"forbidden_port_untouched={FORBIDDEN} hardware_started=1",
        flush=True,
    )
finally:
    subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=root, check=False)
    shutil.rmtree(wrapper_dir, ignore_errors=True)

if output(["git", "status", "--porcelain"], cwd=root):
    raise SystemExit("HW_PREFLIGHT_FINAL_FAIL worktree_dirty=1")
