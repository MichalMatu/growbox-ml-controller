#pragma once

#include "climate/output/OutputTransport.h"
#include "climate/output/supervisor/OutputSupervisorResolver.h"

#include <cstdint>

namespace growbox::app::output {

class OutputSupervisorExecutor final {
public:
  OutputSupervisorExecutor(OutputTransport& transport, OutputStateStore& state_store,
                           OutputSupervisorResolverConfig config) noexcept;

  bool valid() const noexcept {
    return valid_;
  }

  // A transport failure is represented in ExecutionReport and does not make
  // this method fail. false is reserved for invalid supervisor contracts or
  // internal bookkeeping failures.
  bool execute(const OutputSupervisorResolution& resolution, std::uint64_t attempted_ms,
               ExecutionReport& report) noexcept;

private:
  static bool validConfig(const OutputSupervisorResolverConfig& config) noexcept;
  const OutputSupervisorEndpointBinding* findBinding(OutputEndpointId endpoint) const noexcept;
  static const OutputSupervisorEndpointResolution*
  findResolution(const OutputSupervisorResolution& resolution, OutputEndpointId endpoint) noexcept;
  bool validateResolution(const OutputSupervisorResolution& resolution) const noexcept;

  OutputTransport& transport_;
  OutputStateStore& state_store_;
  OutputSupervisorResolverConfig config_{};
  bool valid_{false};
};

} // namespace growbox::app::output
