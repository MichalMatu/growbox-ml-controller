# Agent notes — Growbox ML

## Local Agent — repository workflow

This repository is registered in the shared `MichalMatu/local-agent` multi-repository supervisor.

Canonical Local Agent source of truth:

- repository: `MichalMatu/local-agent`
- production/runtime branch: `main`
- releases: `vX.Y.Z` tags matching `local_agent/version.py`
- read repository-worker truth from `.agent/status/daemon.json`: `daemon_version`, `self_revision`, `execution_model` / `execution_variant`, current task state, and `supervisor_pid`; supervisor-wide fields such as `max_parallel_workers` are published by the shared supervisor and are not guaranteed to be repeated in every repository-worker status snapshot; do not pin a remembered daemon version here.

Repository identity:

- repository: `MichalMatu/growbox-ml-controller`
- local-agent repository id: `growbox-ml-controller`
- agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
- control branch: `agent-control`
- default source branch: `main`
- current MVP work branch: `mvp/environment-controller`
- execution model: one shared bounded-parallel supervisor with short-lived repository workers; one task per repository at a time, with cross-repository overlap only when resource admission permits it; `agent_multirepo.py` remains the serial fallback and enforces the same binding contract

### New chat bootstrap

When starting work on this repository in a new chat/session:

1. Read this `AGENTS.md`, the current `README.md`, `docs/CONTINUATION_PLAN.md`, and `docs/STAGE27_NATIVE_IDF_HANDOFF.md` before proposing or executing changes.
2. Inspect the exact GitHub branch relevant to the requested work. Do not assume `main` is the work branch.
3. If Chat Bridge is active, require the wake envelope to identify exactly repository id `growbox-ml-controller`, repository `MichalMatu/growbox-ml-controller`, and agent binding `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`. Never infer or switch repository identity from remembered chat context; a different repository requires explicit Bridge Rebind.
4. Inspect `.agent/status/daemon.json` on `agent-control` and verify `daemon_version` against `MichalMatu/local-agent/local_agent/version.py` when Local Agent compatibility matters.
5. When exact daemon source identity matters, compare `.agent/status/daemon.json:self_revision` with `MichalMatu/local-agent/main`; do not infer synchronization from the version string alone.
6. Use this repository's own `agent-control` branch for Local Agent tasks. Never send Growbox tasks through another repository's control branch.
7. Verify `.agent/binding.json` on `agent-control` matches the repository identity above before queueing work when binding compatibility matters.
8. For local execution, submit immutable task requests under `.agent/tasks/<task-id>.json` on `agent-control`, include exactly `"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`, declare `resources`, and set `work_branch` explicitly whenever the task must run on a non-default branch such as `mvp/environment-controller`.
9. Follow execution through `.agent/runs/<task-id>.json` and `.agent/status/daemon.json`.
10. Read the terminal result from `.agent/results/<task-id>.json` before reporting completion.
11. Prefer remote run/status/result evidence over asking the user to copy local terminal logs when Local Agent can provide the state directly.
12. Keep repository workspaces isolated. A Growbox task must not publish results through another repository's Local Agent control plane.
13. Do not reopen completed Stage25/26 work. Current hardware direction and the Stage27 bootstrap are frozen in `docs/STAGE27_NATIVE_IDF_HANDOFF.md`.

### Local Agent execution rules

- Local Agent is a deterministic executor, not a coding model. The planner chooses the exact bounded work; the daemon executes declared local commands/changes and reports evidence.
- Hard binding is fail-closed: local registry `agent_binding == .agent/binding.json agent_binding == task.agent_binding` is required before claim/execution on both parallel and serial fallback paths. Missing repository binding reports `unbound`; a control mismatch reports `binding_error`; missing/wrong task binding is terminally rejected before any task command runs.
- Never change, guess, or borrow another repository's binding to make a task run. Chat Bridge repository changes require explicit operator Rebind.
- The planner may also make bounded source changes directly through GitHub on the work branch when that is more efficient, then use Local Agent for real local synchronization/build/test verification. See the hybrid workflow below.
- Machine-generated task content, commands, prompts, logs, code comments, documentation changes and commit messages authored for Local Agent execution must be English-only.
- Task ids and payloads are immutable within this repository. Interrupted tasks are never automatically replayed.
- `expected_head` is not implemented. If exact source identity matters, verify the expected Git SHA explicitly in an early task stage.
- Repository workers execute at most one pending task per turn. Different repositories may run concurrently only when their declared external resources permit it; every task must declare `resources` explicitly and invalid declarations are terminal task-contract errors.
- Repository-local workers must not perform supervisor-wide `restart` or `self_update` actions. Those are owned by the shared supervisor/launchd administration path.
- A repository worker may report current daemon version/revision through `.agent/status/daemon.json`; use that evidence before attempting any maintenance action.
- Use bounded task timeouts/memory. The canonical defaults are command 900 s, no-output 300 s, whole-task 1800 s and process-group RSS 4096 MiB unless the task has a justified override.
- Every task must declare `resources` explicitly; missing, malformed, duplicated, oversized, or non-canonical declarations are terminal task-contract errors with no compatibility fallback.
- Use `resources: []` for repository-local software work, including builds/tests, when no exclusive external device or host-global state is used. `memory_limit_mb` is an independent RSS watchdog and does not determine resource classification.
- Use stable named resources such as `board:growbox-s3` for USB, serial, flashing, monitor, and hardware work so only tasks sharing that concrete resource serialize.
- Use `resources: ["machine"]` only for genuine whole-host operations such as global Local Agent maintenance or host-global toolchain mutation. Resource contention is a wait state and must continue with `NEXT`, not `STOP`.
- Successful stages must not leave background descendants.
- Final results are durably spooled before remote publication; publication recovery must not re-execute commands.

