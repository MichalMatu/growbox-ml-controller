#include "climate/runtime/Stage28eDiagnosticsCore.h"

#include <cassert>
#include <cstdint>
#include <limits>

using namespace growbox::app::climate_io::runtime;

int main() {
  DiagnosticLogFilter filter;
  assert(filter.enabled(DiagnosticLogModule::Sys, DiagnosticLogLevel::Error));
  assert(filter.enabled(DiagnosticLogModule::Sys, DiagnosticLogLevel::Info));
  assert(!filter.enabled(DiagnosticLogModule::Sys, DiagnosticLogLevel::Debug));
  filter.setLevel(DiagnosticLogModule::Sys, DiagnosticLogLevel::Trace);
  assert(filter.enabled(DiagnosticLogModule::Sys, DiagnosticLogLevel::Trace));
  filter.setLevel(DiagnosticLogModule::Rf, DiagnosticLogLevel::Warn);
  assert(filter.enabled(DiagnosticLogModule::Rf, DiagnosticLogLevel::Warn));
  assert(!filter.enabled(DiagnosticLogModule::Rf, DiagnosticLogLevel::Info));

  assert(classifyStackMargin(300U, 1000U) == StackMarginSeverity::Normal);
  assert(classifyStackMargin(249U, 1000U) == StackMarginSeverity::Warning);
  assert(classifyStackMargin(99U, 1000U) == StackMarginSeverity::Critical);
  assert(classifyStackMargin(0U, 0U) == StackMarginSeverity::Unknown);
  assert(classifyStackMargin(1001U, 1000U) == StackMarginSeverity::Unknown);

  TimingAccumulator timing{};
  timing.budget_us = 100U;
  timing.observe(50U);
  timing.observe(100U);
  timing.observe(101U);
  assert(timing.sample_count == 3U);
  assert(timing.total_us == 251U);
  assert(timing.max_us == 101U);
  assert(timing.overrun_count == 1U);

  TimingAccumulator saturating{};
  saturating.sample_count = std::numeric_limits<std::uint64_t>::max();
  saturating.total_us = std::numeric_limits<std::uint64_t>::max() - 2U;
  saturating.overrun_count = std::numeric_limits<std::uint64_t>::max();
  saturating.budget_us = 1U;
  saturating.observe(10U);
  assert(saturating.sample_count == std::numeric_limits<std::uint64_t>::max());
  assert(saturating.total_us == std::numeric_limits<std::uint64_t>::max());
  assert(saturating.overrun_count == std::numeric_limits<std::uint64_t>::max());

  assert(diagnosticLogModuleCount() == 14U);
  assert(diagnosticLogLevelName(DiagnosticLogLevel::Debug)[0] == 'D');
  assert(diagnosticLogModuleName(DiagnosticLogModule::Arbiter)[0] == 'A');

  return 0;
}
