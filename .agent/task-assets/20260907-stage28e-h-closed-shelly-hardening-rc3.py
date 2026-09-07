from pathlib import Path

script = Path("scripts/stage28e_phase_h_closed_tent.py")
s = script.read_text()
replacements = [
    (
        'GROWBOX_PORT = "/dev/cu.usbserial-1130"\n',
        'GROWBOX_PORT = "/dev/cu.usbserial-1130"\nSHELLY_PROOF_SAMPLES = 8\n',
    ),
    (
        '    transition: Optional[tuple[float, dict[str, str]]] = None\n    transition_time: Optional[float] = None\n\n    env_samples: list[EnvSample] = []\n',
        '    transition: Optional[tuple[float, dict[str, str]]] = None\n    transition_time: Optional[float] = None\n    pre_load_state: Optional[tuple[int, int]] = None\n    proof_load_state: Optional[tuple[int, int]] = None\n    proof_power_sealed = False\n    post_state_confirmations = 0\n\n    env_samples: list[EnvSample] = []\n',
    ),
    (
        '                            off_baseline = clean_candidates[-1]\n                            on, power, voltage, _ = shelly_status()\n',
        '                            off_baseline = clean_candidates[-1]\n                            pre_load_state = (lamp_on, humidifier_on)\n                            on, power, voltage, _ = shelly_status()\n',
    ),
    (
        '                            if request >= 0.10:\n                                first_request = (now, values)\n                                print(\n',
        '                            if request >= 0.10:\n                                first_request = (now, values)\n                                proof_load_state = (lamp_on, humidifier_on)\n                                print(\n',
    ),
    (
        '                    else:\n                        if (\n                            first_request is None\n',
        '                    else:\n                        load_state = (lamp_on, humidifier_on)\n                        if proof_load_state is None:\n                            if pre_load_state is None:\n                                pre_load_state = load_state\n                            elif load_state != pre_load_state:\n                                shelly_before.clear()\n                                pre_load_state = load_state\n                        elif not proof_power_sealed and load_state != proof_load_state:\n                            raise AssertionError(\n                                "Shelly fan proof confounded by lamp/humidifier state change during proof window"\n                            )\n                        elif (\n                            transition_time is not None\n                            and not proof_power_sealed\n                            and load_state == proof_load_state\n                        ):\n                            post_state_confirmations += 1\n\n                        if (\n                            first_request is None\n',
    ),
    (
        '                        ):\n                            first_request = (now, values)\n                            print(\n                                "STAGE28E_H_CLOSED_REQUEST_SEEN "\n                                "at_off_baseline=0 "\n',
        '                        ):\n                            first_request = (now, values)\n                            proof_load_state = load_state\n                            print(\n                                "STAGE28E_H_CLOSED_REQUEST_SEEN "\n                                "at_off_baseline=0 "\n',
    ),
    (
        '                    if transition_time is None:\n                        shelly_before.append(power)\n                    else:\n                        shelly_after.append(power)\n                    if voltage is not None:\n',
        '                    if transition_time is None:\n                        shelly_before.append(power)\n                    elif not proof_power_sealed:\n                        shelly_after.append(power)\n                        if (\n                            len(shelly_after) >= SHELLY_PROOF_SAMPLES\n                            and post_state_confirmations >= 1\n                        ):\n                            proof_power_sealed = True\n                            print(\n                                "STAGE28E_H_CLOSED_SHELLY_PROOF_WINDOW_SEALED "\n                                f"samples={len(shelly_after)} confirmations={post_state_confirmations}",\n                                flush=True,\n                            )\n                    if voltage is not None:\n',
    ),
    (
        '        assert shelly_after, "no Shelly evidence after fan transition"\n\n        before_power = shelly_before[-8:]\n        after_power = shelly_after[:8]\n',
        '        assert shelly_after, "no Shelly evidence after fan transition"\n        assert proof_power_sealed, (\n            "Shelly proof window did not complete with stable lamp/humidifier state",\n            len(shelly_after),\n            post_state_confirmations,\n        )\n\n        before_power = shelly_before[-SHELLY_PROOF_SAMPLES:]\n        after_power = shelly_after[:SHELLY_PROOF_SAMPLES]\n',
    ),
]

for old, new in replacements:
    count = s.count(old)
    assert count == 1, (count, old[:160])
    s = s.replace(old, new, 1)
script.write_text(s)

handoff = Path("docs/STAGE28E_PHASE_H_HANDOFF.md")
t = handoff.read_text()
old = """Because Shelly measures combined controlled-load power rather than fan-only power, the observer rejects a proof if lamp or humidifier state changes between the captured fan request and fan transition. That prevents a simultaneous ~97 W lamp or ~15.7 W humidifier transition from being mistaken for the ~3 W fan load.

With lamp/humidifier stable, the observer requires:
"""
new = """Because Shelly measures combined controlled-load power rather than fan-only power, the observer rejects a proof if lamp or humidifier state changes between the captured fan request and fan transition. The physical-power proof window then remains open until eight post-transition Shelly samples are collected and at least one subsequent `stage28d_output` sample confirms that lamp/humidifier state is still unchanged. Any confounder change before that proof window is sealed fails the run. Later load changes during the remaining environmental-response window do not rewrite the already sealed fan-power evidence.

With lamp/humidifier stable through that proof window, the observer requires:
"""
assert t.count(old) == 1, t.count(old)
handoff.write_text(t.replace(old, new, 1))
