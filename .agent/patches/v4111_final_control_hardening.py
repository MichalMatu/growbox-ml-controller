from __future__ import annotations

from pathlib import Path

ROOT = Path('/Users/michal/local-agent-v4.11.1-logging-staging')

# agentd: widen self-update validation margin, explicitly compile production parallel modules,
# and use remote branch evidence for control ACK durability.
p = ROOT / 'agentd.py'
s = p.read_text(encoding='utf-8')
assert 'SELF_UPDATE_INTERVAL = 60\n' in s
s = s.replace(
    'SELF_UPDATE_INTERVAL = 60\n',
    'SELF_UPDATE_INTERVAL = 60\nSELF_UPDATE_VALIDATION_TIMEOUT_SECONDS = 600\n',
    1,
)
assert '            "agent_multirepo.py",\n            "agent_repo_admin.py",' in s
s = s.replace(
    '            "agent_multirepo.py",\n            "agent_repo_admin.py",',
    '            "agent_multirepo.py",\n            "agent_parallel.py",\n            "agent_parallel_worker.py",\n            "agent_repo_admin.py",',
    1,
)
assert '                timeout=300,\n                log_commands=False,\n' in s
s = s.replace(
    '                timeout=300,\n                log_commands=False,\n',
    '                timeout=SELF_UPDATE_VALIDATION_TIMEOUT_SECONDS,\n                log_commands=False,\n',
    1,
)
needle = '''def _control_ack_path(control_id: str) -> Path:\n    return core.CONTROL / REMOTE_CONTROL_ACK_DIR / f"{control_id}.json"\n\n\n'''
insert = '''def _control_ack_path(control_id: str) -> Path:\n    return core.CONTROL / REMOTE_CONTROL_ACK_DIR / f"{control_id}.json"\n\n\ndef control_ack_published(control_id: str) -> bool:\n    """Return True only when the ACK is visible on the fetched remote control branch."""\n    relative = f"{REMOTE_CONTROL_ACK_DIR}/{control_id}.json"\n    result = core.process(\n        [\n            "git",\n            "ls-tree",\n            "--name-only",\n            f"origin/{core.CONTROL_BRANCH}",\n            "--",\n            relative,\n        ],\n        core.CONTROL,\n        timeout=30,\n        log_commands=False,\n    )\n    if result["exit_code"] != 0:\n        raise RuntimeError(storage.git_failure_diagnostic(result))\n    return relative in str(result.get("output", "")).splitlines()\n\n\n'''
assert needle in s
s = s.replace(needle, insert, 1)
old = '''    if not control_id or len(control_id) > 120 or _control_ack_path(control_id).exists():\n        return\n\n    if action == "restart":\n'''
new = '''    if not control_id or len(control_id) > 120:\n        return\n    try:\n        if control_ack_published(control_id):\n            return\n    except Exception as exc:\n        log(f"control ACK verification failed for {control_id}: {type(exc).__name__}: {exc}")\n        return\n\n    if action == "restart":\n'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# Parallel active-worker probe must also distinguish a local-only ACK from a remotely published ACK.
p = ROOT / 'agent_parallel.py'
s = p.read_text(encoding='utf-8')
old = '''    ack = agentd.core.CONTROL / agentd.REMOTE_CONTROL_ACK_DIR / f"{control_id}.json"\n    return not ack.exists()\n'''
new = '''    try:\n        return not agentd.control_ack_published(control_id)\n    except Exception as exc:\n        log(f"control ACK probe degraded id={control_id}: {type(exc).__name__}: {exc}")\n        return False\n'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# Repository-scoped status requests use the same remote ACK durability rule. Global actions still
# remain supervisor-owned and return before any repository-local ACK lookup.
p = ROOT / 'agent_repo_worker.py'
s = p.read_text(encoding='utf-8')
old = '''    if (\n        not control_id\n        or len(control_id) > 120\n        or not _CONTROL_ID_RE.fullmatch(control_id)\n        or _control_ack_path(control_id).exists()\n    ):\n        return\n\n    if action == "status":\n'''
new = '''    if (\n        not control_id\n        or len(control_id) > 120\n        or not _CONTROL_ID_RE.fullmatch(control_id)\n    ):\n        return\n\n    if action in {"restart", "self_update"}:\n        # These are global supervisor actions. A fast per-repository worker must\n        # leave them unacknowledged so the supervisor can own the request.\n        return\n\n    try:\n        if agentd.control_ack_published(control_id):\n            return\n    except Exception as exc:\n        core.log(\n            f"repository control ACK verification failed id={control_id}: "\n            f"{type(exc).__name__}: {exc}"\n        )\n        return\n\n    if action == "status":\n'''
assert old in s
s = s.replace(old, new, 1)
old = '''    if action in {"restart", "self_update"}:\n        # These are global supervisor actions. A fast per-repository worker must\n        # leave them unacknowledged so the supervisor can own the request.\n        return\n\n    publish_repository_control_ack(\n'''
assert old in s
s = s.replace(old, '    publish_repository_control_ack(\n', 1)
p.write_text(s, encoding='utf-8')

