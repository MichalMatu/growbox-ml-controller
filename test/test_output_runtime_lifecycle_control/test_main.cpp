#include "climate/output/lifecycle/OutputRuntimeLifecycleControl.h"
#include "climate/output/supervisor/OutputSupervisorResolver.h"

#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>

namespace output = growbox::app::output;

namespace {

constexpr output::OutputEndpointId kFan = 1U;
constexpr output::OutputEndpointId kLamp = 2U;
constexpr output::OutputEndpointId kHumidifier = 3U;

struct FakeTransport final : output::OutputTransport {
  std::array<output::OutputCommand, 32U> commands{};
  std::size_t count{0U};
  output::OutputEndpointId fail_endpoint{output::kInvalidOutputEndpoint};
  bool fail_always{false};

  output::TxResult send(const output::OutputCommand& command) noexcept override {
    assert(count < commands.size());
    commands[count++] = command;
    if (fail_always && command.endpoint == fail_endpoint) {
      return {output::TransportStatus::Failed, output::TransportError::IoFailure};
    }
    return {output::TransportStatus::Completed, output::TransportError::None};
  }

  void reset() noexcept {
    count = 0U;
    fail_endpoint = output::kInvalidOutputEndpoint;
    fail_always = false;
  }
};

struct Fixture {
  output::OutputPolicyConfig policy{
      output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier)};
  output::OutputStateStore store{};
  output::OutputSupervisorResolverConfig resolver_config{};
  FakeTransport transport{};
  output::OutputSupervisorLifecycle lifecycle;
  output::OutputLifecycleExecutor executor;
  output::OutputRuntimeLifecycleControl control;

  explicit Fixture(output::OutputPolicyConfig custom =
                       output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier))
      : policy(custom), lifecycle(policy),
        executor(policy, lifecycle, transport, store, makeResolverConfig()),
        control(lifecycle, executor) {
    const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{
        kFan, kLamp, kHumidifier};
    assert(store.configure(endpoints, endpoints.size()));
    resolver_config = makeResolverConfig();
    // executor was constructed before store.configure; composition validation
    // therefore must be rebuilt in tests through the alternate fixture helper.
  }

  static output::OutputSupervisorResolverConfig makeResolverConfig() noexcept {
    output::OutputSupervisorResolverConfig config{};
    config.endpoints[0] = {kLamp, nullptr};
    config.endpoints[1] = {kFan, nullptr};
    config.endpoints[2] = {kHumidifier, nullptr};
    config.count = 3U;
    return config;
  }
};

// Construct objects in the same order as production: state store first, then executor.
struct ReadyFixture {
  output::OutputPolicyConfig policy{};
  output::OutputStateStore store{};
  output::OutputSupervisorResolverConfig resolver_config{};
  FakeTransport transport{};
  output::OutputSupervisorLifecycle lifecycle;
  output::OutputLifecycleExecutor executor;
  output::OutputRuntimeLifecycleControl control;

  explicit ReadyFixture(output::OutputPolicyConfig custom =
                            output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier))
      : policy(custom), resolver_config(makeResolverConfig()), lifecycle(policy),
        executor(policy, lifecycle, transport, store, resolver_config),
        control(lifecycle, executor) {
    // This constructor cannot configure store before executor construction. Use create().
  }

  static output::OutputSupervisorResolverConfig makeResolverConfig() noexcept {
    output::OutputSupervisorResolverConfig config{};
    config.endpoints[0] = {kLamp, nullptr};
    config.endpoints[1] = {kFan, nullptr};
    config.endpoints[2] = {kHumidifier, nullptr};
    config.count = 3U;
    return config;
  }
};

struct Harness {
  output::OutputPolicyConfig policy{};
  output::OutputStateStore store{};
  output::OutputSupervisorResolverConfig config{};
  FakeTransport transport{};
  output::OutputSupervisorLifecycle* lifecycle{nullptr};
  output::OutputLifecycleExecutor* executor{nullptr};
  output::OutputRuntimeLifecycleControl* control{nullptr};

  explicit Harness(output::OutputPolicyConfig custom =
                       output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier))
      : policy(custom) {
    const std::array<output::OutputEndpointId, output::kOutputEndpointCapacity> endpoints{
        kFan, kLamp, kHumidifier};
    assert(store.configure(endpoints, endpoints.size()));
    config.endpoints[0] = {kLamp, nullptr};
    config.endpoints[1] = {kFan, nullptr};
    config.endpoints[2] = {kHumidifier, nullptr};
    config.count = 3U;
    lifecycle = new output::OutputSupervisorLifecycle(policy);
    executor = new output::OutputLifecycleExecutor(policy, *lifecycle, transport, store, config);
    control = new output::OutputRuntimeLifecycleControl(*lifecycle, *executor);
    assert(control->valid());
  }

  ~Harness() {
    delete control;
    delete executor;
    delete lifecycle;
  }

  void tickUntilDone(std::uint64_t now = 100U) {
    output::SafetyEnvelope safety{};
    for (unsigned i = 0U; i < 32U && control->transitionActive(); ++i) {
      (void)control->tick(now + i, safety);
    }
    assert(!control->transitionActive());
  }
};

