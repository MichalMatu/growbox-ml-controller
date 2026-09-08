#include "climate/runtime/Stage28MaintenanceRfTransport.h"

#include "climate/rf433/ClimateRf433EndpointRegistry.h"

namespace growbox::app::climate_io::runtime {

::growbox::app::output::TxResult
Stage28MaintenanceRfTransport::send(const ::growbox::app::output::OutputCommand& command) noexcept {
  using ::growbox::app::output::BinaryOutputState;
  using ::growbox::app::output::OutputReason;
  using ::growbox::app::output::OutputSource;
  using ::growbox::app::output::TransportError;
  using ::growbox::app::output::TransportStatus;

  if (command.source != OutputSource::Maintenance ||
      command.reason != OutputReason::MaintenanceRequest) {
    return {TransportStatus::Failed, TransportError::InvalidCommand};
  }
  if (command.state != BinaryOutputState::Off && command.state != BinaryOutputState::On) {
    return {TransportStatus::Failed, TransportError::InvalidCommand};
  }
  const auto* binding = rf433::findClimateRf433Endpoint(command.endpoint);
  if (binding == nullptr || binding->hardware == nullptr) {
    return {TransportStatus::Failed, TransportError::InvalidEndpoint};
  }
  if (!diagnostics_.ready()) {
    return {TransportStatus::Failed, TransportError::Unavailable};
  }
  const auto& frame =
      command.state == BinaryOutputState::On ? binding->hardware->on : binding->hardware->off;
  rf433::LoopbackEvidence evidence{};
  if (!diagnostics_.manualTransmit(frame, evidence)) {
    return {TransportStatus::Failed, TransportError::IoFailure};
  }
  return {TransportStatus::Completed, TransportError::None};
}

} // namespace growbox::app::climate_io::runtime
