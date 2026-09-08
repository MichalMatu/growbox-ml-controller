import json
import os
import re
import shutil
import subprocess
from pathlib import Path

BASE = '578f902ce43cdb3631798ec7e0a6341082c50a49'
BRANCH = 'mvp/environment-controller'
FAKE_DIR = Path('build/a12-final-fake-output')
REAL_DIR = Path('build/a12-final-real-output')


def run(cmd, env=None):
    print('+', ' '.join(str(x) for x in cmd), flush=True)
    subprocess.run([str(x) for x in cmd], check=True, env=env)


def out(cmd, env=None):
    return subprocess.check_output([str(x) for x in cmd], text=True, env=env).strip()


def assert_identity(stage):
    run(['git', 'fetch', '-q', 'origin', BRANCH])
    head = out(['git', 'rev-parse', 'HEAD'])
    remote = out(['git', 'rev-parse', 'FETCH_HEAD'])
    status = out(['git', 'status', '--porcelain'])
    if head != BASE or remote != BASE or status:
        raise SystemExit(
            f'A12_2_IDENTITY_FAIL stage={stage} head={head} remote={remote} status={status!r}'
        )
    print(f'A12_2_IDENTITY_PASS stage={stage} sha={BASE}')


def canonical_env(build_dir, real_outputs, rf_enabled):
    env = os.environ.copy()
    env.update({
        'STAGE27C_BUILD_DIR': str(build_dir),
        'STAGE27C_SDKCONFIG': str(build_dir / 'sdkconfig'),
        'GROWBOX_RF433_LOOPBACK_ENABLED': '1' if rf_enabled else '0',
        'GROWBOX_STAGE28_REAL_OUTPUTS_ENABLED': '1' if real_outputs else '0',
        'GROWBOX_RF433_LOOPBACK_AUTO_SMOKE': '0',
        'GROWBOX_STAGE28_THERMAL_TEST_SEQUENCE_ENABLED': '0',
        'GROWBOX_RF433_REMOTE_CAPTURE_ENABLED': '0',
    })
    return env


def build_canonical(build_dir, real_outputs, rf_enabled):
    shutil.rmtree(build_dir, ignore_errors=True)
    run(
        ['bash', 'scripts/stage27c_crowpanel.sh', 'build'],
        env=canonical_env(build_dir, real_outputs, rf_enabled),
    )


def toolchain_from_compile_commands(build_dir):
    compile_commands = build_dir / 'compile_commands.json'
    if not compile_commands.is_file():
        raise SystemExit(f'A12_2_METRIC_FAIL missing {compile_commands}')
    entries = json.loads(compile_commands.read_text())
    compiler = None
    for entry in entries:
        command = entry.get('command', '')
        match = re.search(r'([^\s"\']*xtensa-esp32s3-elf-g\+\+)', command)
        if match:
            compiler = Path(match.group(1))
            break
        arguments = entry.get('arguments') or []
        if arguments and 'xtensa-esp32s3-elf-g++' in arguments[0]:
            compiler = Path(arguments[0])
            break
    if compiler is None or not compiler.is_file():
        raise SystemExit(f'A12_2_METRIC_FAIL compiler not found from {compile_commands}')
    prefix = compiler.name[:-3]
    size_tool = compiler.with_name(prefix + 'size')
    objdump_tool = compiler.with_name(prefix + 'objdump')
    if not size_tool.is_file() or not objdump_tool.is_file():
        raise SystemExit(
            f'A12_2_METRIC_FAIL tool siblings missing size={size_tool} objdump={objdump_tool}'
        )
    return compiler, size_tool, objdump_tool


