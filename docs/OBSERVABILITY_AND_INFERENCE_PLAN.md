# Growbox observability and inference plan

Updated: 2026-09-05

## Purpose

Use the sensors and independent measurements already present in the reference growbox to extract substantially more information than isolated instantaneous readings. The first objective is deterministic observability and fault detection. Learned/predictive control and ML may consume these signals later, but must not replace hard safety rules.

The guiding principle is:

`raw measurements + actuator transitions + time -> derived state + measured actuator effect + confidence`

Do not claim a hidden physical quantity more precisely than the available measurements support. Prefer directly observed response rates and confidence-scored effects over falsely precise inferred values.

## Available raw signals

### TP357 inside canopy sensor

Primary authoritative signals:

- inside air temperature;
- inside relative humidity;
- sample age/freshness;
- battery/packet quality where available.

Use TP357 temperature as the authoritative thermal-safety input.

### SCD41 inside pot-height sensor

Primary authoritative signal:

- inside CO2 concentration.

Secondary/diagnostic signals:

- temperature;
- relative humidity;
- sample validity/freshness.

SCD41 T/RH may be compared with TP357 to learn placement/offset behavior, but must not silently replace TP357 as the authoritative inside T/RH source.

### Xiaomi intake sensor

Signals:

- intake/outside temperature;
- intake/outside relative humidity;
- freshness/battery diagnostics.

This sensor describes the air available to the exhaust-driven exchange process and is therefore essential for deciding whether ventilation is likely to improve temperature or moisture conditions.

### DS3231

Signals/context:

- UTC wall-clock time;
- trusted/untrusted RTC state;
- local Europe/Warsaw schedule after timezone conversion;
- day/night and light-schedule phase.

### RF433 controller evidence

For every actuator transition record:

- requested semantic actuator;
- requested state;
- RF code/profile;
- command timestamp;
- TX queued/started/completed evidence;
- whether the action was safety-, schedule-, rule-, test- or operator-driven.

Local RF TX completion is transport evidence only and is not physical load acknowledgement.

### Shelly Plug S Gen3 power feedback

Reference address from the Local Agent host:

`http://192.168.0.16`

Available measurements:

- relay output state;
- active power `apower`;
- mains voltage;
- current;
- accumulated energy;
- Shelly internal temperature.

Shelly is upstream of the current growbox power strip and therefore measures total strip power. Characteristic before/after power deltas let individual RF loads be identified even when other constant loads remain on the strip.

## Derived environmental quantities

Compute these from validated fresh measurements and retain source/age metadata.

### Moisture metrics

From temperature and RH derive at least:

- dew point;
- absolute humidity (g/m3) or an equivalent moisture-content representation;
- air VPD from inside T/RH.

For ventilation decisions prefer moisture-content comparison (`inside absolute humidity` versus `intake absolute humidity`) over raw RH comparison. Relative humidity alone can be misleading when inside and intake temperatures differ.

Without a leaf-temperature sensor, any VPD is air-based VPD; do not label it as directly measured leaf VPD.

### Inside/intake gradients

Calculate:

- `inside_T - intake_T`;
- `inside_RH - intake_RH` for diagnostics;
- `inside_absolute_humidity - intake_absolute_humidity` as the preferred moisture-exchange gradient.

These gradients describe the direction in which forced air exchange is likely to push the growbox before the fan is activated.

### Time derivatives and trends

Over bounded windows calculate robust slopes such as:

- `dT/dt`;
- `dRH/dt`;
- `dAbsoluteHumidity/dt`;
- `dCO2/dt`.

Use robust regression/median slope or another outlier-resistant estimator rather than a two-sample difference when sufficient samples are available.

Store window length, sample count, missing-data fraction and confidence with each slope.

## Actuator-effect inference

The system can perform simple system identification from controlled actuator transitions.

### Exhaust fan

For a clean `fan OFF -> fan ON -> fan OFF` observation, record baseline OFF slopes before activation and ON slopes after a settling/response-delay period.

Estimate fan-attributable effects as approximately:

`fan_effect(variable) = slope_ON(variable) - slope_OFF_baseline(variable)`

Track at least:

- temperature effect in degC/min;
- absolute-humidity effect in g/m3/min;
- CO2 effect in ppm/min;
- response delay;
- approximate time constant/settling behavior;
- confidence and confounders.

For CO2, this gives indirect information about effective intake CO2. Initially report the observable effect (`CO2 rises/falls by X ppm/min under fan`) rather than inventing an exact outside ppm value.

A later well-mixed model may estimate effective intake CO2 and air-change rate when the data are identifiable:

`dC_inside/dt ~= ACH * (C_intake - C_inside) + biological_source_sink`

Biological uptake/respiration, mixing, sensor lag and simultaneous actuator changes must be treated as confounders.

### Lamp

From clean lamp transitions with fan/humidifier stable, learn:

- physical power signature from Shelly;
- immediate electrical start/steady behavior if visible;
- change in inside temperature slope after lamp ON/OFF;
- approximate thermal response delay and heat-load contribution.

This can later help predict whether scheduled lighting is likely to approach the thermal cutoff before it actually reaches it. It must never weaken the hard 28 C trip rule.

### Humidifier

From clean humidifier transitions with fan/lamp state recorded, learn:

- physical power signature from Shelly;
- absolute-humidity increase rate;
- RH response rate;
- response delay and saturation behavior;
- effect persistence after OFF.

