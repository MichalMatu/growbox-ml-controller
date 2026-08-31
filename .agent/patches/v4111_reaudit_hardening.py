from __future__ import annotations

from pathlib import Path

ROOT = Path('/Users/michal/local-agent-v4.11.1-logging-staging')


def replace_between(path: Path, start_marker: str, end_marker: str, replacement: str) -> None:
    text = path.read_text(encoding='utf-8')
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    path.write_text(text[:start] + replacement + text[end:], encoding='utf-8')


storage_block = r'''def _control_status_entries(core_module: Any) -> tuple[tuple[str, str], ...]:
    """Return exact porcelain status entries without Git path quoting."""
    status = core_module.process(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        core_module.CONTROL,
        timeout=30,
        log_commands=False,
    )
    if status["exit_code"] != 0:
        raise RuntimeError(git_failure_diagnostic(status))

    fields = str(status.get("output", "")).split("\0")
    entries: list[tuple[str, str]] = []
    index = 0
    while index < len(fields):
        record = fields[index]
        if not record:
            index += 1
            continue
        if len(record) < 4 or record[2] != " ":
            raise RuntimeError(f"invalid git status porcelain record: {record!r}")
        code = record[:2]
        path = record[3:]
        if not path:
            raise RuntimeError("invalid git status porcelain path")
        entries.append((code, path))

        if "R" in code or "C" in code:
            index += 1
            if index >= len(fields) or not fields[index]:
                raise RuntimeError("incomplete git status rename/copy record")
            entries.append((code, fields[index]))
        index += 1
    return tuple(entries)


def _control_dirty_paths(core_module: Any) -> tuple[str, ...]:
    return tuple(sorted({path for _code, path in _control_status_entries(core_module)}))


def _recoverable_control_path(path: str) -> bool:
    return any(
        path == directory or path.startswith(directory + "/")
        for directory in CONTROL_RECOVERABLE_DIRS
    )


def recover_daemon_owned_control_changes(core_module: Any) -> None:
    """Discard only interrupted daemon-owned control artifacts before sync."""
    entries = _control_status_entries(core_module)
    if not entries:
        return

    dirty = tuple(sorted({path for _code, path in entries}))
    unexpected = tuple(path for path in dirty if not _recoverable_control_path(path))
    if unexpected:
        raise RuntimeError(
            "control checkout has unexpected local changes: "
            + ", ".join(unexpected)
        )

    logger = getattr(core_module, "log", None)
    if callable(logger):
        logger(
            "recovering interrupted daemon-owned control changes before sync: "
            + ", ".join(dirty)
        )

    tracked = tuple(sorted({path for code, path in entries if code != "??"}))
    untracked = tuple(sorted({path for code, path in entries if code == "??"}))

    if tracked:
        restore = core_module.process(
            [
                "git",
                "restore",
                "--source=HEAD",
                "--staged",
                "--worktree",
                "--",
                *tracked,
            ],
            core_module.CONTROL,
            timeout=30,
            log_commands=False,
        )
        if restore["exit_code"] != 0:
            raise RuntimeError(git_failure_diagnostic(restore))

    if untracked:
        clean = core_module.process(
            ["git", "clean", "-fd", "--", *untracked],
            core_module.CONTROL,
            timeout=30,
            log_commands=False,
        )
        if clean["exit_code"] != 0:
            raise RuntimeError(git_failure_diagnostic(clean))

    remaining = _control_dirty_paths(core_module)
    if remaining:
        raise RuntimeError(
            "control checkout remained dirty after daemon-owned recovery: "
            + ", ".join(remaining)
        )


'''
replace_between(
    ROOT / 'agent_storage.py',
    'def _control_dirty_paths(core_module: Any)',
    'def sync_control(core_module: Any)',
    storage_block,
)

