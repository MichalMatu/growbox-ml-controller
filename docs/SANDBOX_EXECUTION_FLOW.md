# Sandbox-first execution for Growbox ML Controller

This repository supports a ChatGPT Sandbox workflow that is deliberately independent from other repositories. The persistent Library location is:

```text
/GrowboxML/Sandbox/
```

Nothing from PhotoMaps or another project is reused implicitly.

## Source of truth and execution roles

1. **GitHub `main` is the source of truth.**
2. **ChatGPT Sandbox is the default software worker** for repository-only implementation, Python/ML checks, portable C++ tests, frontend checks and ESP-IDF compilation/static analysis.
3. **Local Agent is reserved for machine/device evidence**: USB, flashing, serial monitor, real ESP32-S3 board tests, screenshots that require the local desktop, or other host-specific state.
4. GitHub Actions remains the canonical clean-room verification before merge.

A source snapshot is immutable and named:

```text
growbox-source-<git-sha>.tar.zst
growbox-source-<git-sha>.tar.zst.sha256
```

The snapshot contains `.sandbox-snapshot/` with the exact Git SHA and dependency keys.

## Why there are three dependency packs

Growbox is not one runtime. It has three independent software stacks, so a single giant offline archive would waste transfer and extraction time.

```text
growbox-host-<host-key>/
growbox-web-<web-key>/
growbox-idf-<idf-key>/
```

### Host pack

Used for Python/ML and portable C++ work.

Contains:

- relocatable CPython 3.11 runtime
- offline wheelhouse for `requirements-lock.txt` and `requirements-dev.txt`
- TensorFlow and ML dependencies
- clang-format 19.1.5
- portable clang-tidy runtime

The project deliberately requires Python 3.11; the sandbox's system Python is not used for Growbox host checks.

### Web pack

Used only for `web/`.

Contains:

- pnpm 11.10.0 CLI
- an offline pnpm store resolved from `web/pnpm-lock.yaml`

The sandbox supplies Node.js 22. Bootstrap refuses another Node major.

### ESP-IDF pack

Used for firmware compilation and `clang-check`.

Contains:

- ESP-IDF 5.5.4
- the complete ESP-IDF tool set selected by the packed `idf-env.json` for the ESP32-S3 environment
- `esp-clang` for the repository's clang static-analysis gate
- the ESP-IDF tool-install metadata and `espidf.constraints.*.txt` required to reproduce/validate the environment offline
- an offline wheelhouse for the IDF Python environment

The IDF pack intentionally depends on the host pack's Python 3.11 runtime. This avoids storing a second CPython distribution. After restore, sandbox activation sources the official packed ESP-IDF `export.sh`; the pack builder verifies that activation before publishing the archive.

## Dependency keys

Run:

```bash
tools/sandbox/dependency-key.sh host
tools/sandbox/dependency-key.sh web
tools/sandbox/dependency-key.sh idf
```

A pack can only be loaded when its key matches the source tree/snapshot.

Host key inputs:

- `requirements-lock.txt`
- `requirements-dev.txt`
- `pyproject.toml`
- `.pre-commit-config.yaml`

Web key inputs:

- `web/package.json`
- `web/pnpm-lock.yaml`
- `web/pnpm-workspace.yaml`

The IDF key pins the sandbox toolchain contract to ESP-IDF 5.5.4, ESP32-S3 and x86_64 Linux.

## Persistent Library layout

Recommended final layout:

```text
/GrowboxML/Sandbox/
  growbox-source-<sha>.tar.zst
  growbox-source-<sha>.tar.zst.sha256

  growbox-host-<host-key>/
    manifest/
    part-000
    part-001
    ...

  growbox-web-<web-key>/
    manifest/
    part-000
    ...

  growbox-idf-<idf-key>/
    manifest/
    part-000
    part-001
    ...
```

Pack archives are split into bounded parts. `manifest/parts.sha256` verifies every part and `manifest/archive.sha256` verifies the reassembled archive before extraction.

## Bootstrap in ChatGPT Sandbox

After extracting the exact source snapshot and materializing the matching pack directories:

```bash
cd /mnt/data/growbox-source

./tools/sandbox/bootstrap-sandbox.sh /mnt/data/growbox-sandbox \
  --host /mnt/data/packs/growbox-host-<host-key> \
  --web /mnt/data/packs/growbox-web-<web-key> \
  --idf /mnt/data/packs/growbox-idf-<idf-key>

source /mnt/data/growbox-sandbox/env.sh
./tools/sandbox/sandbox-doctor.sh
```

For a task that only touches the frontend, use only `--web`. For a host-only C++/Python task, use only `--host`. Firmware checks require both `--host` and `--idf`.

Bootstrap performs only offline dependency installation from the pack. It does not fetch project dependencies from the Internet.

## Check profiles

```bash
./tools/sandbox/run-sandbox-check.sh doctor
./tools/sandbox/run-sandbox-check.sh host-fast
./tools/sandbox/run-sandbox-check.sh host
./tools/sandbox/run-sandbox-check.sh web
./tools/sandbox/run-sandbox-check.sh idf
./tools/sandbox/run-sandbox-check.sh quality
```

`host` runs static checks, non-hardware pytest, the isolated quick ML smoke test, portable CMake/CTest and host clang-tidy.

`web` runs the existing `pnpm gate`: typecheck, lint, tests and production build.

`idf` builds the ESP32-S3 N8 firmware with ESP-IDF 5.5.4 and runs the existing clang static-analysis gate with `esp-clang`.

`quality` executes host + web + IDF checks.

Hardware tests are never claimed by sandbox profiles.

## GitHub Actions: Sandbox Pack

`.github/workflows/sandbox-pack.yml` creates:

- an exact source snapshot on every relevant push/manual run
- host/web/IDF packs only when their dependency/tooling inputs changed, or when a manual run forces rebuild
- a full sandbox-pack validation job when all three packs are rebuilt together

This means ordinary source changes create a new small source snapshot but continue to reuse existing dependency packs.

The normal `.github/workflows/ci.yml` remains canonical for clean CI. A green pack workflow proves pack construction/integrity; a green normal CI proves the repository's official gates.

## Expected task flow

For each new software task:

1. Read current GitHub `main` SHA.
2. Find the matching `growbox-source-<sha>` in `/GrowboxML/Sandbox/`.
3. Materialize only the required pack(s).
4. Verify checksums and dependency keys.
5. Bootstrap the sandbox.
6. Run `sandbox-doctor.sh`.
7. Implement the change.
8. Run the narrowest relevant profile first.
9. Run broader profiles when the changed surface requires them.
10. Publish on a feature branch / PR.
11. Require canonical GitHub CI green before merge.
12. After merge, store the new exact source snapshot in Library.
13. Store a new dependency pack only when its key changed.

Use Local Agent only when the task needs actual Mac/USB/serial/hardware state.

## What is intentionally not sandboxed

The following require Local Agent or another real hardware worker:

- `make flash`
- `make monitor`
- `make flash-monitor`
- `make test-board`
- exhaustive board validity/audit jobs
- any test requiring `GROWBOX_BOARD_PORT`
- physical sensor/actuator behavior

A successful firmware compilation is not evidence that a physical board was flashed or tested.
