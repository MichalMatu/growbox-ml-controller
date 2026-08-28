from pathlib import Path
from textwrap import dedent

ROOT = Path.cwd()


def write(path: str, content: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dedent(content).lstrip(), encoding="utf-8")


write(
    "src/climate/ClimateIoAdapters.h",
    r'''
    #pragma once

    #include "climate/ClimateControlLoop.h"

    #include <cstdint>

    namespace growbox::app::climate_io {

    struct ClimateInputSnapshot {
      ::growbox::climate::ClimateMeasurements measurements{};
      ::growbox::climate::HumidityControlMode humidity_control_mode =
          ::growbox::climate::HumidityControlMode::Rh;
      ::growbox::climate::ClimateTargets targets{};
      ::growbox::climate::ClimateSchedule schedule{};
      ::growbox::climate::ClimateCapabilities capabilities{};
      std::uint64_t sensor_timeout_ms = ::growbox::climate::kDefaultSensorTimeoutMs;
    };

    class ClimateSnapshotProvider {
    public:
      virtual ~ClimateSnapshotProvider() = default;
      virtual bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept = 0;
    };

    enum class ClimateActuatorRole : std::uint8_t {
      Heater = 0U,
      Cooler,
      ExhaustFan,
      Humidifier,
      Dehumidifier,
      Co2Doser,
    };

    class ClimateRoleDriver {
    public:
      virtual ~ClimateRoleDriver() = default;
      virtual bool apply(ClimateActuatorRole role, float level,
                         std::uint64_t monotonic_ms) noexcept = 0;
    };

    class ClimateInputAdapter final : public ::growbox::climate::ClimateInputSource {
    public:
      explicit ClimateInputAdapter(ClimateSnapshotProvider& provider) noexcept : provider_(provider) {}

      bool sample(std::uint64_t monotonic_ms,
                  ::growbox::climate::ClimateControllerInput& input) noexcept override;

    private:
      ClimateSnapshotProvider& provider_;
    };

    class ClimateActuatorAdapter final : public ::growbox::climate::ClimateActuatorSink {
    public:
      explicit ClimateActuatorAdapter(ClimateRoleDriver& driver) noexcept : driver_(driver) {}

      bool apply(const ::growbox::climate::ClimatePolicyRequest& request,
                 std::uint64_t monotonic_ms) noexcept override;

    private:
      ClimateRoleDriver& driver_;
    };

    } // namespace growbox::app::climate_io
    ''',
)

write(
    "src/climate/ClimateIoAdapters.cpp",
    r'''
    #include "climate/ClimateIoAdapters.h"

    namespace growbox::app::climate_io {

    bool ClimateInputAdapter::sample(
        std::uint64_t monotonic_ms,
        ::growbox::climate::ClimateControllerInput& input) noexcept {
      ClimateInputSnapshot snapshot{};
      if (!provider_.snapshot(monotonic_ms, snapshot)) {
        input = {};
        return false;
      }

      input = {};
      input.state.measurements = snapshot.measurements;
      input.humidity_control_mode = snapshot.humidity_control_mode;
      input.targets = snapshot.targets;
      input.schedule = snapshot.schedule;
      input.capabilities = snapshot.capabilities;
      input.sensor_timeout_ms = snapshot.sensor_timeout_ms;
      return true;
    }

    bool ClimateActuatorAdapter::apply(
        const ::growbox::climate::ClimatePolicyRequest& request,
        std::uint64_t monotonic_ms) noexcept {
      bool all_applied = true;
      const auto apply_role = [this, monotonic_ms, &all_applied](ClimateActuatorRole role,
                                                                 float level) noexcept {
        const bool applied = driver_.apply(role, level, monotonic_ms);
        all_applied = applied && all_applied;
      };

      apply_role(ClimateActuatorRole::Heater, request.heater);
      apply_role(ClimateActuatorRole::Cooler, request.cooler);
      apply_role(ClimateActuatorRole::ExhaustFan, request.exhaust_fan);
      apply_role(ClimateActuatorRole::Humidifier, request.humidifier);
      apply_role(ClimateActuatorRole::Dehumidifier, request.dehumidifier);
      apply_role(ClimateActuatorRole::Co2Doser, request.co2_doser);
      return all_applied;
    }

    } // namespace growbox::app::climate_io
    ''',
)