agentd_publish = r'''def publish_control_json(
    relative: str,
    payload: dict[str, Any],
    *,
    commit_message: str,
    timeout: int = 180,
    attempts: int = 2,
    log_commands: bool = False,
) -> bool:
    """Publish control metadata while keeping successful Git plumbing quiet."""
    with core.CONTROL_GIT_LOCK:
        target = (core.CONTROL / relative).resolve()
        root = core.CONTROL.resolve()
        if root not in target.parents:
            raise ValueError(f"control path escapes repository: {relative!r}")

        with termination_critical_section():
            atomic_write_json(target, payload)
            add = core.process(
                ["git", "add", "--", relative],
                core.CONTROL,
                log_commands=log_commands,
            )
            if add["exit_code"] != 0:
                raise RuntimeError(storage.git_failure_diagnostic(add))

            staged = core.process(
                ["git", "diff", "--cached", "--quiet", "--", relative],
                core.CONTROL,
                log_commands=log_commands,
            )
            if staged["exit_code"] == 0:
                return False
            if staged["exit_code"] != 1:
                raise RuntimeError(storage.git_failure_diagnostic(staged))

            commit = core.process(
                ["git", "commit", "-m", commit_message, "--", relative],
                core.CONTROL,
                log_commands=log_commands,
            )
            if commit["exit_code"] != 0:
                raise RuntimeError(storage.git_failure_diagnostic(commit))

        for attempt in range(attempts):
            pull = storage.run_git_with_network_retry(
                core,
                ["git", *storage.bounded_control_pull_args(core.CONTROL_BRANCH)],
                core.CONTROL,
                timeout=timeout,
                log_commands=log_commands,
            )
            if pull["exit_code"] != 0:
                raise RuntimeError(pull["output"])
            push = storage.run_git_with_network_retry(
                core,
                ["git", "push", "origin", core.CONTROL_BRANCH],
                core.CONTROL,
                timeout=timeout,
                log_commands=log_commands,
            )
            if push["exit_code"] == 0:
                return True
            if attempt == attempts - 1:
                raise RuntimeError(push["output"])
    return False


'''
replace_between(
    ROOT / 'agentd.py',
    'def publish_control_json(',
    'def load_task_file(',
    agentd_publish,
)

core_publish = r'''def publish_result(task_id: str, result: dict[str, Any]) -> None:
    """Publish a durable result with quiet successful control-plane Git plumbing."""
    with CONTROL_GIT_LOCK:
        root = CONTROL.resolve()
        results_dir = (CONTROL / ".agent" / "results").resolve()
        if root not in results_dir.parents:
            raise ValueError("result directory escapes control repository")
        results_dir.mkdir(parents=True, exist_ok=True)
        path = results_dir / f"{task_id}.json"
        atomic_write_text(
            path,
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        )

        relative = str(path.relative_to(root))
        add = process(
            ["git", "add", "--", relative],
            CONTROL,
            log_commands=False,
        )
        if add["exit_code"] != 0:
            raise RuntimeError(storage.git_failure_diagnostic(add))

        commit = process(
            ["git", "commit", "-m", f"Agent result: {task_id}", "--", relative],
            CONTROL,
            log_commands=False,
        )
        if commit["exit_code"] != 0:
            status = process(
                ["git", "status", "--short", "--", relative],
                CONTROL,
                log_commands=False,
            )
            if status["exit_code"] != 0 or status["output"].strip():
                raise RuntimeError(storage.git_failure_diagnostic(commit))

        pull = storage.run_git_with_network_retry(
            sys.modules[__name__],
            ["git", *storage.bounded_control_pull_args(CONTROL_BRANCH)],
            CONTROL,
            timeout=180,
            log_commands=False,
        )
        if pull["exit_code"] != 0:
            raise RuntimeError(pull["output"])

        push = storage.run_git_with_network_retry(
            sys.modules[__name__],
            ["git", "push", "origin", CONTROL_BRANCH],
            CONTROL,
            timeout=180,
            log_commands=False,
        )
        if push["exit_code"] != 0:
            raise RuntimeError(push["output"])

    log(f"published result {task_id}")
'''
core_path = ROOT / 'agent_core.py'
core_text = core_path.read_text(encoding='utf-8')
core_start = core_text.index('def publish_result(')
core_path.write_text(core_text[:core_start] + core_publish, encoding='utf-8')

