from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'check_output_rf_ownership.py'


def load_guard():
    spec = spec_from_file_location('output_execution_ownership_guard', SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_output_execution_ownership_is_single_owner():
    guard = load_guard()
    assert guard.find_violations(ROOT) == []


def test_retired_compatibility_sources_are_not_production_scan_targets(tmp_path):
    guard = load_guard()
    retired = tmp_path / 'src' / 'climate' / 'Stage28dRfOutputEndpoint.cpp'
    retired.parent.mkdir(parents=True)
    retired.write_text('transport_.send(command);\n')
    active = tmp_path / 'src' / 'climate' / 'output' / 'OutputSupervisorExecutor.cpp'
    active.parent.mkdir(parents=True)
    active.write_text('transport_.send(command);\n')
    assert [guard.relative(tmp_path, path) for path in guard.production_cpp(tmp_path)] == [
        'src/climate/output/OutputSupervisorExecutor.cpp'
    ]


def test_low_level_rmt_allowlist_rejects_runtime_bypass(tmp_path):
    guard = load_guard()
    allowed = tmp_path / 'src' / 'climate' / 'rf433' / 'Rf433RmtLoopback.cpp'
    allowed.parent.mkdir(parents=True)
    allowed.write_text('rmt_transmit(tx, enc, data, size, cfg);\n')
    runtime = tmp_path / 'src' / 'climate' / 'ClimateV6RealInputRuntime.cpp'
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text('rmt_transmit(tx, enc, data, size, cfg);\n')

    sites = guard.cpp_sites(tmp_path, 'rmt_transmit(')
    assert sites == {
        'src/climate/rf433/Rf433RmtLoopback.cpp',
        'src/climate/ClimateV6RealInputRuntime.cpp',
    }
    assert sites - guard.LOW_LEVEL_RMT['rmt_transmit('] == {
        'src/climate/ClimateV6RealInputRuntime.cpp'
    }


def test_raw_transport_send_allowlist_rejects_new_production_owner(tmp_path):
    guard = load_guard()
    runtime = tmp_path / 'src' / 'climate' / 'ClimateV6RealInputRuntime.cpp'
    runtime.parent.mkdir(parents=True)
    runtime.write_text('transport_.send(command);\n')
    assert guard.RAW_SEND_RE.search(runtime.read_text()) is not None
    assert 'src/climate/ClimateV6RealInputRuntime.cpp' not in guard.RAW_SEND_ALLOW