void testBootPlanOwnsSafeInitialization() {
  Harness h;
  output::ScheduleIntent schedule{};
  assert(h.control->beginBoot(100U, schedule));
  assert(h.lifecycle->mode() == output::SupervisorMode::Arming);
  h.tickUntilDone();
  assert(h.control->bootCompleted());
  assert(h.lifecycle->mode() == output::SupervisorMode::Automatic);
  assert(h.transport.count == 3U);
  assert(h.transport.commands[0].endpoint == kLamp);
  assert(h.transport.commands[1].endpoint == kFan);
  assert(h.transport.commands[2].endpoint == kHumidifier);
  for (std::size_t i = 0U; i < h.transport.count; ++i) {
    assert(h.transport.commands[i].state == output::BinaryOutputState::Off);
    assert(h.transport.commands[i].source == output::OutputSource::Lifecycle);
    assert(h.transport.commands[i].reason == output::OutputReason::LifecyclePolicy);
  }
}

void testFailedBootFaultLocks() {
  Harness h;
  h.transport.fail_endpoint = kLamp;
  h.transport.fail_always = true;
  assert(h.control->beginBoot(200U, {}));
  h.tickUntilDone(200U);
  assert(!h.control->bootCompleted());
  assert(h.lifecycle->mode() == output::SupervisorMode::FaultLocked);
  assert(h.transport.count >= 2U);
}

void testRecoveryPartialFailureFailsClosed() {
  auto policy = output::makeSafeDefaultOutputPolicyConfig(kFan, kLamp, kHumidifier);
  policy.max_transition_failures = 2U;
  for (std::size_t i = 0U; i < policy.count; ++i) {
    auto& recovery =
        policy.endpoints[i]
            .lifecycle[output::outputLifecycleEventIndex(output::OutputLifecycleEvent::Recovery)];
    recovery.max_retries = 0U;
  }
  assert(output::validateOutputPolicyConfig(policy) == output::OutputPolicyConfigStatus::Ok);
  Harness h(policy);
  (void)h.lifecycle->apply(output::OutputLifecycleCommand::EnterFault);
  assert(h.lifecycle->mode() == output::SupervisorMode::FaultLocked);
  h.transport.fail_endpoint = kLamp;
  h.transport.fail_always = true;
  assert(h.control->requestRecovery(300U, {}));
  h.tickUntilDone(300U);
  assert(h.lifecycle->mode() == output::SupervisorMode::FaultLocked);
  assert(h.executor->status() == output::OutputLifecycleExecutionStatus::CompletedWithFailures);
}

void testFaultSupersedesPendingBootPlan() {
  Harness h;
  assert(h.control->beginBoot(400U, {}));
  assert(h.executor->active());
  assert(h.control->requestFault(401U, {}));
  assert(h.lifecycle->mode() == output::SupervisorMode::FaultLocked);
  h.tickUntilDone(401U);
  assert(h.transport.count == 3U);
  for (std::size_t i = 0U; i < h.transport.count; ++i) {
    assert(h.transport.commands[i].reason == output::OutputReason::FaultContainment);
  }
}

void testHardSafetyDefersLifecycleButRemainsResolvable() {
  Harness h;
  assert(h.control->beginBoot(500U, {}));

  output::SafetyEnvelope safety{};
  safety.metadata.sequence = 77U;
  safety.metadata.monotonic_ms = 500U;
  safety.metadata.source = output::OutputSource::Safety;
  safety.metadata.reason = output::OutputReason::ThermalSafety;
  assert(output::setSafetyConstraint(safety.endpoints[0], kFan, output::SafetyConstraint::ForceOn,
                                     output::OutputReason::ThermalSafety));

  const auto report = h.control->tick(500U, safety);
  assert(report.status == output::OutputRuntimeLifecycleStatus::SafetyDeferred);
  assert(report.safety_deferred);
  assert(h.transport.count == 0U);
  assert(h.lifecycle->mode() == output::SupervisorMode::Arming);

  output::OutputSupervisorResolver resolver(h.config);
  output::OutputSupervisorCycleInput input{};
  input.mode = h.lifecycle->mode();
  input.monotonic_ms = 500U;
  input.safety = safety;
  output::OutputSupervisorResolution resolution{};
  assert(resolver.resolve(input, h.store, resolution));
  assert(resolution.plan.size == 1U);
  assert(resolution.plan.steps[0].endpoint == kFan);
  assert(resolution.plan.steps[0].state == output::BinaryOutputState::On);
  assert(resolution.plan.steps[0].source == output::OutputSource::Safety);
}

} // namespace

int main() {
  testBootPlanOwnsSafeInitialization();
  testFailedBootFaultLocks();
  testRecoveryPartialFailureFailsClosed();
  testFaultSupersedesPendingBootPlan();
  testHardSafetyDefersLifecycleButRemainsResolvable();
  return 0;
}
