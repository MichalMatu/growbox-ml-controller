# Project layout

Intentional repository structure after the architecture cleanup. Current runtime status is tracked in `CURRENT_STATUS.md`; historical Stage27/Stage28 evidence remains under `docs/` for reproducibility.

```text
.
├── README.md
├── LICENSE
├── AGENTS.md
├── Makefile
├── CMakeLists.txt
├── pyproject.toml
├── requirements-lock.txt
├── requirements-dev.txt
│
├── config/
│   ├── boards/                  # board profiles
│   ├── runtime/                 # canonical runtime config + profiles
│   └── idf/                     # sdkconfig/partition profiles
├── schemas/                     # controller/trace contracts
├── docs/                        # live docs + historical qualification evidence
├── tools/                       # host tooling, ML/panel/sandbox helpers
├── scripts/                     # quality/config/IDF/runtime guards and helpers
├── examples/
├── third_party/
│
├── lib/environment_control/     # portable controller core
├── components/                  # ESP-IDF third-party/local components
├── src/
│   ├── main.cpp                 # thin app-mode dispatcher
│   ├── legacy/                  # explicit legacy app mode only
│   └── climate/
│       ├── native/              # sensors/RTC/native I/O
│       ├── output/              # OutputSupervisor architecture
│       ├── rf433/               # RF protocol/transport
│       ├── runtime/             # real-input composition/coordinator/console
│       ├── storage/
│       └── telemetry/
│
├── test/                        # portable C++/host tests
├── tests/                       # Python/scientific/tool tests
├── build/                       # local artifacts, gitignored
└── logs/                        # local captures, gitignored
```

## Runtime boundary map

The production real-input path is intentionally separated:

- `ClimateV6RealInputRuntime.cpp`: bootstrap only;
- `runtime/RealInputRuntimeComposition.*`: ownership/lifetime wiring;
- `runtime/RealInputRuntimeCoordinator.*`: cycle orchestration;
- `runtime/RuntimeOutputTransport.*`: transport truth boundary;
- `runtime/RuntimeOutputTelemetryLog.*`: telemetry formatting;
- `output/*`: configured-output ownership/policy/execution;
- `rf433/*`: policy-free RF transport.

Do not move climate policy into transport or direct configured-output writes back into runtime/console code.

## Configuration boundary

Board/runtime defaults live under `config/` and are resolved by CMake. Production C++ consumes the generated typed `RuntimeBuildConfig.h`; do not add duplicate fallback default tables in source files.

## Repository branches after cleanup

- `main`: normal product development;
- `agent-control`: Local Agent control state;
- `gh-pages`: publishing output.

Short-lived implementation/refactor branches should be deleted after their commits are fully integrated into `main`.

## Where new work belongs

| Work | Location |
|---|---|
| Portable controller behavior | `lib/environment_control/src/climate/` |
| Real hardware/runtime orchestration | `src/climate/runtime/` / `src/climate/native/` |
| Output ownership/policy | `src/climate/output/` |
| RF433 transport/protocol | `src/climate/rf433/` |
| Runtime/board configuration | `config/` |
| Host analysis / ML / sandbox | `tools/` |
| Quality/build helpers | `scripts/` |
| Contracts | `schemas/` |
| Current docs and historical evidence | `docs/` |
