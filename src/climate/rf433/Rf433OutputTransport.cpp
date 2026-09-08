#include "climate/rf433/Rf433OutputTransport.h"

#include "climate/rf433/ClimateRf433EndpointRegistry.h"

namespace growbox::app::climate_io::rf433 {

::growbox::app::output::TxResult
Rf433OutputTransport::send(const ::growbox::app::output::OutputCommand& command) noexcept {
  using ::growbox::app::output::BinaryOutputState;
  using ::growbox::app::output::TransportError;
  using ::growbox::app::output::TransportStatus;

  switch (command.state) {
  case BinaryOutputState::Off:
  case BinaryOutputState::On:
    break;
  default:
    return {TransportStatus::Failed, TransportError::InvalidCommand};
  }

  const auto* binding = findClimateRf433Endpoint(command.endpoint);
  if (binding == nullptr || binding->hardware == nullptr) {
    return {TransportStatus::Failed, TransportError::InvalidEndpoint};
  }

  const FrameConfig& frame =
      command.state == BinaryOutputState::On ? binding->hardware->on : binding->hardware->off;
  if (!sender_.transmitFrame(frame)) {
    return {TransportStatus::Failed, TransportError::IoFailure};
  }
  return {TransportStatus::Completed, TransportError::None};
}

} // namespace growbox::app::climate_io::rf433
