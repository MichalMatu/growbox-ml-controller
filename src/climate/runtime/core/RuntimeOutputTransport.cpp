#include "climate/runtime/core/RuntimeOutputTransport.h"

namespace growbox::app::climate_io::runtime {

output::TxResult RuntimeOutputTransport::send(const output::OutputCommand& command) noexcept {
  if (!execution_status_.transport_available) {
    return {output::TransportStatus::NotAttempted, output::TransportError::Unavailable};
  }

  const auto result = real_transport_.send(command);
  if (result.status == output::TransportStatus::Completed) {
    ++transmit_count_;
  } else {
    ++transmit_error_count_;
  }
  return result;
}

} // namespace growbox::app::climate_io::runtime
