#pragma once

#include "climate/output/OutputTransport.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

struct RuntimeExecutionStatus final {
  bool transport_available{false};
  bool output_ready{false};
};

class RuntimeOutputTransport final : public output::OutputTransport {
public:
  RuntimeOutputTransport(output::OutputTransport& real_transport,
                         RuntimeExecutionStatus& execution_status) noexcept
      : real_transport_(real_transport), execution_status_(execution_status) {}

  output::TxResult send(const output::OutputCommand& command) noexcept override;

  std::uint32_t transmitCount() const noexcept {
    return transmit_count_;
  }

  std::uint32_t transmitErrorCount() const noexcept {
    return transmit_error_count_;
  }

private:
  output::OutputTransport& real_transport_;
  RuntimeExecutionStatus& execution_status_;
  std::uint32_t transmit_count_{0U};
  std::uint32_t transmit_error_count_{0U};
};

} // namespace growbox::app::climate_io::runtime