This supports predictive run-time estimates and degraded-performance detection.

## Shelly physical-state inference

The calibrated power-feedback path is:

`requested state -> RF command -> wait/settle -> Shelly power delta -> physical-state confidence`

Use both ON and OFF transitions. A matching positive ON delta and matching negative OFF delta provide much stronger physical evidence than a single reading.

Maintain calibrated distributions/ranges rather than one exact wattage constant. Account for mains-voltage variation and normal device variation.

Possible state-confidence outcomes:

- `confirmed_on` / `confirmed_off`: expected power transition observed within calibrated tolerance;
- `probable`: transition is directionally correct but lower confidence;
- `ambiguous`: another load changed or baseline was unstable;
- `failed_transition`: RF command completed but expected power change did not occur;
- `unexpected_load`: total power changed in a way not explained by the requested actuator states.

Do not use Shelly total power alone to identify simultaneous uncontrolled changes unless the combination is uniquely supported by calibrated signatures.

## Fault and degradation signals available without new hardware

Using existing sensors and Shelly, detect or score:

- RF command apparently ineffective (TX complete, no expected power delta);
- actuator stuck ON (OFF requested, expected negative delta absent);
- actuator unexpectedly ON/OFF from total power signature;
- lamp electrical power drift over time;
- fan electrical power drift and/or declining climate response despite similar power;
- humidifier power present but weak moisture response (empty tank, blocked output, degraded transducer or environmental limitation);
- fan power present but weak T/moisture/CO2 response (airflow obstruction, tent/intake topology change, poor mixing);
- abnormal total power not explained by known actuator combinations;
- mains-voltage correlation with actuator power;
- persistent TP357 versus SCD41 T/RH offset changes that may indicate sensor relocation/degradation;
- stale, invalid or contradictory sensor streams.

Electrical power proves load behavior better than RF transport evidence, but it still does not directly prove airflow, light output or mist output. Combine electrical and environmental response when possible.

## Context and confounders to log

Every actuator-effect learning window should include:

- monotonic and UTC timestamps;
- local Europe/Warsaw schedule phase;
- lamp requested/effective state;
- fan requested/effective state;
- humidifier requested/effective state;
- RF TX evidence;
- Shelly power/voltage/current before and after transition;
- TP357 T/RH and freshness;
- SCD41 CO2 plus diagnostic T/RH and freshness;
- Xiaomi intake T/RH and freshness;
- derived VPD, dew point and absolute humidity;
- baseline slopes before the action;
- post-action slopes;
- response delay/settling interval;
- any simultaneous transition or missing/stale input;
- confidence and reason for accepting/rejecting the window.

Reject or mark ambiguous windows where several actuators change together unless that combination is the explicit experiment.

## Useful higher-level quantities for later optimization

Once enough clean observations exist, derive:

- fan cooling effectiveness versus inside/intake temperature gradient;
- fan drying effectiveness versus inside/intake moisture gradient;
- fan CO2 replenishment effectiveness versus current inside CO2 and light phase;
- approximate ventilation delay/time constant;
- lamp heat contribution and thermal inertia;
- humidifier moisture contribution and persistence;
- energy used per useful climate correction;
- time-to-target estimates;
- time-to-safety-limit estimates;
- actuator degradation trends over days/weeks.

These are strong later ML features because they represent what the hardware actually did, not just what the controller requested.

## Control use order

1. Hard deterministic safety remains authoritative.
2. Freshness/validity checks determine whether a signal is usable.
3. Direct physical gradients determine whether an actuator is plausibly beneficial.
4. Calibrated/learned actuator-effect estimates may refine normal deterministic arbitration.
5. ML consumes the same observations in shadow/research mode until explicitly qualified.

Examples:

- thermal trip: lamp OFF + fan ON regardless of learned fan effectiveness;
- high humidity: ventilation only if intake moisture content or measured historical fan response indicates benefit, unless a higher-priority safety rule overrides;
- low daytime CO2: request ventilation only when safe and observed/predicted fan exchange is likely to improve CO2; if effectiveness is unknown, use a bounded supervised exploration pulse rather than blind periodic ventilation;
- all controlled variables acceptable: default exhaust fan OFF.

## Staged implementation

### Now / qualification phase

- keep automatic physical outputs fake-locked until existing gates authorize them;
- log/compute derived environmental metrics;
- retain Shelly as independent test feedback;
- require Shelly power confirmation in supervised RF role-routing and closed-loop evidence where available;
- collect clean actuator response windows;
- store confidence and confounder metadata.

### First supervised closed-loop phase

- use Shelly signatures to confirm expected physical transitions and flag faults;
- collect fan/lamp/humidifier response slopes;
- use direct intake moisture/temperature gradients for deterministic ventilation eligibility;
- keep learned response models advisory until sufficient repeatability is demonstrated.

### Later adaptive/ML phase

- feed observed actuator effects, gradients, slopes, response delays, power signatures and confidence into the feature pipeline;
- evaluate predictive control offline/shadow first;
- only promote a learned decision path after deterministic safety, replay tests and supervised hardware validation remain intact.

## Safety boundary

No inference in this document may bypass or weaken:

- authoritative TP357 thermal safety;
- lamp trip/recovery hysteresis;
- sensor freshness checks;
- actuator dwell/chatter protection;
- explicit real-output authorization gates;
- master-cutoff safety policy.

A learned or inferred effect can improve normal decisions; it cannot overrule a hard safety condition.
