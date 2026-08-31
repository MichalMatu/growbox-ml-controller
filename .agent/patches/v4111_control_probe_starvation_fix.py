from pathlib import Path

root = Path('/Users/michal/local-agent-v4.11.1-control-probe-staging')
parallel = root / 'agent_parallel.py'
tests = root / 'tests' / 'test_parallel_control.py'
notes = root / 'docs' / 'RELEASE_NOTES_V4.11.1.md'

text = parallel.read_text(encoding='utf-8')
text = text.replace(
    'from dataclasses import dataclass\n',
    'from dataclasses import dataclass\nfrom enum import Enum\n',
    1,
)
marker = 'PARALLEL_EXECUTION_MODEL = "parallel_repository_supervisor"\n_daemon_lock_handle: Any | None = None\n'
replacement = '''PARALLEL_EXECUTION_MODEL = "parallel_repository_supervisor"\n_daemon_lock_handle: Any | None = None\n\n\nclass ControlProbeResult(Enum):\n    CLEAR = "clear"\n    PENDING = "pending"\n    DEFERRED = "deferred"\n'''
if marker not in text:
    raise SystemExit('parallel constants marker not found')
text = text.replace(marker, replacement, 1)

old = '''def pending_control_request_from_bound_checkout() -> bool:\n    """Return True for a valid unacknowledged daemon control request."""\n    path = agentd.core.CONTROL / agentd.REMOTE_CONTROL_REQUEST\n    if not path.exists():\n        return False\n    try:\n        request = json.loads(path.read_text(encoding="utf-8"))\n        control_id = str(request["id"])\n        str(request["action"])\n    except Exception as exc:\n        log(f"invalid daemon control request during probe: {type(exc).__name__}: {exc}")\n        return False\n    if not control_id or len(control_id) > 120:\n        return False\n    try:\n        return not agentd.control_ack_published(control_id)\n    except Exception as exc:\n        log(f"control ACK probe degraded id={control_id}: {type(exc).__name__}: {exc}")\n        return False\n\n\ndef probe_control_request(\n    repository: RepositoryContext,\n) -> bool:\n    """Probe control while other repositories run without invoking global actions."""\n    try:\n        with serial_worker.repository_execution_lease(repository):\n            serial.bind_supervisor_control(repository)\n            serial.sync_control_quietly()\n            return pending_control_request_from_bound_checkout()\n    except ExecutionLeaseBusy:\n        return False\n    except Exception as exc:\n        log(\n            f"supervisor control probe degraded repository={repository.repository_id}: "\n            f"{type(exc).__name__}: {exc}"\n        )\n        return False\n'''
new = '''def pending_control_request_from_bound_checkout() -> ControlProbeResult:\n    """Classify a control request after a successful control-checkout sync."""\n    path = agentd.core.CONTROL / agentd.REMOTE_CONTROL_REQUEST\n    if not path.exists():\n        return ControlProbeResult.CLEAR\n    try:\n        request = json.loads(path.read_text(encoding="utf-8"))\n        control_id = str(request["id"])\n        str(request["action"])\n    except Exception as exc:\n        log(f"invalid daemon control request during probe: {type(exc).__name__}: {exc}")\n        return ControlProbeResult.CLEAR\n    if not control_id or len(control_id) > 120:\n        return ControlProbeResult.CLEAR\n    try:\n        published = agentd.control_ack_published(control_id)\n    except Exception as exc:\n        log(f"control ACK probe degraded id={control_id}: {type(exc).__name__}: {exc}")\n        return ControlProbeResult.DEFERRED\n    return ControlProbeResult.CLEAR if published else ControlProbeResult.PENDING\n\n\ndef probe_control_request(\n    repository: RepositoryContext,\n) -> ControlProbeResult:\n    """Probe control while other repositories run without invoking global actions."""\n    try:\n        with serial_worker.repository_execution_lease(repository):\n            serial.bind_supervisor_control(repository)\n            serial.sync_control_quietly()\n            return pending_control_request_from_bound_checkout()\n    except ExecutionLeaseBusy:\n        return ControlProbeResult.DEFERRED\n    except Exception as exc:\n        log(\n            f"supervisor control probe degraded repository={repository.repository_id}: "\n            f"{type(exc).__name__}: {exc}"\n        )\n        return ControlProbeResult.DEFERRED\n'''
if old not in text:
    raise SystemExit('parallel probe block not found')
