#pragma once

#include "climate/output/OutputTransport.h"
#include "climate/runtime/diagnostics/RfDiagnostics.h"

namespace growbox::app::climate_io::runtime {

class MaintenanceRfTransport final : public ::growbox::app::output::OutputTransport {
public:
  explicit MaintenanceRfTransport(RfDiagnostics& diagnostics) noexcept
      : diagnostics_(diagnostics) {}

  ::growbox::app::output::TxResult
  send(const ::growbox::app::output::OutputCommand& command) noexcept override;

private:
  RfDiagnostics& diagnostics_;
};

} // namespace growbox::app::climate_io::runtime