write(
    "test/test_climate_io_adapters/test_main.cpp",
    r'''
    #include "climate/ClimateIoAdapters.h"

    #include <array>
    #include <cassert>
    #include <cmath>
    #include <cstddef>
    #include <cstdint>
    #include <vector>

    using namespace growbox::app::climate_io;
    using namespace growbox::climate;

    namespace {

    bool near(float left, float right, float tolerance = 1.0e-6F) {
      return std::fabs(left - right) <= tolerance;
    }

    class FakeSnapshotProvider final : public ClimateSnapshotProvider {
    public:
      ClimateInputSnapshot value{};
      bool available = true;
      std::size_t calls = 0U;
      std::uint64_t last_monotonic_ms = 0U;

      bool snapshot(std::uint64_t monotonic_ms, ClimateInputSnapshot& output) noexcept override {
        ++calls;
        last_monotonic_ms = monotonic_ms;
        if (!available) {
          return false;
        }
        output = value;
        return true;
      }
    };

    struct RoleCall {
      ClimateActuatorRole role = ClimateActuatorRole::Heater;
      float level = 0.0F;
      std::uint64_t monotonic_ms = 0U;
    };

    class FakeRoleDriver final : public ClimateRoleDriver {
    public:
      std::vector<RoleCall> calls{};
      ClimateActuatorRole failing_role = ClimateActuatorRole::Heater;
      bool fail_enabled = false;

      bool apply(ClimateActuatorRole role, float level,
                 std::uint64_t monotonic_ms) noexcept override {
        calls.push_back(RoleCall{role, level, monotonic_ms});
        return !(fail_enabled && role == failing_role);
      }
    };

    ClimateInputSnapshot populatedSnapshot() {
      ClimateInputSnapshot snapshot{};
      snapshot.measurements.air_temperature_c = {23.5F, true, 111U};
      snapshot.measurements.relative_humidity_pct = {61.0F, true, 222U};
      snapshot.measurements.co2_ppm = {880.0F, true, 333U};
      snapshot.measurements.outside_temperature_c = {12.0F, true, 444U};
      snapshot.measurements.outside_humidity_pct = {52.0F, true, 555U};
      snapshot.humidity_control_mode = HumidityControlMode::Vpd;
      snapshot.targets.air_temperature_c = 24.0F;
      snapshot.targets.relative_humidity_pct = 60.0F;
      snapshot.targets.air_vpd_kpa = 1.15F;
      snapshot.targets.co2_enabled = true;
      snapshot.targets.co2_ppm = 950.0F;
      snapshot.schedule.light_level = 0.75F;
      snapshot.capabilities.heater = true;
      snapshot.capabilities.cooler = false;
      snapshot.capabilities.exhaust_fan = true;
      snapshot.capabilities.humidifier = true;
      snapshot.capabilities.dehumidifier = false;
      snapshot.capabilities.co2_doser = true;
      snapshot.sensor_timeout_ms = 45'000U;
      return snapshot;
    }

    void testInputAdapterMapsRuntimeObservableSnapshot() {
      FakeSnapshotProvider provider{};
      provider.value = populatedSnapshot();
      ClimateInputAdapter adapter(provider);
      ClimateControllerInput input{};
      input.previous.heater = 1.0F;
      input.estimated_effective.heater = 1.0F;

      assert(adapter.sample(123'456U, input));
      assert(provider.calls == 1U);
      assert(provider.last_monotonic_ms == 123'456U);
      assert(near(input.state.measurements.air_temperature_c.value, 23.5F));
      assert(input.state.measurements.air_temperature_c.valid);
      assert(input.state.measurements.air_temperature_c.age_ms == 111U);
      assert(near(input.state.measurements.relative_humidity_pct.value, 61.0F));
      assert(near(input.state.measurements.co2_ppm.value, 880.0F));
      assert(near(input.state.measurements.outside_temperature_c.value, 12.0F));
      assert(near(input.state.measurements.outside_humidity_pct.value, 52.0F));
      assert(input.humidity_control_mode == HumidityControlMode::Vpd);
      assert(near(input.targets.air_temperature_c, 24.0F));
      assert(near(input.targets.air_vpd_kpa, 1.15F));
      assert(input.targets.co2_enabled);
      assert(near(input.targets.co2_ppm, 950.0F));
      assert(near(input.schedule.light_level, 0.75F));
      assert(input.capabilities.heater);
      assert(!input.capabilities.cooler);
      assert(input.capabilities.exhaust_fan);
      assert(input.capabilities.humidifier);
      assert(!input.capabilities.dehumidifier);
      assert(input.capabilities.co2_doser);
      assert(input.sensor_timeout_ms == 45'000U);

      // Previous and effective actions are owned by ClimateControlLoop/ClimateRuntimeController,
      // not by a sensor/configuration provider.
      assert(near(input.previous.heater, 0.0F));
      assert(near(input.estimated_effective.heater, 0.0F));
    }

    void testInputAdapterClearsStaleStateOnProviderFailure() {
      FakeSnapshotProvider provider{};
      provider.available = false;
      ClimateInputAdapter adapter(provider);
      ClimateControllerInput input{};
      input.state.measurements.air_temperature_c = {99.0F, true, 0U};
      input.capabilities.heater = true;

      assert(!adapter.sample(8'000U, input));
      assert(!input.state.measurements.air_temperature_c.valid);
      assert(!input.capabilities.heater);
      assert(input.state.measurements.air_temperature_c.age_ms == kUnknownMeasurementAgeMs);
    }

    void testActuatorAdapterMapsEverySemanticRoleExactlyOnce() {
      FakeRoleDriver driver{};
      ClimateActuatorAdapter adapter(driver);
      ClimatePolicyRequest request{};
      request.heater = 0.1F;
      request.cooler = 0.2F;
      request.exhaust_fan = 0.3F;
      request.humidifier = 0.4F;
      request.dehumidifier = 0.5F;
      request.co2_doser = 0.6F;

      assert(adapter.apply(request, 77'000U));
      assert(driver.calls.size() == 6U);
      constexpr std::array<ClimateActuatorRole, 6U> expected_roles{
          ClimateActuatorRole::Heater,       ClimateActuatorRole::Cooler,
          ClimateActuatorRole::ExhaustFan,   ClimateActuatorRole::Humidifier,
          ClimateActuatorRole::Dehumidifier, ClimateActuatorRole::Co2Doser,
      };
      constexpr std::array<float, 6U> expected_levels{0.1F, 0.2F, 0.3F, 0.4F, 0.5F, 0.6F};
      for (std::size_t index = 0U; index < expected_roles.size(); ++index) {
        assert(driver.calls[index].role == expected_roles[index]);
        assert(near(driver.calls[index].level, expected_levels[index]));
        assert(driver.calls[index].monotonic_ms == 77'000U);
      }
    }

    void testActuatorAdapterReportsPartialFailureButStillVisitsAllRoles() {
      FakeRoleDriver driver{};
      driver.fail_enabled = true;
      driver.failing_role = ClimateActuatorRole::ExhaustFan;
      ClimateActuatorAdapter adapter(driver);
      ClimatePolicyRequest request{};
      request.heater = 0.2F;
      request.exhaust_fan = 0.8F;
      request.co2_doser = 0.4F;

      assert(!adapter.apply(request, 91'000U));
      assert(driver.calls.size() == 6U);
      assert(driver.calls[2].role == ClimateActuatorRole::ExhaustFan);
      assert(driver.calls[5].role == ClimateActuatorRole::Co2Doser);
    }

    } // namespace

    int main() {
      testInputAdapterMapsRuntimeObservableSnapshot();
      testInputAdapterClearsStaleStateOnProviderFailure();
      testActuatorAdapterMapsEverySemanticRoleExactlyOnce();
      testActuatorAdapterReportsPartialFailureButStillVisitsAllRoles();
      return 0;
    }
    ''',
)

