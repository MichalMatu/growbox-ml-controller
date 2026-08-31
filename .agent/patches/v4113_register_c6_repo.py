from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOME = Path.home()
LOCAL_AGENT = HOME / "local-agent"
REGISTRY = HOME / "Library" / "Application Support" / "local-agent" / "repositories.json"
REPOSITORY_ID = "esp32-c6-zigbee"
REPOSITORY = "MichalMatu/esp32_c6_zigbee"
ENTRY = {
    "id": REPOSITORY_ID,
    "repository": REPOSITORY,
    "control_branch": "agent-control",
    "default_branch": "main",
}


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def run(*args: str) -> str:
    completed = subprocess.run(
        args,
        cwd=LOCAL_AGENT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=900,
        check=False,
    )
    print(f"$ {' '.join(args)}")
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.returncode != 0:
        raise RuntimeError(f"command failed with exit {completed.returncode}: {' '.join(args)}")
    return completed.stdout


original = REGISTRY.read_bytes()
try:
    payload = json.loads(original.decode("utf-8"))
    if payload.get("version") != 1 or not isinstance(payload.get("repositories"), list):
        raise RuntimeError("unexpected repository registry format")

    repositories = payload["repositories"]
    matching_ids = [item for item in repositories if item.get("id") == REPOSITORY_ID]
    matching_remotes = [item for item in repositories if item.get("repository", "").casefold() == REPOSITORY.casefold()]

    if matching_ids or matching_remotes:
        if len(matching_ids) != 1 or len(matching_remotes) != 1 or matching_ids[0] is not matching_remotes[0]:
            raise RuntimeError("conflicting existing ESP32-C6 registry identity")
        current = matching_ids[0]
        for key, value in ENTRY.items():
            if current.get(key, value) != value:
                raise RuntimeError(f"existing ESP32-C6 registry field mismatch: {key}")
        print("REGISTRY_ENTRY_ALREADY_PRESENT")
    else:
        repositories.append(ENTRY)
        encoded = (json.dumps(payload, indent=2, ensure_ascii=True) + "\n").encode("utf-8")
        atomic_write(REGISTRY, encoded)
        print("REGISTRY_ENTRY_ADDED")

    sys.path.insert(0, str(LOCAL_AGENT))
    from agent_repository import load_repository_registry

    loaded = load_repository_registry(path=REGISTRY)
    if len(loaded) != 4:
        raise RuntimeError(f"expected 4 enabled repositories, got {len(loaded)}")
    selected = [item for item in loaded if item.repository_id == REPOSITORY_ID]
    if len(selected) != 1 or selected[0].repository != REPOSITORY:
        raise RuntimeError("ESP32-C6 repository entry did not validate")

    python = str(LOCAL_AGENT / ".venv" / "bin" / "python")
    admin = str(LOCAL_AGENT / "agent_repo_admin.py")
    registry = str(REGISTRY)
    run(python, admin, "--registry", registry, "provision", "--repository-id", REPOSITORY_ID)
    run(python, admin, "--registry", registry, "validate", "--repository-id", REPOSITORY_ID)
    listing = run(python, admin, "--registry", registry, "list")
    lines = [line for line in listing.splitlines() if line.strip()]
    if len(lines) != 4 or not any(line.startswith(REPOSITORY_ID + "\t" + REPOSITORY + "\t") for line in lines):
        raise RuntimeError("final repository listing does not contain exactly four repositories")

    control = HOME / "agent-workspace" / "repos" / REPOSITORY_ID / "control"
    work = HOME / "agent-workspace" / "repos" / REPOSITORY_ID / "work"
    checkpoints = HOME / "agent-workspace" / "repos" / REPOSITORY_ID / "checkpoints"
    for path in (control, work, checkpoints):
        if not path.exists():
            raise RuntimeError(f"expected provisioned path missing: {path}")

    print("ESP32_C6_REPOSITORY_ONBOARDING_OK")
except Exception:
    atomic_write(REGISTRY, original)
    print("REGISTRY_ROLLED_BACK")
    raise
