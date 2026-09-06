# Stage28E Phase E Handoff — Measured Memory Optimization

Updated: 2026-09-07
Work branch: `mvp/environment-controller`
Phase E implementation head: `4a8ce18edd8cc90e6300929d2d9f035c4ec49eb5`
Previous handoff: `docs/STAGE28E_PHASE_D_HANDOFF.md`
Next phase: **Stage28E Phase F — focused binary-arbiter continuity/regression proof**

## Phase E outcome

**Phase E implementation and bounded hardware verification are complete.**

The phase recovered internal-RAM headroom with three small, evidence-driven changes while preserving the controller, AH, RF and safety semantics:

1. move only the telemetry queue payload to PSRAM with an internal-RAM fallback;
2. right-size the `stage27_store` task stack from `7168 B` to `6144 B`;
3. right-size only the Stage27C main task stack from `16384 B` to `12288 B`.

No blanket PSRAM allocator policy was enabled. `CONFIG_SPIRAM_USE_MALLOC` remains disabled. RMT/ISR/DMA-sensitive storage was not moved. No control, AH, arbiter, RF, thermal or output behavior was changed.

## Starting point from Phase D

Phase D final bounded baseline on implementation SHA `09340089767cde117d12acc049790a2b93778b8e`:

- internal free/min/largest: `213900 / 213264 / 172032 B`;
- PSRAM free/min/largest: `8363512 / 8363108 / 8257536 B`;
- main task configured stack: `16384 B`;
- main HWM: `11336 B` free;
- `stage27_store` configured stack: `7168 B`;
- image: `743477 B`;
- `.bss`: `10216 B`;
- safe final state: `fake-locked`;
- Shelly master ON, median about `65.5 W`.

## E0 — ESP-IDF 5.5.4 allocation contract audit

The installed local ESP-IDF 5.5.4 audit confirmed:

- `CONFIG_SPIRAM_USE_CAPS_ALLOC=y`;
- `CONFIG_SPIRAM_USE_MALLOC` is not set;
- `CONFIG_FREERTOS_TASK_CREATE_ALLOW_EXT_MEM=y`;
- ordinary FreeRTOS queue/task allocation remains internal unless an explicit caps-aware/static path is selected;
- caps-aware task APIs are available, but external task stacks have stricter execution/cache constraints than generic queue storage.

Decision: use targeted queue storage placement first; do not globally enable PSRAM malloc and do not move the storage task stack to PSRAM.

## E1 — telemetry queue payload to PSRAM

Implementation SHA:

`4a5121abf2a93ba76bfc219575d2b52b8025fb03`

Change:

- queue depth remains `16`;
- `sizeof(Stage27TelemetrySnapshot) = 296 B`;
- queue payload size remains `4736 B`;
- `StaticQueue_t` control metadata stays inside the logger object/internal memory;
- the queue payload buffer is allocated explicitly with `MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT`;
- if that allocation fails, code falls back to the previous `xQueueCreate()` internal-RAM path;
- task priority, task stack and queue semantics are unchanged.

Software gate:

- exact SHA PASS;
- firmware build PASS;
- image `743637 B`;
- host tests `24/24 PASS`;
- generated config still has `CONFIG_SPIRAM_USE_CAPS_ALLOC=y` and no global `CONFIG_SPIRAM_USE_MALLOC`;
- clean worktree / `git diff --check` PASS.

Bounded hardware evidence:

- explicit marker: `queue_psram=1 queue_bytes=4736`;
- internal free/min/largest: `218672 / 218140 / 176128 B`;
- gain vs D2: `+4772 B free`, `+4876 B min`;
- PSRAM free/min/largest: `8358772 / 8358368 / 8257536 B`;
- main HWM: `11160 B` free at the final sample;
- `stage27_store` HWM: `2988 B` free with its original `7168 B` stack;
- telemetry records written: `12`;
- queue drops: `0`;
- storage write errors: `0`;
- 11 heartbeats and heap-integrity PASS;
- no coredump, arbiter counter regression, crash, corrupt heap or stack-canary marker;
- Shelly master ON, median `65.5 W`;
- final state `fake-locked`.

The first hardware task reported `failed` because its parser treated auxiliary `status ...` lines without storage fields as if they had `-1` drops. A read-only evidence recheck v3 parsed heap/HWM from `status firmware_sha=...` and storage data from `soak_v=2 ...`; it passed and did not require reflashing.

## E2 — right-size `stage27_store` stack

Implementation SHA:

`c2aff0a14bbcca567de4083a284d3522fa52421e`

Change:

- `stage27_store` stack `7168 -> 6144 B`;
- no queue placement, storage behavior, task priority or control behavior change.

Software gate:

- exact SHA PASS;
- image `743637 B`;
- host tests `24/24 PASS`;
- clean worktree PASS.

Bounded hardware evidence:

