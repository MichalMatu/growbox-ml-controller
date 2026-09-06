# Agent notes — Growbox ML

## Local Agent — repository workflow

This repository is registered in the shared `MichalMatu/local-agent` multi-repository supervisor. Read the live daemon version, revision and execution model from `.agent/status/daemon.json` on `agent-control`; do not hard-code a Local Agent release number in this repository.

Repository identity:

- repository: `MichalMatu/growbox-ml-controller`
- local-agent repository id: `growbox-ml-controller`
- agent binding: `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`
- control branch: `agent-control`
- default source branch: `main`
- execution model: one shared bounded-parallel supervisor; one task per repository at a time, with cross-repository overlap only when task resource admission permits it; the serial supervisor remains the fallback and enforces the same binding contract

### New chat bootstrap

When starting work on this repository in a new chat/session:

1. Read this `AGENTS.md` and the current `README.md` before proposing or executing changes.
2. Inspect the current GitHub state of the repository and the branch relevant to the requested work. Do not assume `main` is always the correct work branch; the README may identify an active integration branch.
3. For repository-only software work, read `docs/SANDBOX_EXECUTION_FLOW.md` and prefer the exact ChatGPT Sandbox source snapshot plus matching dependency packs before creating a Local Agent task.
4. If Chat Bridge is active, require the wake envelope to identify exactly repository id `growbox-ml-controller`, repository `MichalMatu/growbox-ml-controller`, and agent binding `815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5`. Never infer or switch repository identity from remembered chat context; a different repository requires explicit Bridge Rebind.
5. Use this repository's own `agent-control` branch for Local Agent tasks. Never send Growbox tasks through another repository's control branch (for example LiteGraph).
6. Verify `.agent/binding.json` on `agent-control` matches the repository identity above before queueing work when binding compatibility matters.
7. For local execution, submit task requests under `.agent/tasks/<task-id>.json` on `agent-control`; every executable task must contain exactly `"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"` and explicit `resources`.
8. Follow execution through `.agent/runs/<task-id>.json` and `.agent/status/daemon.json`.
9. Read the terminal result from `.agent/results/<task-id>.json` before reporting completion.
10. Prefer remote status/results from GitHub over asking the user to copy local terminal logs when Local Agent can provide the state directly.
11. Keep repository workspaces isolated. A task for this repository must not read, modify, checkpoint, or publish results through another repository's Local Agent workspace.

### ChatGPT Sandbox-first software execution

For repository-only work, the default software worker is ChatGPT Sandbox, not Local Agent. GitHub `main` remains the source of truth. Persistent sandbox artifacts for this repository live only under `/GrowboxML/Sandbox/`; never reuse another repository's source snapshot or dependency pack implicitly.

Use the exact `growbox-source-<sha>.tar.zst` snapshot for the Git SHA being worked on and materialize only the matching pack(s) needed by the changed surface:

- `host` — Python 3.11, ML, portable C++ and host clang tooling
- `web` — Node 22 / pnpm 11.10.0 frontend dependencies
- `idf` — ESP-IDF 5.5.4, ESP32-S3 toolchain and `esp-clang`; load together with `host`

After bootstrap, always source the generated sandbox `env.sh` and run `tools/sandbox/sandbox-doctor.sh` before claiming the environment is usable. Use `tools/sandbox/run-sandbox-check.sh host`, `web`, `idf` or `quality` for verification. Dependency-key mismatches are hard failures; do not bypass them or silently rebuild against a different source snapshot.

Use Local Agent when the requested evidence actually depends on the Mac, USB/serial, flashing, a physical ESP32-S3, board E2E, screenshots that require the local desktop, or other machine-specific state. A successful sandbox IDF build is software evidence only and must never be reported as a flashed or hardware-tested board.

Canonical details, Library layout and lifecycle: `docs/SANDBOX_EXECUTION_FLOW.md`.

### Control branch contract

`agent-control` is a control plane, not a development branch. Product/source changes belong on the requested source/work branch. The control branch is reserved for Local Agent binding, queue, status, run, result, and daemon-control files under `.agent/`.

The canonical Local Agent implementation and operational documentation live in `MichalMatu/local-agent`. If the control protocol changes, update this bootstrap section so future chats do not depend on remembered conversation context.

Hard binding is fail-closed. The executor requires local registry `agent_binding == .agent/binding.json agent_binding == task.agent_binding` before claim/execution. Missing repository binding reports `unbound`; a control mismatch reports `binding_error`; missing/wrong task binding is terminally rejected before any task command runs. Do not “repair” a task by changing or guessing its binding.

Every task must declare `resources` explicitly. Missing or invalid declarations are terminal task-contract errors; there is no compatibility fallback to `machine`. Use `resources: []` for repository-local software work, including builds/tests, when no exclusive external device or host-global state is used. `memory_limit_mb` is an independent RSS watchdog and does not determine resource classification. Use stable named resources such as `board:growbox-s3` for USB/serial/flash/monitor/hardware work so only tasks sharing that concrete resource serialize. Use `resources: ["machine"]` only for genuine whole-host operations such as global Local Agent maintenance or host-global toolchain mutation. Resource contention is a wait state: the immutable task remains pending and is retried. Read repository-worker truth such as `daemon_version`, `self_revision`, `execution_model` / `execution_variant`, current task state, and `supervisor_pid` from `.agent/status/daemon.json`. Supervisor-wide fields such as `max_parallel_workers` are not guaranteed to be repeated in every repository-worker status snapshot; read the shared supervisor status when that field matters. Do not pin a Local Agent release number here.

For substantial coding tasks, prefer `workflow_policy: "efficient-verification-v1"` with explicit `work` / `focused` stages and exactly one final `full` verification stage. Task payloads are immutable: a claimed or interrupted task is not replayed automatically, so changed work or an intentional retry must use a new unique task id. A successful local task proves execution and verification; source publication remains an explicit final step.

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

### Direct GitHub work and local execution

Use an available GitHub tool with write permission for bounded source/configuration/documentation changes when the exact diff and relevant CI can verify the outcome. A commit proves publication, not successful execution. Report the exact commit and completed checks. Do not create an artificial Local Agent task when GitHub evidence already provides the required verification.

For repository-only software execution, prefer the sandbox-first flow above. Use Local Agent for Mac command execution, local builds/tests when the sandbox pack cannot represent the required host state, device access and machine-specific evidence. A hybrid flow may edit through GitHub and run a read-only local verification task for the exact committed SHA; verify that SHA explicitly in an early stage (`expected_head` is not a supported task field). Check current daemon/run evidence before a direct write and avoid racing a local task that is modifying the same branch. Follow this repository's branch policy.

Local tasks retain their unique immutable ids, exact `agent_binding`, explicit `resources`, bounded limits and terminal result requirement. When Chat Bridge is active, both paths remain confined to its immutable repository binding. Use `STOP` only after the goal has the required CI or local result evidence. A different repository requires explicit operator Rebind. Canonical policy: `MichalMatu/local-agent/main/docs/AUTONOMOUS_CHAT_LOOP.md` and `docs/OPERATIONS.md`.
