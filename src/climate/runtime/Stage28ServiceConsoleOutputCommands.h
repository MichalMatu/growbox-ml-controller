#pragma once

#include "climate/runtime/ServiceConsoleTextSink.h"
#include "climate/runtime/Stage28ServiceConsoleCommand.h"

#include <cstdint>

namespace growbox::app::output {
class OutputAutomationControl;
class OutputManualControl;
class OutputMaintenanceControl;
} // namespace growbox::app::output

namespace growbox::app::climate_io::runtime {

class Stage28ServiceConsoleOutputCommands final : public ServiceConsoleStatusContributor {
public:
  struct Config {
    const bool* real_outputs_active{nullptr};
    ::growbox::app::output::OutputAutomationControl* automation_control{nullptr};
    ::growbox::app::output::OutputManualControl* manual_control{nullptr};
    ::growbox::app::output::OutputMaintenanceControl* maintenance_control{nullptr};
  };

  Stage28ServiceConsoleOutputCommands(Config config, ServiceConsoleTextSink& sink) noexcept
      : config_(config), sink_(sink) {}

  bool handle(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;
  void printStatusDetails() noexcept override;

private:
  bool realOutputsActive() const noexcept;
  const char* outputModeName() const noexcept;
  void printAutomationStatus() noexcept;
  void handleAutomationRequest(bool enabled) noexcept;
  void printMaintenanceStatus() noexcept;
  void handleMaintenanceRequest(bool enter) noexcept;
  void handleMaintenanceRaw(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;
  void handleManualOutput(const ServiceConsoleCommand& command, std::uint64_t now_ms) noexcept;

  Config config_{};
  ServiceConsoleTextSink& sink_;
};

} // namespace growbox::app::climate_io::runtime
