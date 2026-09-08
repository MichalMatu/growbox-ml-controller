import subprocess
from pathlib import Path

SOURCE = '.agent/scripts/20260908-a11-5-runtime-composition-v1-run.py'

subprocess.run(['git', 'fetch', '-q', 'origin', 'agent-control'], check=True)
source = subprocess.check_output(['git', 'show', f'FETCH_HEAD:{SOURCE}'], text=True)

anchor = """def build_metrics(build_dir):
    elf_files = list(build_dir.glob('*.elf'))
"""
replacement = """def build_metrics(build_dir):
    cache_text = (build_dir / 'CMakeCache.txt').read_text()
    compiler_match = re.search(r'^CMAKE_CXX_COMPILER:FILEPATH=(.+)$', cache_text, flags=re.M)
    if compiler_match is None:
        compiler_match = re.search(r'^CMAKE_CXX_COMPILER:STRING=(.+)$', cache_text, flags=re.M)
    if compiler_match is None:
        raise SystemExit(f'A11_5_METRIC_FAIL CMAKE_CXX_COMPILER missing in {build_dir}')
    compiler = Path(compiler_match.group(1).strip())
    compiler_name = compiler.name
    if compiler_name.endswith('g++'):
        tool_prefix = compiler_name[:-3]
    elif compiler_name.endswith('gcc'):
        tool_prefix = compiler_name[:-3]
    else:
        raise SystemExit(f'A11_5_METRIC_FAIL unexpected compiler name {compiler_name!r}')
    size_tool = compiler.with_name(tool_prefix + 'size')
    objdump_tool = compiler.with_name(tool_prefix + 'objdump')
    if not size_tool.is_file() or not objdump_tool.is_file():
        raise SystemExit(
            f'A11_5_METRIC_FAIL build tool siblings missing size={size_tool} objdump={objdump_tool}'
        )
    elf_files = list(build_dir.glob('*.elf'))
"""
if source.count(anchor) != 1:
    raise SystemExit(f'A11_5_V2_PATCH_FAIL metrics anchor count={source.count(anchor)}')
source = source.replace(anchor, replacement, 1)

old_size = "f'xtensa-esp32s3-elf-size \"{elf}\"'"
new_size = "f'\"{size_tool}\" \"{elf}\"'"
if source.count(old_size) != 1:
    raise SystemExit(f'A11_5_V2_PATCH_FAIL size call count={source.count(old_size)}')
source = source.replace(old_size, new_size, 1)

old_objdump = "f'xtensa-esp32s3-elf-objdump -d -C \"{elf}\"'"
new_objdump = "f'\"{objdump_tool}\" -d -C \"{elf}\"'"
if source.count(old_objdump) != 1:
    raise SystemExit(f'A11_5_V2_PATCH_FAIL objdump call count={source.count(old_objdump)}')
source = source.replace(old_objdump, new_objdump, 1)

Path('/tmp/a11_5_v2_inner.py').write_text(source)
subprocess.run(['python3', '/tmp/a11_5_v2_inner.py'], check=True)
