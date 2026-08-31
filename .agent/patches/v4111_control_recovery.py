from pathlib import Path

ROOT = Path('/Users/michal/local-agent-v4.11.1-logging-staging')

storage = ROOT / 'agent_storage.py'
s = storage.read_text(encoding='utf-8')
needle = 'CONTROL_SPARSE_PATHS = (".agent",)\n'
insert = '''CONTROL_SPARSE_PATHS = (".agent",)
CONTROL_RECOVERABLE_DIRS = (
    ".agent/status",
    ".agent/runs",
    ".agent/results",
    ".agent/daemon/acks",
)
'''
assert needle in s
s = s.replace(needle, insert, 1)
needle = '''def sync_control(core_module: Any) -> None:
    """Synchronize the active control checkout while preserving its shallow boundary."""
    with core_module.CONTROL_GIT_LOCK:
        branch = core_module.process(
'''
insert = '''def _control_dirty_paths(core_module: Any) -> tuple[str, ...]:
    status = core_module.process(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        core_module.CONTROL,
        timeout=30,
        log_commands=False,
    )
    if status["exit_code"] != 0:
        raise RuntimeError(status["output"])
    paths: set[str] = set()
    for line in str(status.get("output", "")).splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            before, after = path.split(" -> ", 1)
            paths.add(before.strip('"'))
            paths.add(after.strip('"'))
        elif path:
            paths.add(path.strip('"'))
    return tuple(sorted(paths))


def _recoverable_control_path(path: str) -> bool:
    return any(
        path == directory or path.startswith(directory + "/")
        for directory in CONTROL_RECOVERABLE_DIRS
    )


def recover_daemon_owned_control_changes(core_module: Any) -> None:
    """Discard only interrupted daemon-owned control artifacts before sync."""
    dirty = _control_dirty_paths(core_module)
    if not dirty:
        return
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

    restore = core_module.process(
        [
            "git",
            "restore",
            "--source=HEAD",
            "--staged",
            "--worktree",
            "--",
            *CONTROL_RECOVERABLE_DIRS,
        ],
        core_module.CONTROL,
        timeout=30,
        log_commands=False,
    )
    if restore["exit_code"] != 0:
        raise RuntimeError(restore["output"])
    clean = core_module.process(
        ["git", "clean", "-fd", "--", *CONTROL_RECOVERABLE_DIRS],
        core_module.CONTROL,
        timeout=30,
        log_commands=False,
    )
    if clean["exit_code"] != 0:
        raise RuntimeError(clean["output"])


def sync_control(core_module: Any) -> None:
    """Synchronize the active control checkout while preserving its shallow boundary."""
    with core_module.CONTROL_GIT_LOCK:
        recover_daemon_owned_control_changes(core_module)
        branch = core_module.process(
'''
assert needle in s
s = s.replace(needle, insert, 1)
storage.write_text(s, encoding='utf-8')

tests = ROOT / 'tests/test_agent_storage.py'
s = tests.read_text(encoding='utf-8')
old = '''        process = mock.Mock(side_effect=[
            {"exit_code": 0, "output": "agent-control"},
            {"exit_code": 0, "output": "Already up to date."},
        ])'''
new = '''        process = mock.Mock(side_effect=[
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": "agent-control"},
            {"exit_code": 0, "output": "Already up to date."},
        ])'''
assert old in s
s = s.replace(old, new, 1)
old = '''        self.assertEqual(process.call_count, 2)
        self.assertEqual(process.call_args_list[0].args[0], ["git", "symbolic-ref", "--quiet", "--short", "HEAD"])
        self.assertEqual(process.call_args_list[1].args[0], ["git", *storage.bounded_control_pull_args("agent-control")])'''
new = '''        self.assertEqual(process.call_count, 3)
        self.assertEqual(process.call_args_list[0].args[0], ["git", "status", "--porcelain=v1", "--untracked-files=all"])
        self.assertEqual(process.call_args_list[1].args[0], ["git", "symbolic-ref", "--quiet", "--short", "HEAD"])
        self.assertEqual(process.call_args_list[2].args[0], ["git", *storage.bounded_control_pull_args("agent-control")])'''
assert old in s
s = s.replace(old, new, 1)
old = '''        process = mock.Mock(side_effect=[
            {"exit_code": 0, "output": "main"},
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": "Already up to date."},
        ])'''
new = '''        process = mock.Mock(side_effect=[
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": "main"},
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": "Already up to date."},
        ])'''
assert old in s
s = s.replace(old, new, 1)
old = '''        self.assertEqual(process.call_count, 3)
        self.assertEqual(process.call_args_list[1].args, (["git", "checkout", "agent-control"], Path("/tmp/control")))
        self.assertEqual(process.call_args_list[2].args[0], ["git", *storage.bounded_control_pull_args("agent-control")])'''
new = '''        self.assertEqual(process.call_count, 4)
        self.assertEqual(process.call_args_list[2].args, (["git", "checkout", "agent-control"], Path("/tmp/control")))
        self.assertEqual(process.call_args_list[3].args[0], ["git", *storage.bounded_control_pull_args("agent-control")])'''
assert old in s
s = s.replace(old, new, 1)
marker = '    def test_transient_ssh_failure_is_retried_and_recovers(self) -> None:\n'
assert marker in s
extra = '''    def test_sync_control_recovers_only_daemon_owned_dirty_paths(self) -> None:
        process = mock.Mock(side_effect=[
            {"exit_code": 0, "output": " M .agent/status/daemon.json\\n?? .agent/runs/task.json\\n"},
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
        self.assertEqual(process.call_args_list[1].args[0][:4], ["git", "restore", "--source=HEAD", "--staged"])
        self.assertEqual(process.call_args_list[2].args[0][:3], ["git", "clean", "-fd"])
        self.assertIn("daemon-owned control changes", core.log.call_args.args[0])

    def test_sync_control_rejects_unexpected_dirty_paths(self) -> None:
        process = mock.Mock(return_value={
            "exit_code": 0,
            "output": " M .agent/tasks/task.json\\n",
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

'''
s = s.replace(marker, extra + marker, 1)
tests.write_text(s, encoding='utf-8')

notes = ROOT / 'docs/RELEASE_NOTES_V4.11.1.md'
s = notes.read_text(encoding='utf-8')
needle = '- does not change task/resource arbitration, concurrency, leases, control semantics, or the serial fallback.\n'
replacement = '''- recovers interrupted daemon-owned control status/run/result/ack files before a control-branch pull, preventing a SIGKILL between write/stage/commit from wedging later recovery;
- refuses to auto-clean unexpected control changes such as tasks or daemon control requests;
- does not change task/resource arbitration, concurrency, leases, or the serial fallback.
'''
assert needle in s
notes.write_text(s.replace(needle, replacement, 1), encoding='utf-8')
