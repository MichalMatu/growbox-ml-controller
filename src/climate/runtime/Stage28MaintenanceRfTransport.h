#pragma once

#include "climate/output/OutputTransport.h"
#include "climate/runtime/Stage28RfDiagnostics.h"

namespace growbox::app::climate_io::runtime {

class Stage28MaintenanceRfTransport final : public ::growbox::app::output::OutputTransport {
public:
  explicit Stage28MaintenanceRfTransport(Stage28RfDiagnostics& diagnostics) noexcept
      : diagnostics_(diagnostics) {}

  ::growbox::app::output::TxResult
  send(const ::growbox::app::output::OutputCommand& command) noexcept override;

private:
  Stage28RfDiagnostics& diagnostics_;
};

} // namespace growbox::app::climate_io::runtime
