#include "climate/runtime/core/RealInputRuntimeComposition.h"

#include "climate/output/OutputBindings.h"
#include "climate/runtime/RuntimeBuildConfig.h"

#include <array>

namespace growbox::app::climate_io::runtime {
namespace {

storage::Stage27TelemetryLogger::Config makeStorageConfig() noexcept {
  storage::Stage27TelemetryLogger::Config config{};
  config.sd_pins = {runtime_config::kSdMosiGpio, runtime_config::kSdMisoGpio,
                    runtime_config::kSdSclkGpio, runtime_config::kSdCsGpio,
                    runtime_config::kSdPowerGpio};
  config.sd_enabled = runtime_config::kStage27SdEnabled;
  config.flash_fallback_enabled = runtime_config::kStage27FlashFallbackEnabled;
  config.sd_cmd0_precondition = runtime_config::kSdCmd0Precondition;
  return config;
}

RfDiagnosticsConfig makeRfDiagnosticsConfig() noexcept {
  RfDiagnosticsConfig config{};
  config.enabled = runtime_config::kRf433LoopbackEnabled;
  config.passive_capture = runtime_config::kRf433RemoteCaptureEnabled;
  config.tx_gpio = runtime_config::kRf433TxGpio;
  config.rx_gpio = runtime_config::kRf433RxGpio;
  return config;
}

output::OutputSupervisorResolverConfig
makeRuntimeSupervisorConfig(output::BinaryActuatorPolicy& exhaust_policy,
                            output::BinaryActuatorPolicy& humidifier_policy) noexcept {
  output::OutputSupervisorResolverConfig config{};
  config.endpoints[0] = {stage28d::kScheduledLightEndpoint, nullptr};
  config.endpoints[1] = {stage28d::kExhaustFanEndpoint, &exhaust_policy};
  config.endpoints[2] = {stage28d::kHumidifierEndpoint, &humidifier_policy};
  config.count = 3U;
  return config;
}

} // namespace

RuntimeIoOwner::RuntimeIoOwner() noexcept
    : storage_config_(makeStorageConfig()), storage_logger_(storage_config_),
      rf_diagnostics_config_(makeRfDiagnosticsConfig()),
      rf_radio_(rf433::Rf433RmtLoopback::Config{rf_diagnostics_config_.tx_gpio,
                                                rf_diagnostics_config_.rx_gpio}),
      rf_diagnostics_(rf_diagnostics_config_, rf_radio_), rf_frame_sender_(rf_radio_),
      rf_output_transport_(rf_frame_sender_) {}

bool RuntimeIoOwner::beginRf() noexcept {
  const bool radio_ready = rf_diagnostics_config_.enabled && rf_radio_.begin();
  return rf_diagnostics_.begin(radio_ready);
}

const output::OutputPolicyConfig& safeOutputPolicy() noexcept {
  static const output::OutputPolicyConfig policy = stage28d::makeOutputPolicyConfig();
  return policy;
}

RuntimePersistenceOwner::RuntimePersistenceOwner() noexcept
    : persistence_store_(nvs_backend_, safeOutputPolicy()), persistence_(persistence_store_) {}

void RuntimePersistenceOwner::initialize() noexcept {
  static constexpr std::array<output::OutputEndpointId, output::kOutputEndpointCapacity>
      kShadowOutputEndpoints{stage28d::kExhaustFanEndpoint, stage28d::kScheduledLightEndpoint,
                             stage28d::kHumidifierEndpoint};
  state_store_ready_ =
      state_store_.configure(kShadowOutputEndpoints, kShadowOutputEndpoints.size());
  init_result_ = state_store_ready_ ? persistence_.initialize(state_store_)
                                    : output::OutputPersistenceCoordinatorInitResult{};
}

const output::OutputPolicyConfig& RuntimePersistenceOwner::policy() const noexcept {
  return persistence_.valid() ? persistence_.policy() : safeOutputPolicy();
}

RuntimeOutputOwner::RuntimeOutputOwner(output::OutputTransport& real_transport,
                                       RuntimeExecutionStatus& execution_status,
                                       RfDiagnostics& diagnostics,
                                       const output::OutputPolicyConfig& policy,
                                       output::OutputStateStore& state_store) noexcept
    : policy_(policy), semantic_output_config_(stage28d::makeClimateSemanticOutputConfig(policy_)),
      exhaust_policy_(stage28d::kExhaustFanBinaryPolicy),
      humidifier_policy_(stage28d::kHumidifierBinaryPolicy),
      supervisor_config_(makeRuntimeSupervisorConfig(exhaust_policy_, humidifier_policy_)),
      supervisor_transport_(real_transport, execution_status), output_lifecycle_(policy_),
      lifecycle_executor_(policy_, output_lifecycle_, supervisor_transport_, state_store,
                          supervisor_config_),
      runtime_lifecycle_(output_lifecycle_, lifecycle_executor_),
      automation_control_(output_lifecycle_, lifecycle_executor_),
      manual_control_(policy_, output_lifecycle_), maintenance_rf_transport_(diagnostics),
      maintenance_control_(policy_, output_lifecycle_, automation_control_, lifecycle_executor_,
                           state_store, supervisor_config_, maintenance_rf_transport_),
      supervisor_resolver_(supervisor_config_),
      supervisor_executor_(supervisor_transport_, state_store, supervisor_config_),
      supervisor_sink_(semantic_output_config_, supervisor_resolver_, supervisor_executor_,
                       state_store) {
  bindings_valid_ = stage28d::validateOutputBindings(semantic_output_config_, policy_) ==
                    stage28d::OutputBindingStatus::Ok;
  valid_ = bindings_valid_ && output_lifecycle_.valid() && lifecycle_executor_.valid() &&
           runtime_lifecycle_.valid() && automation_control_.valid() && manual_control_.valid() &&
           maintenance_control_.valid() && supervisor_sink_.valid();
}

RuntimeControlOwner::RuntimeControlOwner() noexcept
    : runtime_controller_(nullptr, productionRuntimeConfig()) {}

} // namespace growbox::app::climate_io::runtime
