import subprocess

SOURCE = ".agent/scripts/20260910-output-hw-preflight-v1-run.py"
REPLACEMENTS = {
    'CURRENT = "d9383a693f66851f5151a96f0341fd4eeaaf746d"': 'CURRENT = "014610e40ecfef96e7caddf1ee98deced2a4d64f"',
    'QUALIFIED = "1c59f3cfa239abbfbae721247d01d65a39d4bdfc"': 'QUALIFIED = "02208d23f403bca3540dbbd652eb55703a044833"',
    'EXPECTED_BIN_SIZE = 771888': 'EXPECTED_BIN_SIZE = 771920',
}

script = subprocess.check_output(["git", "show", f"FETCH_HEAD:{SOURCE}"], text=True)
for old, new in REPLACEMENTS.items():
    count = script.count(old)
    if count != 1:
        raise SystemExit(f"HW_PREFLIGHT_V2_RUNNER_FAIL replacement_count={count} old={old!r}")
    script = script.replace(old, new)

exec(compile(script, SOURCE, "exec"))
