# Fresh-context continuation plan

Updated: 2026-09-04
Work branch: `mvp/environment-controller`
Control branch: `agent-control`

The authoritative handoff is `/continuation.md`.

Current transition:

**Stage28A DONE -> Stage28B DONE -> Stage28C DONE -> pre-Stage28D golden hardening active**

Stage28C has frozen exactly one neutral RF433 remote/socket identity. Detailed evidence is in `docs/STAGE28C_FINAL_EVIDENCE.md`.

Current hardened source at this checkpoint: `60da0a4d2a99f3045596b6a8a8bf362a0c6e1aca`.

Current receive settings are `100 kHz`, `10 us` minimum signal and `20 ms` idle/max signal. Do not reconstruct the active implementation from historical Stage28B receive values.

Before Stage28D, complete one clean golden gate consisting of full software regressions, firmware build, documentation consistency and a bounded real-board soak with outputs fake-locked.

Do not introduce semantic role mapping, unattended 230 V control or physical-state acknowledgement semantics as part of this pre-stage cleanup.
