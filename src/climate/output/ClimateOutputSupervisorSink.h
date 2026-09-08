#pragma once

#include "climate/ClimateSemanticOutput.h"
#include "climate/output/OutputSupervisorExecutor.h"

#include <cstdint>

namespace growbox::app::climate_io {

struct ClimateOutputSupervisorCycleContext {
  ::growbox::app::output::SupervisorMode mode =
      ::growbox::app::output::SupervisorMode::Automatic;
  ::growbox::app::output::ScheduleIntent schedule{};
  ::growbox::app::output::ManualIntent manual{};
  ::growbox::app::output::SafetyEnvelope safety{};
};

class ClimateOutputSupervisorSink final : public ::growbox::climate::ClimateActuatorSink {
public:
  ClimateOutputSupervisorSink(
      ClimateSemanticOutputConfig climate_config,
      ::growbox::app::output::OutputSupervisorResolver& resolver,
      ::growbox::app::output::OutputSupervisorExecutor& executor,
      ::growbox::app::output::OutputStateStore& state_store) noexcept;

  bool valid() const noexcept;
  void setCycleContext(const ClimateOutputSupervisorCycleContext& context) noexcept {
    context_ = context;
  }

  bool apply(const ::growbox::climate::ClimatePolicyRequest& request,
             std::uint64_t monotonic_ms) noexcept override;
  bool applyAndReport(const ::growbox::climate::ClimatePolicyRequest& request,
                      std::uint64_t monotonic_ms,
                      ::growbox::climate::ClimatePolicyRequest& executed_projection) noexcept override;
  bool applyAndReportExecution(
      const ::growbox::climate::ClimatePolicyRequest& request, std::uint64_t monotonic_ms,
      ::growbox::climate::ClimateExecutionProjection& execution) noexcept override;
  bool applyFailSafeOff(std::uint64_t monotonic_ms) noexcept override;

  const ::growbox::app::output::OutputSupervisorResolution& lastResolution() const noexcept {
    return last_resolution_;
  }
  const ::growbox::app::output::ExecutionReport& lastReport() const noexcept {
    return last_report_;
  }

private:
  static float roleLevel(const ::growbox::climate::ClimatePolicyRequest& request,
                         ClimateActuatorRole role) noexcept;
  static void setRoleLevel(::growbox::climate::ClimatePolicyRequest& request,
                           ClimateActuatorRole role, float level) noexcept;
  static bool reportTransportCompleted(
      const ::growbox::app::output::ExecutionReport& report) noexcept;

  bool buildControlIntent(const ::growbox::climate::ClimatePolicyRequest& request,
                          std::uint64_t monotonic_ms,
                          ::growbox::app::output::ControlIntent& intent) noexcept;
  bool executeCycle(const ::growbox::app::output::ControlIntent& control,
                    std::uint64_t monotonic_ms, bool& transport_completed) noexcept;
  bool projectExecutedClimate(
      ::growbox::climate::ClimateExecutionProjection& projection) const noexcept;
  std::uint64_t nextSequence() noexcept;

  ClimateSemanticOutputConfig climate_config_{};
  ClimateSemanticOutputConfigStatus config_status_{ClimateSemanticOutputConfigStatus::Ok};
  ::growbox::app::output::OutputSupervisorResolver& resolver_;
  ::growbox::app::output::OutputSupervisorExecutor& executor_;
  ::growbox::app::output::OutputStateStore& state_store_;
  ClimateOutputSupervisorCycleContext context_{};
  ::growbox::app::output::OutputSupervisorResolution last_resolution_{};
  ::growbox::app::output::ExecutionReport last_report_{};
  std::uint64_t sequence_{0U};
};

} // namespace growbox::app::climate_io
