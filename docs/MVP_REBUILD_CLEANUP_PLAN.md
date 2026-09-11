# MVP Rebuild Cleanup Plan

Status: frozen companion plan for `MVP_ENVIRONMENT_CONTROLLER.md`
Branch: `mvp/environment-controller`

This document defines how the repository is cleaned while rebuilding the climate-only MVP. It is part of the frozen implementation plan and exists to prevent the migration branch from becoming a permanent archive of obsolete v4/v5 concepts.

## 1. Cleanup principle

The climate MVP is a deliberate redesign, not an incremental extension of the previous multi-pot configurator architecture.

The repository history is already preserved by Git and the old working implementation remains available on `main` and historical commits/tags. Therefore obsolete code does not need to be kept as duplicate `legacy/`, `archive/`, `old/` or disabled directories on `mvp/environment-controller` merely for preservation.

Rules:

- `main` remains untouched by the MVP rebuild;
- work continues only on `mvp/environment-controller`;
- do not create another migration branch;
- do not keep dead copies of removed code inside the active branch;
- if old code is needed later, recover it from Git history or `main`;
- delete obsolete implementation only after its replacement path is proven green;
- the final branch must have one obvious active climate pipeline.

## 2. What the final MVP repository should optimize for

The active repository should make the product architecture obvious from the directory tree.

The important long-term areas are conceptually:

```text
docs/
schemas/

controller/
  domain / state
  configuration
  RuleControlPolicy
  arbitration
  SafetySupervisor
  status / reasons

tools/ml/
  physics/
  simulator
  controller input / feature encoding
  teacher
  dataset generation
  dataset audit
  training
  closed-loop benchmark
  calibration

embedded/ or components/
  runtime integration
  sensor adapters
  actuator adapters
  model inference
```

Exact directories may evolve during implementation. The important rule is separation of controller core, simulation/training and hardware adapters.

## 3. Code that is expected to survive the rebuild

Preserve unless evidence/tests justify replacement:

- useful climate physics, especially `tools/ml/physics/van_henten.py`;
- psychrometric helpers such as `tools/ml/physics/psychrometrics.py`;
- generic contract loading/hash/version mechanisms that remain useful after schema v5 simplification;
- leakage-free dataset splitting by scenario;
- deterministic seed/replay utilities that are generic;
- model export/inference infrastructure that can be adapted cleanly to the new contract;
- calibration concepts for heater response, fan exchange, humidifier delivery and CO2 response where still applicable;
- generic build/lint/test infrastructure that is not coupled to the old product model;
- source/research documentation that explains the physics provenance.

Do not preserve code only because it is large or expensive to recreate. Preserve it only when it serves the new architecture.

## 4. Code/concepts expected to disappear from the active MVP path

After replacement gates pass, remove code whose only purpose is the old multi-pot/product concept, including as applicable:

- 4-pot and 9-pot assumptions;
- pot arrays and per-pot feature expansion;
- soil moisture control;
- soil/root temperature control;
- irrigation outputs and pulse scheduling;
- heat-mat outputs;
- nutrient tank temperature/heater logic;
- EC/pH-related placeholders;
- old 15-output and 25-output ML contracts;
- old 128-feature / 228-feature contract assumptions;
- old teacher candidate generation for pots/nutrients;
- old dataset randomization for pots/nutrient systems;
- tests that assert obsolete feature/output counts or obsolete product semantics;
- compatibility code whose only consumer was the removed old contract.

Do not replace these with empty placeholders. Future plant/irrigation work receives a deliberate separate module/version.

## 5. Frontend cleanup decision

The current browser configurator under `web/` was designed around a much larger hardware/configuration concept, including old high-dimensional contracts and a chamber configurator.

It is not part of climate MVP v1 and must not drive the new controller or ML contract.

Expected cleanup after the climate core and replacement tooling are green:

- remove the old schema-driven hardware configurator if it remains tied to obsolete v4/v5 contracts;
- remove the 3D chamber configurator from the active MVP branch unless it proves directly useful for the new product;
- remove frontend-specific bundled copies of obsolete schemas;
- remove frontend tests/build jobs whose only purpose is the deleted configurator;
- update root build/CI scripts so deleted frontend jobs are no longer required.

Do not spend migration time rewriting this frontend for the new contract.

A future product UI should be rebuilt as a thin view/editor of stable `ControllerConfig` and `ControllerStatus` after the controller core is proven. UI must not define the architecture.

## 6. `tools/panel/` cleanup decision

The existing panel/server/bridge/form-schema tooling predates the simplified climate-only architecture.

Treat `tools/panel/` as migration-era tooling, not protected product code.

During the rebuild:

- keep it only if a part is genuinely useful for inspecting simulator/controller behavior;
- do not adapt old form/configuration machinery merely to keep it alive;
- prefer small purpose-built dataset/benchmark reports over maintaining a large configurator stack;
- once no required baseline/diagnostic flow depends on it, remove obsolete panel code and its tests.

If a lightweight diagnostic UI becomes useful later, rebuild it against `ControllerStatus` rather than old schema/form assumptions.

## 7. Documentation cleanup

Documentation must converge with implementation.

