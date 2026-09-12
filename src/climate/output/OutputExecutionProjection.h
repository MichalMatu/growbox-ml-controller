#pragma once

#include "climate/output/supervisor/OutputSupervisorResolver.h"

namespace growbox::app::output {

bool buildExecutedControlProjection(const OutputSupervisorResolution& resolution,
                                    const ExecutionReport& report,
                                    const OutputStateStore& state_store,
                                    ExecutedControlProjection& output) noexcept;

const ExecutedEndpointProjection*
findExecutedEndpointProjection(const ExecutedControlProjection& projection,
                               OutputEndpointId endpoint) noexcept;

} // namespace growbox::app::output