# Unit tests: self-update validation and remote ACK lookup.
p = ROOT / 'tests/test_agentd.py'
s = p.read_text(encoding='utf-8')
needle = '''        self.assertIn("agent_repository.py", compile_command)\n        self.assertIn("agent_version.py", compile_command)\n'''
replacement = '''        self.assertIn("agent_repository.py", compile_command)\n        self.assertIn("agent_parallel.py", compile_command)\n        self.assertIn("agent_parallel_worker.py", compile_command)\n        self.assertIn("agent_version.py", compile_command)\n        self.assertEqual(compile_kwargs["timeout"], agentd.SELF_UPDATE_VALIDATION_TIMEOUT_SECONDS)\n        self.assertEqual(calls[1][1]["timeout"], agentd.SELF_UPDATE_VALIDATION_TIMEOUT_SECONDS)\n'''
assert needle in s
s = s.replace(needle, replacement, 1)
marker = '    def test_remote_restart_control_is_acknowledged_before_restart(self) -> None:\n'
extra = '''    def test_control_ack_published_checks_remote_tracking_branch(self) -> None:\n        relative = f"{agentd.REMOTE_CONTROL_ACK_DIR}/ack-1.json"\n        with mock.patch.object(\n            agentd.core,\n            "process",\n            return_value={"exit_code": 0, "output": relative + "\\n"},\n        ) as process:\n            self.assertTrue(agentd.control_ack_published("ack-1"))\n        self.assertEqual(\n            process.call_args.args[0],\n            [\n                "git",\n                "ls-tree",\n                "--name-only",\n                f"origin/{agentd.core.CONTROL_BRANCH}",\n                "--",\n                relative,\n            ],\n        )\n        self.assertFalse(process.call_args.kwargs["log_commands"])\n\n    def test_control_ack_local_only_is_not_considered_published(self) -> None:\n        ack = agentd._control_ack_path("local-only")\n        ack.parent.mkdir(parents=True, exist_ok=True)\n        ack.write_text("{}\\n", encoding="utf-8")\n        with mock.patch.object(\n            agentd.core,\n            "process",\n            return_value={"exit_code": 0, "output": ""},\n        ):\n            self.assertFalse(agentd.control_ack_published("local-only"))\n\n'''
assert marker in s
s = s.replace(marker, extra + marker, 1)
old = '''        with mock.patch.object(agentd, "publish_control_json", side_effect=fake_publish), mock.patch.object(\n            agentd, "restart_self", side_effect=RuntimeError("restart called")\n        ):\n'''
new = '''        with mock.patch.object(agentd, "control_ack_published", return_value=False), mock.patch.object(\n            agentd, "publish_control_json", side_effect=fake_publish\n        ), mock.patch.object(\n            agentd, "restart_self", side_effect=RuntimeError("restart called")\n        ):\n'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# Parallel probe tests now model remote ACK state rather than local file presence.
p = ROOT / 'tests/test_parallel_control.py'
s = p.read_text(encoding='utf-8')
old = '''        self.assertTrue(parallel.pending_control_request_from_bound_checkout())\n\n    def test_acknowledged_request_does_not_trigger_repeat_drain(self) -> None:\n'''
new = '''        with mock.patch.object(agentd, "control_ack_published", return_value=False):\n            self.assertTrue(parallel.pending_control_request_from_bound_checkout())\n\n    def test_acknowledged_request_does_not_trigger_repeat_drain(self) -> None:\n'''
assert old in s
s = s.replace(old, new, 1)
old = '''        ack.write_text("{}\\n", encoding="utf-8")\n        self.assertFalse(parallel.pending_control_request_from_bound_checkout())\n'''
new = '''        ack.write_text("{}\\n", encoding="utf-8")\n        with mock.patch.object(agentd, "control_ack_published", return_value=True):\n            self.assertFalse(parallel.pending_control_request_from_bound_checkout())\n'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# Repository status control test needs explicit remote ACK state. Global controls return earlier.
p = ROOT / 'tests/test_agent_repo_control.py'
s = p.read_text(encoding='utf-8')
old = '''        with mock.patch.object(worker, "publish_repository_status") as publish_status, mock.patch.object(\n            worker, "publish_repository_control_ack"\n        ) as publish_ack:\n'''
new = '''        with mock.patch.object(agentd, "control_ack_published", return_value=False), mock.patch.object(\n            worker, "publish_repository_status"\n        ) as publish_status, mock.patch.object(\n            worker, "publish_repository_control_ack"\n        ) as publish_ack:\n'''
assert old in s
s = s.replace(old, new, 1)
marker = '    def test_restart_is_left_for_supervisor_without_ack(self) -> None:\n'
extra = '''    def test_status_control_ignores_local_only_ack(self) -> None:\n        worker.bind_repository(self.repository)\n        self.write_control({"id": "status-local", "action": "status"})\n        ack = self.repository.control / agentd.REMOTE_CONTROL_ACK_DIR / "status-local.json"\n        ack.parent.mkdir(parents=True, exist_ok=True)\n        ack.write_text("{}\\n", encoding="utf-8")\n        with mock.patch.object(agentd, "control_ack_published", return_value=False), mock.patch.object(\n            worker, "publish_repository_status"\n        ) as publish_status, mock.patch.object(\n            worker, "publish_repository_control_ack"\n        ) as publish_ack:\n            worker.handle_repository_control(self.repository)\n        publish_status.assert_called_once()\n        publish_ack.assert_called_once()\n\n'''
assert marker in s
s = s.replace(marker, extra + marker, 1)
p.write_text(s, encoding='utf-8')

notes = ROOT / 'docs/RELEASE_NOTES_V4.11.1.md'
s = notes.read_text(encoding='utf-8')
needle = '- does not change task/resource arbitration, concurrency, leases, or the serial fallback.\n'
replacement = (
    '- treats a control ACK as durable only when it is visible on the fetched remote `agent-control` branch, so a crash after local ACK commit but before push does not suppress the request;\n'
    '- expands local self-update validation to explicitly compile the parallel production entrypoints and gives the full local test gate a 600 second bounded margin;\n'
    '- does not change task/resource arbitration, concurrency, leases, or the serial fallback.\n'
)
assert needle in s
s = s.replace(needle, replacement, 1)
notes.write_text(s, encoding='utf-8')
