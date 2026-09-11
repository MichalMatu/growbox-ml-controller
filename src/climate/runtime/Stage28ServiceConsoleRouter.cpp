#include "climate/runtime/Stage28ServiceConsoleRouter.h"

namespace growbox::app::climate_io::runtime {

ServiceConsoleCommandDomain serviceConsoleCommandDomain(ServiceConsoleCommandKind kind) noexcept {
  switch (kind) {
  case ServiceConsoleCommandKind::None:
    return ServiceConsoleCommandDomain::None;
  case ServiceConsoleCommandKind::Help:
    return ServiceConsoleCommandDomain::Builtin;
  case ServiceConsoleCommandKind::ManualOutput:
  case ServiceConsoleCommandKind::AutomationStatus:
  case ServiceConsoleCommandKind::AutomationEnable:
  case ServiceConsoleCommandKind::AutomationDisable:
  case ServiceConsoleCommandKind::MaintenanceStatus:
  case ServiceConsoleCommandKind::MaintenanceEnter:
  case ServiceConsoleCommandKind::MaintenanceExit:
  case ServiceConsoleCommandKind::MaintenanceRawOutput:
    return ServiceConsoleCommandDomain::Output;
  case ServiceConsoleCommandKind::SdLogStatus:
  case ServiceConsoleCommandKind::SdLogList:
  case ServiceConsoleCommandKind::SdLogRead:
  case ServiceConsoleCommandKind::SdLogSelfTest:
    return ServiceConsoleCommandDomain::Storage;
  case ServiceConsoleCommandKind::Status:
  case ServiceConsoleCommandKind::Sensors:
  case ServiceConsoleCommandKind::RfList:
  case ServiceConsoleCommandKind::RfReceive:
  case ServiceConsoleCommandKind::RtcSetUnix:
    return ServiceConsoleCommandDomain::System;
  case ServiceConsoleCommandKind::Invalid:
    return ServiceConsoleCommandDomain::Invalid;
  }
  return ServiceConsoleCommandDomain::Invalid;
}

} // namespace growbox::app::climate_io::runtime