Keep:

- frozen MVP architecture and rebuild plan;
- hardware MVP set;
- simulator physics sources/provenance;
- calibration protocol that still applies;
- final climate contract and benchmark documentation.

Remove or clearly retire after migration:

- docs that describe old multi-pot contracts as active;
- frontend/configurator architecture that no longer exists;
- obsolete convergence/migration notes after they no longer help active work;
- contradictory v4/v5 feature/output counts presented as current state.

Do not leave multiple documents claiming to be the active contract.

## 8. Test cleanup

Tests are migrated in two phases.

Phase A — protection during rebuild:

- keep old tests long enough to capture the baseline and protect reusable modules;
- add new climate-only tests before deleting old behavior tests;
- keep physics regression tests independent from teacher/training tests.

Phase B — convergence:

- remove tests for intentionally deleted product behavior;
- rename/rewrite tests that still encode `pot`, `nutrient`, old `fan`, old `lights_active` or old output-count assumptions;
- remove frontend/panel tests with no remaining production/tooling target;
- final test suite must describe only the active architecture plus reusable generic utilities.

A deleted feature does not need a permanently failing/skipped regression test proving that it once existed.

## 9. Build, dependencies and CI cleanup

After code deletion, inspect and remove dead dependencies and build paths.

Expected candidates include:

- Node/pnpm dependencies if `web/` is removed;
- Three.js / React / Vite-related CI if no active frontend remains;
- Python dependencies used only by deleted panel/3D/twin/configurator tooling;
- Makefile targets for obsolete frontend or old contract-generation flows;
- GitHub Actions jobs that validate deleted components;
- generated schema snapshots that no active runtime consumes.

Do not remove a dependency solely because it looks unused by inspection; verify references/build targets first.

## 10. Cleanup timing and gates

Cleanup is progressive, not one giant final deletion commit.

Safe sequence:

```text
A. baseline old branch state
B. climate schema v6
C. climate state/features
D. climate simulator
E. physics/regression PASS
F. new teacher
G. dataset audit PASS
H. model + closed-loop benchmark PASS
I. active runtime/export path proven
J. delete obsolete implementation/tooling/docs/tests/dependencies
```

However, obvious isolated dead code may be removed earlier when all of the following are true:

- it has no remaining caller in the target path;
- no baseline comparison still requires it;
- replacement semantics are already covered by tests;
- deletion does not combine with a physics/teacher/training behavior change in the same commit.

Avoid a single enormous cleanup commit. Delete coherent areas separately so regressions are attributable.

## 11. Cleanup-specific stop conditions

Stop cleanup and investigate when:

- deleting code requires introducing compatibility shims for the old architecture;
- an allegedly obsolete module is still used by the new climate path;
- removing a frontend/panel directory unexpectedly changes simulator/training results;
- CI failures reveal hidden dependencies that were not understood;
- the proposed deletion removes provenance/calibration/physics knowledge rather than obsolete implementation;
- a replacement path has not yet reached its acceptance gate.

The goal is simplification, not deletion for its own sake.

## 12. Final active-contract rule

At completion there must be exactly one authoritative active climate ML contract/schema.

Old contracts may exist in Git history, tags or release artifacts, but the active source tree must not present multiple old schemas as selectable/current product definitions unless there is a concrete runtime compatibility requirement.

The same rule applies to:

- feature counts;
- output counts;
- simulator path;
- teacher path;
- dataset generator;
- model export path.

One active path is preferred over compatibility complexity in MVP.

## 13. Future UI rule

The MVP does not need a frontend configurator to prove climate control.

Future UI is allowed only after stable controller config/status semantics exist. Its role is:

```text
ControllerConfig <-> UI
ControllerStatus -> UI
```

not:

```text
UI schema -> defines controller architecture -> defines ML model
```

This prevents future UI work from coupling hardware/product configuration directly to ML feature dimensions again.

## 14. Go / no-go gate for starting code changes

The planning phase is complete when all of the following are true:

- climate MVP boundary is explicit;
- pots/irrigation/nutrients are outside v1;
- product roles and ML outputs are separated;
- ML v1 feature semantics are defined;
- light and circulation-fan policy boundaries are defined;
- CO2 semantics require one timestep-invariant injection path;
- protected physics modules are identified;
- teacher rebuild principles are defined;
- dataset audit is a mandatory pre-training gate;
- closed-loop control is the primary model acceptance test;
- future plant/irrigation extension boundary is defined;
- cleanup strategy and recovery path through Git/main are defined;
- implementation order and stop conditions are defined.

All of these conditions are satisfied by the frozen MVP documents as of this plan.

## 15. Frozen verdict

**GO: begin code changes.**

Further architecture planning before implementation is more likely to create speculative complexity than reduce risk.

The next work item is not another design pass. It is Stage 0 from the frozen plan:

1. capture the current branch HEAD;
2. run and record the existing test baseline;
3. record current contract hash/feature/output dimensions;
4. save deterministic old-simulator reference traces;
5. then implement the climate-only schema/contract v6 as the first behavioral migration step.

No frontend rewrite and no broad cleanup should precede this baseline capture.