text = text.replace(old, new, 1)

old_loop = '''                if running:\n                    if probe_control_request(repositories[0]):\n                        control_pending = True\n                        log("global control request detected; draining active workers")\n                        time.sleep(REAP_INTERVAL_SECONDS)\n                        continue\n                    last_control_at = time.monotonic()\n                else:\n'''
new_loop = '''                if running:\n                    probe_result = probe_control_request(repositories[0])\n                    if probe_result is ControlProbeResult.PENDING:\n                        control_pending = True\n                        log("global control request detected; draining active workers")\n                        time.sleep(REAP_INTERVAL_SECONDS)\n                        continue\n                    if probe_result is ControlProbeResult.DEFERRED:\n                        time.sleep(ERROR_RETRY_SECONDS)\n                        continue\n                    last_control_at = time.monotonic()\n                else:\n'''
if old_loop not in text:
    raise SystemExit('parallel main-loop probe block not found')
text = text.replace(old_loop, new_loop, 1)
parallel.write_text(text, encoding='utf-8')

text = tests.read_text(encoding='utf-8')
text = text.replace(
    'self.assertFalse(parallel.pending_control_request_from_bound_checkout())',
    'self.assertIs(\n            parallel.pending_control_request_from_bound_checkout(),\n            parallel.ControlProbeResult.CLEAR,\n        )',
    1,
)
text = text.replace(
    'self.assertTrue(parallel.pending_control_request_from_bound_checkout())',
    'self.assertIs(\n                parallel.pending_control_request_from_bound_checkout(),\n                parallel.ControlProbeResult.PENDING,\n            )',
    1,
)
text = text.replace(
    'self.assertFalse(parallel.pending_control_request_from_bound_checkout())',
    'self.assertIs(\n                parallel.pending_control_request_from_bound_checkout(),\n                parallel.ControlProbeResult.CLEAR,\n            )',
    1,
)
text = text.replace(
    'self.assertFalse(parallel.pending_control_request_from_bound_checkout())',
    'self.assertIs(\n                parallel.pending_control_request_from_bound_checkout(),\n                parallel.ControlProbeResult.CLEAR,\n            )',
    1,
)
text = text.replace(
    '            return_value=True,\n        ):\n            self.assertTrue(parallel.probe_control_request(repo))',
    '            return_value=parallel.ControlProbeResult.PENDING,\n        ):\n            self.assertIs(\n                parallel.probe_control_request(repo),\n                parallel.ControlProbeResult.PENDING,\n            )',
    1,
)
text = text.replace(
    '            self.assertFalse(parallel.probe_control_request(repo))\n',
    '            self.assertIs(\n                parallel.probe_control_request(repo),\n                parallel.ControlProbeResult.DEFERRED,\n            )\n',
    1,
)
insert_after = '''        self.assertIn("invalid daemon control request", log.call_args.args[0])\n\n'''
addition = '''        self.assertIn("invalid daemon control request", log.call_args.args[0])\n\n    def test_ack_probe_failure_is_deferred_for_prompt_retry(self) -> None:\n        path = self.request_path()\n        path.parent.mkdir(parents=True, exist_ok=True)\n        path.write_text(\n            json.dumps({"id": "status-retry", "action": "status"}),\n            encoding="utf-8",\n        )\n        with mock.patch.object(\n            agentd, "control_ack_published", side_effect=RuntimeError("network down")\n        ), mock.patch.object(parallel, "log"):\n            self.assertIs(\n                parallel.pending_control_request_from_bound_checkout(),\n                parallel.ControlProbeResult.DEFERRED,\n            )\n\n'''
if insert_after not in text:
    raise SystemExit('test insertion marker not found')
text = text.replace(insert_after, addition, 1)
tests.write_text(text, encoding='utf-8')

text = notes.read_text(encoding='utf-8')
needle = '- treats a control ACK as durable only when it is visible on the fetched remote `agent-control` branch, so a crash after local ACK commit but before push does not suppress the request;\n'
addition = needle + '- retries a deferred control probe promptly without advancing the control-poll clock, preventing a busy control-repository lease or transient probe failure from starving global restart/self-update/status requests;\n'
if needle not in text:
    raise SystemExit('release notes marker not found')
text = text.replace(needle, addition, 1)
notes.write_text(text, encoding='utf-8')