# Update storage unit coverage for NUL-delimited porcelain and exact tracked/untracked cleanup.
test_storage = ROOT / 'tests/test_agent_storage.py'
s = test_storage.read_text(encoding='utf-8')
s = s.replace('import unittest\n', 'import subprocess\nimport tempfile\nimport unittest\n', 1)
s = s.replace(
    '["git", "status", "--porcelain=v1", "--untracked-files=all"]',
    '["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]',
)
start = s.index('    def test_sync_control_recovers_only_daemon_owned_dirty_paths')
end = s.index('    def test_transient_ssh_failure_is_retried_and_recovers', start)
replacement = r'''    def test_sync_control_recovers_only_daemon_owned_dirty_paths(self) -> None:
        process = mock.Mock(side_effect=[
            {"exit_code": 0, "output": " M .agent/status/daemon.json\0?? .agent/runs/task.json\0"},
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": "agent-control"},
            {"exit_code": 0, "output": "Already up to date."},
        ])
        core = SimpleNamespace(
            CONTROL=Path("/tmp/control"),
            CONTROL_BRANCH="agent-control",
            CONTROL_GIT_LOCK=nullcontext(),
            process=process,
            log=mock.Mock(),
        )
        storage.sync_control(core)
        self.assertEqual(
            process.call_args_list[1].args[0],
            [
                "git",
                "restore",
                "--source=HEAD",
                "--staged",
                "--worktree",
                "--",
                ".agent/status/daemon.json",
            ],
        )
        self.assertEqual(
            process.call_args_list[2].args[0],
            ["git", "clean", "-fd", "--", ".agent/runs/task.json"],
        )
        self.assertIn("daemon-owned control changes", core.log.call_args.args[0])

    def test_sync_control_recovers_untracked_only_without_restore(self) -> None:
        process = mock.Mock(side_effect=[
            {"exit_code": 0, "output": "?? .agent/results/new result.json\0"},
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": "agent-control"},
            {"exit_code": 0, "output": "Already up to date."},
        ])
        core = SimpleNamespace(
            CONTROL=Path("/tmp/control"),
            CONTROL_BRANCH="agent-control",
            CONTROL_GIT_LOCK=nullcontext(),
            process=process,
            log=mock.Mock(),
        )
        storage.sync_control(core)
        self.assertEqual(
            process.call_args_list[1].args[0],
            ["git", "clean", "-fd", "--", ".agent/results/new result.json"],
        )
        self.assertFalse(
            any(call.args[0][1] == "restore" for call in process.call_args_list)
        )

    def test_sync_control_rejects_unexpected_dirty_paths(self) -> None:
        process = mock.Mock(return_value={
            "exit_code": 0,
            "output": " M .agent/tasks/task.json\0",
        })
        core = SimpleNamespace(
            CONTROL=Path("/tmp/control"),
            CONTROL_BRANCH="agent-control",
            CONTROL_GIT_LOCK=nullcontext(),
            process=process,
            log=mock.Mock(),
        )
        with self.assertRaisesRegex(RuntimeError, "unexpected local changes"):
            storage.sync_control(core)
        process.assert_called_once()

    def test_control_recovery_handles_real_mixed_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "storage-test"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "storage@example.invalid"], cwd=repo, check=True)
            tracked = repo / ".agent" / "status" / "daemon.json"
            tracked.parent.mkdir(parents=True)
            tracked.write_text("old\n", encoding="utf-8")
            subprocess.run(["git", "add", ".agent/status/daemon.json"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
            tracked.write_text("new\n", encoding="utf-8")
            untracked = repo / ".agent" / "results" / "new result.json"
            untracked.parent.mkdir(parents=True)
            untracked.write_text("{}\n", encoding="utf-8")

            def process(args, cwd, **_kwargs):
                completed = subprocess.run(
                    args,
                    cwd=cwd,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                return {"exit_code": completed.returncode, "output": completed.stdout}

            core = SimpleNamespace(CONTROL=repo, process=process, log=mock.Mock())
            storage.recover_daemon_owned_control_changes(core)
            self.assertEqual(tracked.read_text(encoding="utf-8"), "old\n")
            self.assertFalse(untracked.exists())
            status = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            )
            self.assertEqual(status.stdout, "")

    def test_control_recovery_refuses_real_task_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            task = repo / ".agent" / "tasks" / "task.json"
            task.parent.mkdir(parents=True)
            task.write_text("{}\n", encoding="utf-8")

            def process(args, cwd, **_kwargs):
                completed = subprocess.run(
                    args,
                    cwd=cwd,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                return {"exit_code": completed.returncode, "output": completed.stdout}

            core = SimpleNamespace(CONTROL=repo, process=process, log=mock.Mock())
            with self.assertRaisesRegex(RuntimeError, "unexpected local changes"):
                storage.recover_daemon_owned_control_changes(core)
            self.assertTrue(task.exists())

'''
s = s[:start] + replacement + s[end:]
test_storage.write_text(s, encoding='utf-8')