- internal free/min/largest: `219568 / 219036 / 176128 B`;
- gain vs E1: `+896 B free`, `+896 B min`;
- `stage27_store` configured stack: `6144 B`;
- worst observed HWM: `1884 B` free;
- telemetry records written: `12`;
- queue drops: `0`;
- storage write errors: `0`;
- 11 heartbeats and heap-integrity PASS;
- Shelly master ON, median `65.5 W`;
- final state `fake-locked`.

Decision: do not reduce `stage27_store` below `6144 B` in Phase E. The measured `~1.8 KiB` worst free margin is adequate for the tested workload but no longer large enough to justify another cut before longer Phase G runtime evidence.

## E3 — right-size Stage27C main task stack

Implementation SHA:

`4a8ce18edd8cc90e6300929d2d9f035c4ec49eb5`

Change:

- base project default remains `CONFIG_ESP_MAIN_TASK_STACK_SIZE=16384`;
- only `config/idf/sdkconfig.defaults.stage27c` overrides Stage27C to `12288 B`;
- other build modes are not globally changed.

Software gate:

- generated Stage27C `sdkconfig` explicitly contains `CONFIG_ESP_MAIN_TASK_STACK_SIZE=12288`;
- firmware build PASS;
- image `743641 B`;
- host tests `24/24 PASS`;
- clean worktree PASS.

Bounded hardware evidence:

- internal free/min/largest: `223792 / 223260 / 180224 B`;
- gain vs E2: `+4224 B free`, `+4224 B min`;
- cumulative gain vs D2: `+9892 B free`, `+9996 B min`;
- main task configured stack: `12288 B`;
- worst observed main HWM: `7240 B` free;
- `stage27_store` configured stack: `6144 B`;
- worst observed storage-task HWM: `1820 B` free;
- telemetry records written: `12`;
- queue drops: `0`;
- storage write errors: `0`;
- 11 heartbeats and heap-integrity PASS;
- largest internal block improved to `180224 B`;
- Shelly master ON, median `65.5 W`;
- final state `fake-locked`;
- no coredump, counter regression, crash, corrupt heap or stack-canary marker.

Decision: stop main-stack optimization at `12288 B`. The tested free margin is large, but Phase E is complete and further tuning should be based on Phase G long-runtime evidence rather than progressively shrinking stacks.

## Phase E aggregate result

Measured bounded-runtime comparison:

| Metric | Phase D baseline | Phase E final | Delta |
| --- | ---: | ---: | ---: |
| internal free | `213900 B` | `223792 B` | `+9892 B` |
| internal min | `213264 B` | `223260 B` | `+9996 B` |
| internal largest block | `172032 B` | `180224 B` | `+8192 B` |
| main configured stack | `16384 B` | `12288 B` | `-4096 B reserved` |
| main worst free HWM | `11336 B` | `7240 B` | still large margin |
| storage configured stack | `7168 B` | `6144 B` | `-1024 B reserved` |
| storage worst free HWM | about `2988 B` before E2 | `1820 B` final | acceptable, stop here |
| telemetry queue payload internal | `4736 B` | `0 B` on PSRAM path | `4736 B` moved |
| image | `743477 B` | `743641 B` | `+164 B` |

The final internal-memory gain is about `9.9 KiB` while preserving the measured runtime behavior and safety boundary.

## Safety / behavior statement

Phase E did **not** change:

- rule-controller authority;
- ML shadow/research-only policy;
- AH demand calculations;
- `Stage28dBinaryRoleArbiter` algorithm or counters;
- RF protocol or output routing;
- thermal trip `>=28 C`;
- recovery `<=26 C` continuously for 10 minutes;
- manual RF block during `real-bounded`;
- final fake-locked hardware policy.

Hardware work used only `/dev/cu.usbserial-1130` with `board:growbox-s3` and safe flags; `/dev/cu.usbserial-10` was not used.

## Why Phase E stops here

The phase has achieved its goal without broad allocator churn:

- a large, proven PSRAM-eligible queue payload moved out of internal RAM;
- two stacks were right-sized from measured HWM data;
- internal free/min and largest-block metrics all improved materially;
- no tested storage or runtime regression appeared.

Further cuts now provide diminishing memory benefit while increasing stack-risk. Service-console and other transient frames remain candidates only if later Phase G evidence identifies pressure.

## Phase F entry condition and scope

After the formal Phase E docs/exit gate passes, Phase F may start.

Phase F is **not** another memory optimization phase. It is the focused V5-inspired binary-arbiter continuity/regression proof.

Required proof:

1. run the arbiter in a single known instance with synthetic inputs;
2. hold request below threshold and around the minimum-OFF dwell boundary;
3. prove cumulative dwell-hold counters are monotonic within one instance;
4. prove a continuous single instance cannot produce the historical `43 -> 1` style regression except through allowed integer wrap;
5. prove that after the full 120 s minimum-OFF dwell an eligible `0.111` request can transition ON;
6. preserve lifecycle/boot/instance evidence around the test;
7. do not modify `applyBinary()` merely to fit historical V5 logs;
8. keep all physical outputs fake-locked during this proof.

Long runtime soak remains Phase G. Final physical `AH/rule request -> binary arbiter -> RF -> physical fan` remains Phase H only.