src_cmake = ROOT / "src" / "CMakeLists.txt"
src_text = src_cmake.read_text(encoding="utf-8")
needle = '    "main.cpp"\n'
assert needle in src_text
assert '"climate/ClimateIoAdapters.cpp"' not in src_text
src_cmake.write_text(src_text.replace(needle, needle + '    "climate/ClimateIoAdapters.cpp"\n', 1), encoding="utf-8")

host_cmake = ROOT / "test" / "host" / "CMakeLists.txt"
host_text = host_cmake.read_text(encoding="utf-8")
assert "climate_io_adapter_tests" not in host_text
insert = dedent(
    r'''

    add_executable(
      climate_io_adapter_tests
      "${PROJECT_ROOT}/test/test_climate_io_adapters/test_main.cpp"
      "${PROJECT_ROOT}/src/climate/ClimateIoAdapters.cpp"
    )
    target_include_directories(
      climate_io_adapter_tests
      PRIVATE
        "${PROJECT_ROOT}/src"
        "${PROJECT_ROOT}/lib/environment_control/src"
    )
    target_compile_features(climate_io_adapter_tests PRIVATE cxx_std_17)
    target_compile_options(climate_io_adapter_tests PRIVATE -Wall -Wextra -Wpedantic)
    ''')
marker = "\nif(UNIX)\n"
assert marker in host_text
host_text = host_text.replace(marker, insert + marker, 1)
link_marker = "  target_link_libraries(climate_virtual_hil_tests PRIVATE m)\n"
assert link_marker in host_text
host_text = host_text.replace(
    link_marker,
    link_marker + "  target_link_libraries(climate_io_adapter_tests PRIVATE m)\n",
    1,
)
test_marker = "add_test(NAME climate_virtual_hil_tests COMMAND climate_virtual_hil_tests)"
assert test_marker in host_text
host_text = host_text.replace(
    test_marker,
    test_marker + "\nadd_test(NAME climate_io_adapter_tests COMMAND climate_io_adapter_tests)",
    1,
)
host_cmake.write_text(host_text, encoding="utf-8")