# Verify successful metadata publication is quiet while failures remain diagnosable.
test_agentd = ROOT / 'tests/test_agentd.py'
s = test_agentd.read_text(encoding='utf-8')
s = s.replace('import threading\n', 'import threading\nfrom contextlib import nullcontext\n', 1)
marker = '    def test_daemon_status_reports_hardened_watchdog_defaults(self) -> None:\n'
extra = r'''    def test_publish_control_json_keeps_successful_git_plumbing_quiet(self) -> None:
        process = mock.Mock(side_effect=[
            {"exit_code": 0, "output": ""},
            {"exit_code": 1, "output": ""},
            {"exit_code": 0, "output": ""},
        ])
        retry = mock.Mock(side_effect=[
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": ""},
        ])
        with mock.patch.object(agentd.core, "process", process), mock.patch.object(
            agentd.storage,
            "run_git_with_network_retry",
            retry,
        ), mock.patch.object(
            agentd,
            "termination_critical_section",
            return_value=nullcontext(),
        ):
            published = agentd.publish_control_json(
                ".agent/status/daemon.json",
                {"state": "idle"},
                commit_message="Agent daemon status: idle",
            )
        self.assertTrue(published)
        self.assertTrue(process.call_args_list)
        self.assertTrue(
            all(call.kwargs.get("log_commands") is False for call in process.call_args_list)
        )
        self.assertEqual(retry.call_count, 2)
        self.assertTrue(
            all(call.kwargs.get("log_commands") is False for call in retry.call_args_list)
        )

    def test_quiet_control_git_failure_keeps_diagnostic(self) -> None:
        failure = {
            "exit_code": 124,
            "output": "",
            "timed_out": True,
            "elapsed_seconds": 30.0,
        }
        with mock.patch.object(agentd.core, "process", return_value=failure), mock.patch.object(
            agentd,
            "termination_critical_section",
            return_value=nullcontext(),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed_out=true"):
                agentd.publish_control_json(
                    ".agent/status/daemon.json",
                    {"state": "idle"},
                    commit_message="Agent daemon status: idle",
                )

'''
assert marker in s
s = s.replace(marker, extra + marker, 1)
test_agentd.write_text(s, encoding='utf-8')

# Strengthen existing result publication test with quiet-plumbing assertions.
test_core = ROOT / 'tests/test_agent_core.py'
s = test_core.read_text(encoding='utf-8')
needle = '            self.assertEqual(len(commit_calls), 1)\n            self.assertEqual(commit_calls[0].args[0][-2:], ["--", ".agent/results/result-test.json"])\n'
replacement = needle + '            self.assertTrue(all(c.kwargs.get("log_commands") is False for c in process.call_args_list))\n            self.assertTrue(all(c.kwargs.get("log_commands") is False for c in retry.call_args_list))\n'
assert needle in s
s = s.replace(needle, replacement, 1)
test_core.write_text(s, encoding='utf-8')

notes = ROOT / 'docs/RELEASE_NOTES_V4.11.1.md'
s = notes.read_text(encoding='utf-8')
needle = '- keeps low-level Git/process diagnostics unchanged for troubleshooting;\n'
replacement = (
    '- keeps successful control-plane Git publication quiet so operator logs stay focused on `IDLE`, task and failure events;\n'
    '- preserves non-empty Git diagnostics and transient-network retry messages when those quiet operations fail;\n'
    '- handles tracked, staged-new and purely untracked interrupted daemon-owned control metadata with exact-path recovery;\n'
)
assert needle in s
s = s.replace(needle, replacement, 1)
notes.write_text(s, encoding='utf-8')
