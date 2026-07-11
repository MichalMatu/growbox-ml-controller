# Data contract v1

The machine-readable source of truth is
[`schemas/environment-controller-v1.json`](../schemas/environment-controller-v1.json). Do not add a
Python-only or C++-only feature. Change the schema, regenerate derived files, retrain the model, and
commit all resulting deterministic artifacts together.

## Inputs

The contract includes:

- six measurements and a separate validity mask for every measurement;
- growbox volume, thermal mass, heat loss, and air leakage;
- pot volume, substrate water capacity, and transpiration factor;
- heater, fan, humidifier, and irrigation-pump availability and capabilities;
- temperature, humidity, CO2, and soil-moisture targets;
- the previous four normalized actuator commands.

Every scalar has a unit, allowed range, normalization range, and default. The generated header owns
the exact model-feature order and count.

## Missing sensors

A missing or rejected reading has a false validity mask. Its numeric slot is replaced with the
contract default before normalization; the mask tells the model that the value is imputed. A
non-finite reading is still an invalid controller input and causes the independent safety layer to
select a fail-safe decision.

## Missing actuators

An absent actuator is represented by `available = false` and zero maximum capability. The feature
encoder supplies that state to the model, and the safety supervisor independently forces the final
command to zero. Availability is therefore both learnable context and a hard constraint.

## Outputs

The model output order is `heater`, `fan`, `humidifier`, `irrigation`. All four are continuous and
normalized to `[0, 1]`. A physical adapter interprets them according to an actuator's control type.
Safety may quantize a binary actuator or suppress/limit an irrigation pulse.

## Version and hash

The schema version identifies compatibility policy; the canonical short hash detects an exact
contract mismatch. Firmware boot records expose both. `ModelRuntime` rejects a generated model
whose input/output dimensions or schema hash do not match the compiled contract.
