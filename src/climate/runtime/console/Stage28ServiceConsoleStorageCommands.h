#pragma once

#include "climate/runtime/console/ServiceConsoleTextSink.h"
#include "climate/runtime/console/Stage28ServiceConsoleCommand.h"

namespace growbox::app::climate_io::storage {
class Stage27TelemetryLogger;
}

namespace growbox::app::climate_io::runtime {

class Stage28ServiceConsoleStorageCommands final {
public:
  Stage28ServiceConsoleStorageCommands(const storage::Stage27TelemetryLogger* storage_logger,
                                       ServiceConsoleTextSink& sink) noexcept
      : storage_logger_(storage_logger), sink_(sink) {}

  bool handle(const ServiceConsoleCommand& command) noexcept;

private:
  void printSdLogStatus() noexcept;
  void printSdLogList() noexcept;
  void handleSdLogRead(const ServiceConsoleCommand& command) noexcept;
  void handleSdLogSelfTest() noexcept;

  const storage::Stage27TelemetryLogger* storage_logger_{nullptr};
  ServiceConsoleTextSink& sink_;
};

} // namespace growbox::app::climate_io::runtime
