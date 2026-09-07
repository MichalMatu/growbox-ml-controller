from pathlib import Path

script = Path('scripts/stage28e_phase_h_closed_tent.py')
s = script.read_text()
old = 'GROWBOX_PORT = "/dev/cu.usbserial-1130"\nSHELLY_PROOF_SAMPLES = 8\n'
new = 'GROWBOX_PORT = "/dev/cu.usbserial-1130"\nSHELLY_PROOF_SAMPLES = 8\nSTAGE28D_OUTPUT_MARKER = "stage28d_output "\n'
assert old in s
s = s.replace(old, new, 1)
old = '''def send(handle: serial.Serial, command: str) -> None:\n    handle.write((command + "\\n").encode())\n    handle.flush()\n\n\n'''
new = '''def send(handle: serial.Serial, command: str) -> None:\n    handle.write((command + "\\n").encode())\n    handle.flush()\n\n\ndef is_stage28d_output_line(line: str) -> bool:\n    # ESP-IDF serial logs prefix ESP_LOG output with timestamp/tag metadata.\n    # Accept both raw service-console-style payloads and prefixed log lines.\n    return STAGE28D_OUTPUT_MARKER in line\n\n\n'''
assert old in s
s = s.replace(old, new, 1)
old = '                if line.startswith("stage28d_output ") and runtime_baseline is not None:\n'
new = '                if is_stage28d_output_line(line) and runtime_baseline is not None:\n'
assert old in s
s = s.replace(old, new, 1)
script.write_text(s)

handoff = Path('docs/STAGE28E_PHASE_H_HANDOFF.md')
h = handoff.read_text()
anchor = '## Closed-tent observer — release candidate\n'
assert anchor in h
section = '''## H v6 result and parser root cause\n\nTask:\n\n`.agent/tasks/20260907-stage28e-h-v6-closed-autonomous.json`\n\nFormal outcome: **primary FAIL, recovery/final PASS**.\n\nThe primary observer again reported:\n\n`stable safety-clear physical fan-OFF closed-tent baseline not observed`\n\nThe raw retained Mac log disproves that physical interpretation. A read-only audit found:\n\n- `24` clean safety-clear physical fan-OFF windows;\n- representative OFF windows lasted about `114-145 s`;\n- maximum clean OFF duration observed: `145.03 s`;\n- runtime ended the real-bounded observation at `arbiter_transitions=46`, `tx=50`, `tx_errors=0`;\n- recovery/final completed successfully and final RF-disabled `fake-locked` was proved.\n\nThe actual root cause was an observer parser bug. Production emits output-state telemetry through ESP-IDF logging, for example:\n\n`I (...) climate_stage27: stage28d_output ...`\n\nThe v6 observer required `line.startswith("stage28d_output ")`. Audit of the exact v6 log found:\n\n- lines containing `stage28d_output `: `576`;\n- lines starting with `stage28d_output `: `0`;\n- ESP-IDF-prefixed `climate_stage27: stage28d_output ` lines: `576`.\n\nTherefore the observer ignored 100% of arbiter/output-state samples and could never acquire its OFF baseline even though the production controller repeatedly produced valid OFF and ON states. This is a qualification-tooling false negative, not evidence of a controller, arbiter, RF or physical-output failure.\n\nThe RC observer is corrected to recognize the `stage28d_output ` marker anywhere in the serial line while preserving the same KV parsing and acceptance criteria. The preflight must regression-test both raw and ESP-IDF-prefixed forms before the next hardware H run.\n\n'''
h = h.replace(anchor, section + anchor, 1)
handoff.write_text(h)

status = Path('docs/CURRENT_STATUS.md')
c = status.read_text()
anchor = '## Closed-tent H release-candidate harness\n'
assert anchor in c
section = '''## H v6 parser false negative\n\nH v6 completed with primary FAIL but recovery/final PASS. The board returned to RF-disabled `fake-locked`.\n\nA retained-log audit established that the failure was in the observer parser, not in the deterministic controller path:\n\n- `576/576` `stage28d_output` lines were ESP-IDF-prefixed;\n- `0` began with the raw marker expected by the observer;\n- the production runtime nevertheless produced `24` clean OFF windows lasting up to about `145 s`;\n- the run reached `arbiter_transitions=46`, `tx=50`, `tx_errors=0`.\n\nThe observer now accepts `stage28d_output ` as an in-line marker so both raw and prefixed ESP-IDF serial forms are parsed. Production C/C++ remains unchanged. Formal H is still open until a corrected observer run proves the complete natural OFF->ON path and mandatory recovery/final.\n\n'''
c = c.replace(anchor, section + anchor, 1)
status.write_text(c)

plan = Path('docs/CONTINUATION_PLAN.md')
p = plan.read_text()
anchor = '## Immediate next work\n'
if anchor in p:
    section = '''## H v6 qualification-tooling finding\n\nH v6 was a false negative caused by the closed-tent observer requiring `line.startswith("stage28d_output ")` even though production ESP-IDF output prefixes every such line. Exact retained-log audit: `576` containing lines, `0` raw-starting lines, `576` ESP-IDF-prefixed lines. The same run contained `24` clean OFF windows up to about `145 s`, `46` arbiter transitions and `50` RF TX with zero TX errors. Recovery/final fake-locked passed.\n\nBefore the next physical H run, require a software-only regression/preflight proving the corrected observer parses both raw and prefixed output-state forms. Do not change production C/C++ for this fix.\n\n'''
    p = p.replace(anchor, section + anchor, 1)
else:
    p += '''\n\n## H v6 qualification-tooling finding\n\nH v6 was a false negative caused by the observer using a raw-line `startswith` check for `stage28d_output` while ESP-IDF prefixes all production output-state lines. Correct the observer only, regression-test raw and prefixed forms, and leave production C/C++ unchanged before rerunning formal H.\n'''
plan.write_text(p)
