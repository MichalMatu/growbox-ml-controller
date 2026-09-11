#pragma once

#include "climate/runtime/Stage28ServiceConsoleCommand.h"

#include <cstdint>

namespace growbox::app::climate_io::runtime {

enum class ServiceConsoleCommandDomain : std::uint8_t {
  None = 0U,
  Builtin,
  Output,
  Storage,
  System,
  Invalid,
};

ServiceConsoleCommandDomain serviceConsoleCommandDomain(ServiceConsoleCommandKind kind) noexcept;

} // namespace growbox::app::climate_io::runtime
