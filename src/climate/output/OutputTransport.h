#pragma once

#include "climate/output/OutputExecution.h"

namespace growbox::app::output {

class OutputTransport {
public:
  virtual ~OutputTransport() = default;
  virtual TxResult send(const OutputCommand& command) noexcept = 0;
};

} // namespace growbox::app::output
