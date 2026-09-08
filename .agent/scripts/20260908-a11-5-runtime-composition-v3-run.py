import subprocess
from pathlib import Path

SOURCE = '.agent/scripts/20260908-a11-5-runtime-composition-v1-run.py'

subprocess.run(['git', 'fetch', '-q', 'origin', 'agent-control'], check=True)
source = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)

source = source.replace('import os\nimport re\n', 'import json\nimport os\nimport re\nimport shlex\n', 1)

anchor = """def build_metrics(build_dir):
    elf_files = list(build_dir.glob('*.elf'))
"""
replacement = """def build_metrics(build_dir):
    compiler = None
    commands_path = build_dir / 'compile_commands.json'
    if commands_path.is_file():
        for entry in json.loads(commands_path.read_text()):
            arguments = entry.get('arguments')
            if arguments is None:
                command = entry.get('command', '')
                arguments = shlex.split(command) if command else []
            for token in arguments[:4]:
                candidate = Path(token)
                if candidate.name.endswith('g++') and 'xtensa' in candidate.name:
                    compiler = candidate
                    break
            if compiler is not None:
                break
    if compiler is None:
        ninja_path = build_dir / 'build.ninja'
        if ninja_path.is_file():
            ninja = ninja_path.read_text()
            match = re.search(r'(/[^\\s\"$]*xtensa-[^/\\s\"$]*-elf-g\\+\\+)', ninja)
            if match is not None:
                compiler = Path(match.group(1))
    if compiler is None or not compiler.is_file():
        raise SystemExit(f'A11_5_METRIC_FAIL unable to resolve build compiler in {build_dir}')
    compiler_name = compiler.name
    if not compiler_name.endswith('g++'):
        raise SystemExit(f'A11_5_METRIC_FAIL unexpected compiler name {compiler_name!r}')
    tool_prefix = compiler_name[:-3]
    size_tool = compiler.with_name(tool_prefix + 'size')
    objdump_tool = compiler.with_name(tool_prefix + 'objdump')
    if not size_tool.is_file() or not objdump_tool.is_file():
        raise SystemExit(
            f'A11_5_METRIC_FAIL build tool siblings missing size={size_tool} objdump={objdump_tool}'
        )
    print(f'A11_5_TOOLCHAIN compiler={compiler} size={size_tool} objdump={objdump_tool}')
    elf_files = list(build_dir.glob('*.elf'))
"""
if source.count(anchor) != 1:
    raise SystemExit(f'A11_5_V3_PATCH_FAIL metrics anchor count={source.count(anchor)}')
source = source.replace(anchor, replacement, 1)

old_size = """    size_text = shell_out(
        f'source scripts/source_idf.sh >/dev/null 2>&1; '
        f'xtensa-esp32s3-elf-size \"{elf}\"'
    )
"""
new_size = """    size_text = out([size_tool, elf])
"""
if source.count(old_size) != 1:
    raise SystemExit(f'A11_5_V3_PATCH_FAIL size block count={source.count(old_size)}')
source = source.replace(old_size, new_size, 1)

old_objdump = """    disassembly = shell_out(
        f'source scripts/source_idf.sh >/dev/null 2>&1; '
        f'xtensa-esp32s3-elf-objdump -d -C \"{elf}\"'
    )
"""
new_objdump = """    disassembly = out([objdump_tool, '-d', '-C', elf])
"""
if source.count(old_objdump) != 1:
    raise SystemExit(f'A11_5_V3_PATCH_FAIL objdump block count={source.count(old_objdump)}')
source = source.replace(old_objdump, new_objdump, 1)

Path('/tmp/a11_5_v3_inner.py').write_text(source)
subprocess.run(['python3', '/tmp/a11_5_v3_inner.py'], check=True)