### Efficient verification workflow

For non-trivial staged coding work, prefer:

```json
"workflow_policy": "efficient-verification-v1"
```

Rules:

- primary `steps` use `verification_level: "work"` or `"focused"`;
- `verify_steps` use `"focused"` and exactly one final `"full"` stage;
- the full stage must be the last verification stage;
- do not mix legacy `commands` / `verify_commands` fields into an opted-in task;
- if the full gate finds a defect and source changes, rerun the affected focused gate first, then rerun the final full gate.

Use the narrowest meaningful verification while editing, then one broad final gate. Do not repeatedly run the complete suite after every small edit.

### Direct GitHub work and local execution

Use an available GitHub tool with write permission for bounded source/configuration/documentation changes when the exact diff and relevant CI can verify the outcome. A commit proves publication, not successful execution. Report the exact commit and completed checks. Do not create an artificial Local Agent task when GitHub evidence already provides the required verification.

Use Local Agent for Mac command execution, local builds/tests, device access and machine-specific evidence. A hybrid flow may edit through GitHub and run a read-only local verification task for the exact committed SHA; verify that SHA explicitly in an early stage (`expected_head` is not a supported task field). Check current daemon/run evidence before a direct write and avoid racing a local task that is modifying the same branch. Follow this repository's branch policy.

Local tasks retain their unique immutable ids, exact `agent_binding`, explicit `resources`, bounded limits and terminal result requirement. When Chat Bridge is active, both paths remain confined to its immutable repository binding. Use `STOP` only after the goal has the required CI or local result evidence. A different repository requires explicit operator Rebind. Canonical policy: `MichalMatu/local-agent/main/docs/AUTONOMOUS_CHAT_LOOP.md` and `docs/OPERATIONS.md`.

### Control branch contract

`agent-control` is a control plane, not a development branch. Product/source changes belong on the requested `work_branch`.

The control branch is reserved for Local Agent state under `.agent/`, including:

- `.agent/binding.json`
- `.agent/tasks/`
- `.agent/runs/`
- `.agent/results/`
- `.agent/status/`
- `.agent/daemon/`

The canonical implementation and operational documentation live in `MichalMatu/local-agent`. If that repository changes its control protocol, update this bootstrap section so future chats depend on repository evidence rather than remembered conversation context.

## Panel UI (`tools/panel/static/`) — układ pól

**Nie układaj parametrów w mini-kartach jeden pod drugim.** To powtarzający się błąd (donice, uprawa, aktuary).

### Zasada

W kartach **Donica N**, **aktuator**, **cel** itp. pola liczbowe / enum idą **w jednym poziomym rzędzie**, tak jak w reszcie panelu:

| Sekcja | Wzorzec (OK) |
|--------|----------------|
| Czujniki → Donice | `.pot-card-sensors` — siatka 2 kolumny (Wilg. \| Gleba T) |
| Cele → Donice | `.compact-row` + `.mini-cell` |
| Aktuary | `.field-stack` z **poziomym** `flex-direction: row` |
| Parametry growboxa → Donice | `.compact-row` w `.cultivation-pot-card` |

### Antywzorzec (NIE)

- `field-stack` + `flex-direction: column` wewnątrz `.pot-card` / `.cultivation-pot-card`
- pełna szerokość `.mini-cell` (`width: 100%`) w karcie, która ma **kilka** parametrów obok siebie
- osobna pionowa kolumna label+input pod label+input w jednej donicy

Efekt: marnowanie wysokości, brak spójności z Czujnikami i Aktuatorami.

### Przed commitem / po zmianie `form.js` lub `panel.css`

```bash
.venv/bin/python -m pytest tests/test_panel_layout.py -q
```

Testy są źródłem prawdy: `tests/test_panel_layout.py`.

### Układ strony

- **Lewa kolumna** — `card-stack`: Sterowanie, **Czujniki**, **Cele**, **Aktuary** (`#form-sections.card-stack`)
- **Prawa kolumna** — **Na żywo** (tabele czujników + paski aktuatorów + `panel-actions`; **Poprzedni stan** w modalu przez przycisk **Poprzedni**)
- **Panel modal** (`#modal-backdrop` → `.panel-modal.modal--wide`) — jeden przesuwalny modal; widoki z `panel-actions` pod Na żywo (bez zakładek/stopki w modalu)
- Donice w parametrach growboxa (modal **Growbox**): **ta sama szerokość** karty co w Czujnikach (`--pot-card-w`), 3 pola w poziomym gridzie

**Antywzorzec układu strony (puste dziury):**

- `.form-grid` z kartami o różnej wysokości obok siebie (np. Czujniki | Cele)
- `.growbox-params-split` (Obudowa obok Donic) — zostawia pustą przestrzeń
- siatka 2-kolumnowa na Aktuary (Klimat | Pompy), gdy jedna połowa jest niższa

Nie „optymalizuj” na jeden ekran kosztem pustych pól — lepiej zwarty pionowy stos.

### Pliki panelu

- Render: `tools/panel/static/js/form.js` (`renderZoneCultivationCard`, `renderPotCard`, `renderActuatorGroupCell`, …)
- Style: `tools/panel/static/panel.css` (`.card-stack`, `.compact-row`, `.pot-card`, `.cultivation-pot-card`)
- Szkielet: `tools/panel/static/index.html`