write(
    "docs/CURRENT_STATUS.md",
    r'''
    # Current controller status

    Date: 2026-08-28  
    Development branch: `mvp/environment-controller`

    This document is the short source of truth for the current climate-controller product path.
    Historical simulator, browser-contract and convergence documents remain in the repository for
    reproducibility, but they must not be read as the current runtime architecture.

    ## Current authoritative climate path

    Climate-v6 is the active migration target for new controller work:

    - schema v6 / contract `climate-mvp-v1`;
    - 44 runtime-observable input features;
    - 6 semantic ML-controlled outputs: heater, cooler, exhaust fan, humidifier, dehumidifier and CO2 doser;
    - bounded MLP shape `44 -> 32 -> 32 -> 6` retained as the compatibility/research model shape;
    - `ClimateRulePolicy` remains authoritative for production-oriented runtime work;
    - `MlShadow` evaluates ML without changing the applied command;
    - `MlActive` exists only as an explicit research opt-in and is not qualified for real growbox actuation;
    - deterministic arbitration and safety remain authoritative over every policy proposal;
    - the effective-actuator estimator advances only from the final applied semantic command.

    The scientific rationale and rejected alternatives are frozen in `docs/ML_DECISION_REPORT.md`.

    ## Runtime implementation completed

    The C++ climate-v6 runtime now includes:

    - `ClimateFeatureEncoder`;
    - `ClimateRuntimeController` with Rule / ML_SHADOW / ML_ACTIVE modes;
    - trend and effective-actuator state estimation;
    - Python/C++ golden parity;
    - validated runtime trace schema and NDJSON recording;
    - deterministic trace replay and counterfactual ML evaluation;
    - `ClimateControlLoop` with fail-closed input handling, best-effort OFF on actuator rejection and
      an actuator fault latch;
    - multi-step virtual HIL tests covering state, stale/unavailable inputs, shadow ML, safety
      transitions and rejected actuator commands.

    These climate-v6 sources are compiled by the real ESP-IDF ESP32-S3 build. CI and the local
    framework baseline are ESP-IDF v5.5.4.

    ## New hardware-neutral I/O seam

    `src/climate/ClimateIoAdapters.*` is the application-side boundary for future hardware work.
    It deliberately does not contain SCD41, BLE, RTC, GPIO, relay, PWM or networking code.

    The input side maps a coherent runtime-observable snapshot into `ClimateInputSource`. The output
    side maps the six semantic role levels from `ClimateActuatorSink` to a role driver. This keeps
    sensor libraries and physical endpoints replaceable without changing the climate controller.

    `ClimateControlLoop` owns confirmed previous actions. `ClimateRuntimeController` owns trends and
    estimated effective actions. Hardware providers must not invent or duplicate those states.

    ## What is not integrated yet

    The current `src/main.cpp` still runs the preserved legacy simulator/serial demonstration through
    `EnvironmentController`. Climate-v6 is compiled and host/HIL tested but is not yet the default
    `app_main()` execution path and does not drive physical GPIO loads.

    Planned first hardware set remains:

    - inside: SCD41 for air temperature, RH and CO2;
    - outside: an external BLE temperature/RH sensor, exact model not frozen;
    - system time: battery/supercapacitor-backed RTC, exact part not frozen;
    - physical actuator endpoints: not frozen yet.

    See `docs/MVP_HARDWARE_SENSOR_SET.md`.

    ## Next steps

    1. Keep the legacy demo intact while proving the new adapter seam in host and ESP-IDF builds.
    2. Add concrete SCD41 / BLE / RTC providers behind the input adapter once parts and libraries are frozen.
    3. Add concrete semantic role drivers behind the actuator adapter.
    4. Bring up real hardware in Rule mode first.
    5. Run ML only in `MlShadow` while collecting real traces.
    6. Re-qualify any ML candidate from real data before considering active ML actuation.
    ''',
)

