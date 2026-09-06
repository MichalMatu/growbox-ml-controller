from __future__ import annotations

import json
import re
from pathlib import Path

RESULT = Path('/tmp/growbox-ah-arbiter-clean-v5-result.json')

data = json.loads(RESULT.read_text())
output = '\n'.join(str(command.get('output', '')) for command in data.get('commands', []))
lines = output.splitlines()

stage_re = re.compile(r'stage28d_output .*?arbiter_dwell_holds=(\d+)')
esp_ms_re = re.compile(r'^[A-Z] \((\d+)\)')
boot_tokens = (
    'ESP-ROM:', 'rst:', 'boot:', 'entry 0x', 'Stage27 soak boot:', 'reset_reason=',
    'I2C probe:', 'Stage27 real-input runtime:', 'Brownout', 'Guru Meditation',
    'abort()', 'watchdog', 'WDT', 'Rebooting',
)

stages: list[tuple[int, int | None, int, str]] = []
for index, line in enumerate(lines):
    match = stage_re.search(line)
    if not match:
        continue
    ms_match = esp_ms_re.search(line.strip())
    stages.append((index, int(ms_match.group(1)) if ms_match else None, int(match.group(1)), line.strip()))

print(f'V5_DIAG_STAGE_LINES count={len(stages)}')
if not stages:
    raise RuntimeError('no stage28d_output lines found in V5 result')

for line in lines:
    if any(token in line for token in boot_tokens):
        print('V5_DIAG_BOOT ' + line.strip())

found_drop = False
for previous, current in zip(stages, stages[1:]):
    p_index, p_ms, p_dwell, p_line = previous
    c_index, c_ms, c_dwell, c_line = current
    dwell_drop = c_dwell < p_dwell
    clock_drop = p_ms is not None and c_ms is not None and c_ms < p_ms
    if not (dwell_drop or clock_drop):
        continue
    found_drop = True
    between = lines[p_index + 1:c_index]
    markers = [line.strip() for line in between if any(token in line for token in boot_tokens)]
    print(
        'V5_DIAG_DISCONTINUITY '
        f'prev_dwell={p_dwell} curr_dwell={c_dwell} prev_esp_ms={p_ms} curr_esp_ms={c_ms} '
        f'dwell_drop={int(dwell_drop)} clock_drop={int(clock_drop)} boot_markers_between={len(markers)}'
    )
    print('V5_DIAG_PREV ' + p_line)
    for marker in markers:
        print('V5_DIAG_BETWEEN ' + marker)
    print('V5_DIAG_CURR ' + c_line)

if not found_drop:
    print('V5_DIAG_NO_COUNTER_OR_CLOCK_DROP')

for marker in ('AHV2_CLEAN_BASELINE_PASS', 'AHV2_AH_REQUEST_GE_010', 'AHV2_PRIMARY_ERROR', 'AHV2_RECOVERY_PASS'):
    for line in lines:
        if marker in line:
            print('V5_DIAG_MARKER ' + line.strip())

print('V5_DIAG_PASS offline_only=1 serial_opened=0 hardware_touched=0')
