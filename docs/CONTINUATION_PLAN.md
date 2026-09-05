# Fresh-context continuation plan

Updated: 2026-09-05
Work branch: `mvp/environment-controller`
Control branch: `agent-control`
Primary roadmap/handoff: `docs/PROJECT_ROADMAP.md`

## Read first in a new chat

1. `AGENTS.md`
2. `docs/PROJECT_ROADMAP.md`
3. `docs/CURRENT_STATUS.md`
4. this file
5. stage-specific evidence only when needed

Then fetch fresh `mvp/environment-controller` HEAD and `agent-control:.agent/status/daemon.json`. Never continue from remembered chat state alone.

## Current transition

**Stage27C FROZEN -> Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden gate COMPLETE -> Stage28D manual RF path COMPLETE -> semantic/safety integration NEXT**

The service-console firmware `af16aebde8f69d1a1257256c7711e9721c07c9d5` is hardware-qualified for the current manual diagnostic path.

On 2026-09-05 the operator physically confirmed correct ON/OFF response for all three RF loads:

- lamp: `235030016` / `16926208`, 560 us, repeat 10;
- fan: `906118656` / `1040336384`, 575 us, repeat 10;
- humidifier: `637683200` / `771900928`, 560 us, repeat 10.

Do not redo these manual RF identity tests unless new evidence invalidates them.

## Current locked boundary

- rule policy authoritative;
- ML shadow/research-only;
- automatic physical outputs fake-locked;
- no unattended real-output control authorized yet;
- manual RF is only an explicit bounded operator-present diagnostic;
- physical observation remains the acceptance criterion for mains-load actuation.

## Architecture decision for current loads

- fan RF endpoint -> intended semantic role `ExhaustFan`;
- humidifier RF endpoint -> intended semantic role `Humidifier`;
- lamp stays under the lighting schedule/timer for normal operation.

Lamp safety is a separate higher-priority layer:

`schedule/timer -> requested lamp state -> thermal safety override -> physical output`

The current Climate-v6 model receives `schedule.light_level` and the simulator accounts for lamp heat, but lamp is not one of the six ML outputs. Do not add a seventh ML output merely to complete the next hardware gate.

## First incomplete gate

Start with **software-only semantic/safety integration** while keeping the real runtime fake-locked:

1. bind fan endpoint to `ExhaustFan`;
2. bind humidifier endpoint to `Humidifier`;
3. create/use a dedicated scheduled-light endpoint/path for the lamp;
4. implement an independent lamp over-temperature OFF override with recovery hysteresis;
5. ensure high-temperature safety can demand maximum exhaust ventilation when available;
6. ensure unknown/duplicate/missing mappings fail closed;
7. add focused host tests proving mapping/arbitration without real RF TX.

Do not perform physical actuation in this first software slice.

## Next hardware session after software qualification

When the software slice passes its focused/build gate:

1. flash the exact qualified firmware and verify SHA, sensors, RF readiness and `outputs=fake-locked` before actuation;
2. run one operator-present physical role-routing test per endpoint, each ending OFF;
3. test the lamp thermal override using deterministic injected/simulated over-temperature rather than deliberately overheating the growbox;
4. physically verify lamp forced OFF and fan forced ON under that injected condition;
5. verify recovery hysteresis/hold behavior;
6. run a short supervised real-sensor closed-loop session;
7. only after all supervised gates pass, propose a separate unattended real-output soak for explicit operator approval.

## Local Agent / Chat Bridge essentials

Hard binding for every Growbox task:

`"agent_binding": "815cf40f-8d2a-4e1f-b7cc-c0f4e37b6cb5"`

Use `resources: []` for software/docs/build and `resources: ["board:growbox-s3"]` for USB/serial/flashing/hardware. Task IDs and payloads are immutable. `agent-control` holds task/run/result/status state; product/source changes belong on `mvp/environment-controller`.

Chat Bridge only transports wakeups and pins repository identity. Local Agent deterministically executes queued tasks. ChatGPT remains the planner and must inspect terminal result evidence before claiming completion.

Recommended first message in the fresh chat:

`Continue Growbox from docs/PROJECT_ROADMAP.md. Verify fresh work-branch HEAD and Local Agent daemon first. Start from the first incomplete gate. Keep real automatic outputs fake-locked until the roadmap reaches a supervised hardware gate.`