def build_metrics(build_dir):
    elf_files = list(build_dir.glob('*.elf'))
    bin_files = [p for p in build_dir.glob('*.bin') if p.is_file()]
    if len(elf_files) != 1:
        raise SystemExit(f'A12_2_METRIC_FAIL expected one ELF in {build_dir}, found={elf_files!r}')
    elf = elf_files[0]
    compiler, size_tool, objdump_tool = toolchain_from_compile_commands(build_dir)
    size_text = out([size_tool, elf])
    rows = [line.split() for line in size_text.splitlines() if line.strip()]
    if len(rows) < 2 or len(rows[-1]) < 6:
        raise SystemExit(f'A12_2_METRIC_FAIL unexpected size output {size_text!r}')
    text_size = int(rows[-1][0], 0)
    data_size = int(rows[-1][1], 0)
    bss_size = int(rows[-1][2], 0)

    disassembly = out([objdump_tool, '-d', '-C', elf])
    marker = 'growbox::app::climate_io::runClimateV6RealInputRuntime()'
    pos = disassembly.find(marker)
    if pos < 0:
        raise SystemExit('A12_2_STACK_FAIL runtime symbol missing from real-output ELF')
    window = disassembly[pos:pos + 2500]
    frame_match = re.search(r'\bentry\s+a1,\s*(0x[0-9a-fA-F]+|\d+)', window)
    if frame_match is None:
        raise SystemExit('A12_2_STACK_FAIL unable to parse Xtensa runtime entry frame')
    runtime_frame = int(frame_match.group(1), 0)

    sdkconfig = (build_dir / 'sdkconfig').read_text()
    stack_match = re.search(r'^CONFIG_ESP_MAIN_TASK_STACK_SIZE=(\d+)$', sdkconfig, flags=re.M)
    if stack_match is None:
        raise SystemExit('A12_2_STACK_FAIL CONFIG_ESP_MAIN_TASK_STACK_SIZE missing')
    main_stack = int(stack_match.group(1))
    firmware_bin = build_dir / 'growbox_ml_controller.bin'
    bin_size = firmware_bin.stat().st_size if firmware_bin.is_file() else max(
        (p.stat().st_size for p in bin_files), default=0
    )
    return {
        'compiler': str(compiler),
        'text': text_size,
        'data': data_size,
        'bss': bss_size,
        'static_dram': data_size + bss_size,
        'firmware_bin': bin_size,
        'runtime_frame': runtime_frame,
        'main_stack': main_stack,
    }


assert_identity('start')
run(['git', 'diff', '--check'])

# Formatting, lint, and schema checks. Any auto-fix invalidates the immutable candidate.
run(['.venv/bin/pre-commit', 'run', '--all-files'])
if out(['git', 'status', '--porcelain']):
    raise SystemExit('A12_2_SOURCE_CHANGED_FAIL pre-commit modified the immutable candidate')
run(['bash', 'scripts/check_schema.sh'])
print('A12_2_LINT_FORMAT_SCHEMA_PASS')

# Canonical repository-wide software pre-push gate. Hardware-marked tests and duplicate
# firmware builds are excluded here; exact fake/real firmware profiles run below.
quality_env = os.environ.copy()
quality_env['SKIP_IDF_BUILD'] = '1'
run(['bash', 'scripts/quality_gate_push.sh'], env=quality_env)
print('A12_2_PREPUSH_PASS')

# Required build-only firmware profiles. No serial, flash, monitor, USB probing, or RF TX.
build_canonical(FAKE_DIR, real_outputs=False, rf_enabled=False)
print('A12_2_FAKE_FIRMWARE_PASS')
build_canonical(REAL_DIR, real_outputs=True, rf_enabled=True)
print('A12_2_REAL_FIRMWARE_PASS')

run(['python3', 'scripts/check_output_rf_ownership.py'])
metrics = build_metrics(REAL_DIR)
if metrics['main_stack'] != 16384:
    raise SystemExit(f"A12_2_STACK_FAIL RF main stack={metrics['main_stack']} expected=16384")
if metrics['runtime_frame'] <= 0:
    raise SystemExit(f"A12_2_STACK_FAIL runtime frame invalid={metrics['runtime_frame']}")
print('A12_2_METRICS ' + ' '.join(f'{k}={v}' for k, v in metrics.items()))

assert_identity('end')
run(['git', 'diff', '--check'])
print(
    'A12_2_FINAL_FULL_PASS '
    f'sha={BASE} python_tests=PASS host_cpp_tests=PASS lint_format_schema=PASS prepush=PASS '
    f'ownership=PASS fake_firmware=PASS real_firmware=PASS rf_enabled=PASS '
    f'main_stack={metrics["main_stack"]} runtime_frame={metrics["runtime_frame"]} '
    f'text={metrics["text"]} data={metrics["data"]} bss={metrics["bss"]} '
    f'static_dram={metrics["static_dram"]} firmware_bin={metrics["firmware_bin"]} '
    'hardware_started=0'
)