architecture = dedent(
    r'''
    # Architecture

    Current status: [CURRENT_STATUS.md](CURRENT_STATUS.md).  
    Hardware plan: [MVP_HARDWARE_SENSOR_SET.md](MVP_HARDWARE_SENSOR_SET.md).  
    Scientific ML decision record: [ML_DECISION_REPORT.md](ML_DECISION_REPORT.md).

    ## Design rule

    The climate controller is independent from sensor libraries and physical actuator endpoints.
    Hardware produces semantic measurements and consumes semantic role commands. The controller does
    not know whether a value came from I2C, BLE, MQTT, a simulator or a recorded trace.

    ## Current climate-v6 path

    ```text
    sensor/config/time providers
               |
               v
      ClimateInputSnapshot
               |
               v
      ClimateInputAdapter
               |
               v
       ClimateControlLoop
               |
               v
    ClimateRuntimeController
       |               |
       | Rule          | optional ML
       |               | (shadow by default)
       +-------+-------+
               |
          arbitration
               |
      deterministic safety
               |
               v
       semantic safe command
               |
               v
     ClimateActuatorAdapter
               |
               v
       semantic role driver
               |
               v
    GPIO / relay / PWM / remote device later
    ```

    `ClimateControlLoop` is the I/O-facing safety boundary. If an input provider fails, it passes an
    invalid/default input into the runtime so safety resolves to OFF. If an actuator command is
    rejected, it attempts an all-OFF command, resets unconfirmed runtime actuator state, and latches
    an actuator fault if OFF also fails.

    The loop owns the confirmed previous-applied action. The runtime owns trend estimation and the
    effective-actuator estimator. A sensor/configuration adapter must not duplicate either state.

    ## Policy modes

    - `Rule` — authoritative default and current production recommendation.
    - `MlShadow` — ML is evaluated and recorded but Rule remains authoritative.
    - `MlActive` — explicit research-only opt-in; currently not qualified for real actuation.

    Arbitration and deterministic safety are applied independently of which policy produced a
    proposal. ML never bypasses safety.

    ## Climate-v6 contract

    `schemas/environment-controller.v6.json` / generated `ClimateContract.h` define schema v6,
    contract `climate-mvp-v1`, 44 features and 6 ML-controlled semantic outputs. Inputs contain only
    runtime-observable state: measurements with validity/freshness, targets, schedule level, trends,
    previous applied actions, estimated effective actions and role capabilities.

    The older root `schemas/environment-controller.json` and legacy `EnvironmentController` demo are
    retained during migration because the serial demo/browser history still depends on them. They are
    not the architecture for new climate-v6 runtime work.

    ## Application I/O boundary

    `src/climate/ClimateIoAdapters.*` provides the narrow application seam:

    - `ClimateSnapshotProvider` produces measurements, target/configuration state, schedule level,
      capabilities and the sensor timeout;
    - `ClimateInputAdapter` maps that snapshot to `ClimateInputSource`;
    - `ClimateRoleDriver` accepts one normalized semantic role command at a time;
    - `ClimateActuatorAdapter` maps all six `ClimatePolicyRequest` outputs to those roles and reports
      failure if any role application fails.

    No concrete SCD41/BLE/RTC/GPIO dependency belongs in the portable controller library.

    ## Verification layers

    - Python scientific/simulator tests;
    - Python/C++ golden runtime parity;
    - portable C++ runtime tests;
    - `ClimateControlLoop` failure tests;
    - multi-step virtual HIL tests;
    - application I/O adapter mapping tests;
    - real ESP-IDF ESP32-S3 compile gate;
    - GitHub Actions CI using ESP-IDF v5.5.4.

    Simulator or virtual-HIL PASS establishes software behavior, not real hardware readiness.

    ## Preserved legacy demo

    `src/main.cpp` currently still drives `DummyEnvironmentSimulator` through the older
    `EnvironmentController` and bounded UART/NDJSON demo protocol. This is intentionally preserved
    until the climate-v6 application path has concrete input/output providers. Do not silently mix
    the two contracts or treat the legacy demo as the current ML runtime architecture.
    ''').lstrip()
(ROOT / "docs" / "ARCHITECTURE.md").write_text(architecture, encoding="utf-8")

readme = ROOT / "README.md"
readme_text = readme.read_text(encoding="utf-8")n