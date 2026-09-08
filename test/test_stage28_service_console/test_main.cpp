#include "climate/runtime/Stage28ServiceConsoleCommand.h"
#include <cassert>
#include <cstring>
using namespace growbox::app::climate_io::runtime;
namespace {
void testReadOnlyMenuCommands() {
  assert(parseServiceConsoleCommand("help").kind == ServiceConsoleCommandKind::Help);
  assert(parseServiceConsoleCommand("status").kind == ServiceConsoleCommandKind::Status);
  assert(parseServiceConsoleCommand("sensors").kind == ServiceConsoleCommandKind::Sensors);
  assert(parseServiceConsoleCommand("rf list").kind == ServiceConsoleCommandKind::RfList);
}
void testAutomationCommands() {
  auto c = parseServiceConsoleCommand("automation");
  assert(c.kind == ServiceConsoleCommandKind::AutomationStatus);
  c = parseServiceConsoleCommand("automation status");
  assert(c.kind == ServiceConsoleCommandKind::AutomationStatus);
  c = parseServiceConsoleCommand("AUTOMATION ON");
  assert(c.kind == ServiceConsoleCommandKind::AutomationEnable);
  c = parseServiceConsoleCommand("automation off");
  assert(c.kind == ServiceConsoleCommandKind::AutomationDisable);
  assert(parseServiceConsoleCommand("automation maybe").kind == ServiceConsoleCommandKind::Invalid);
}
void testMaintenanceCommands() {
  auto c = parseServiceConsoleCommand("maintenance");
  assert(c.kind == ServiceConsoleCommandKind::MaintenanceStatus);
  c = parseServiceConsoleCommand("maintenance status");
  assert(c.kind == ServiceConsoleCommandKind::MaintenanceStatus);
  c = parseServiceConsoleCommand("maintenance enter");
  assert(c.kind == ServiceConsoleCommandKind::MaintenanceEnter);
  c = parseServiceConsoleCommand("maintenance exit");
  assert(c.kind == ServiceConsoleCommandKind::MaintenanceExit);
  c = parseServiceConsoleCommand("rf raw lamp on");
  assert(c.kind == ServiceConsoleCommandKind::MaintenanceRawOutput &&
         c.device == ServiceConsoleRfDevice::Lamp && c.state == ServiceConsoleRfState::On);
  c = parseServiceConsoleCommand("RF RAW FAN OFF");
  assert(c.kind == ServiceConsoleCommandKind::MaintenanceRawOutput &&
         c.device == ServiceConsoleRfDevice::Fan && c.state == ServiceConsoleRfState::Off);
  assert(parseServiceConsoleCommand("rf raw lamp maybe").kind ==
         ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("maintenance maybe").kind ==
         ServiceConsoleCommandKind::Invalid);
}
void testSupervisedManualOutputCommands() {
  auto c = parseServiceConsoleCommand("output lamp on");
  assert(c.kind == ServiceConsoleCommandKind::ManualOutput &&
         c.device == ServiceConsoleRfDevice::Lamp && c.state == ServiceConsoleRfState::On);
  c = parseServiceConsoleCommand("OUTPUT FAN OFF");
  assert(c.kind == ServiceConsoleCommandKind::ManualOutput &&
         c.device == ServiceConsoleRfDevice::Fan && c.state == ServiceConsoleRfState::Off);
  c = parseServiceConsoleCommand("rf humidifier on");
  assert(c.kind == ServiceConsoleCommandKind::ManualOutput &&
         c.device == ServiceConsoleRfDevice::Humidifier && c.state == ServiceConsoleRfState::On);
  assert(parseServiceConsoleCommand("output rx").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("output lamp maybe").kind ==
         ServiceConsoleCommandKind::Invalid);
}
void testRfReceiveTimeoutBounds() {
  auto c = parseServiceConsoleCommand("rf rx");
  assert(c.kind == ServiceConsoleCommandKind::RfReceive && c.timeout_ms == 1000U);
  assert(parseServiceConsoleCommand("rf rx 49").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("rf rx 5001").kind == ServiceConsoleCommandKind::Invalid);
}
void testRtcSetUnixCommand() {
  auto c = parseServiceConsoleCommand("rtc set-unix 1788589800");
  assert(c.kind == ServiceConsoleCommandKind::RtcSetUnix && c.unix_time_s == 1788589800ULL);
  assert(parseServiceConsoleCommand("rtc set-unix -1").kind == ServiceConsoleCommandKind::Invalid);
}
void testSdLogCommands() {
  assert(parseServiceConsoleCommand("sdlog status").kind == ServiceConsoleCommandKind::SdLogStatus);
  assert(parseServiceConsoleCommand("sdlog list").kind == ServiceConsoleCommandKind::SdLogList);
  assert(parseServiceConsoleCommand("sdlog selftest").kind ==
         ServiceConsoleCommandKind::SdLogSelfTest);
  auto c = parseServiceConsoleCommand("sdlog read B37B41D6.JL 0 384");
  assert(c.kind == ServiceConsoleCommandKind::SdLogRead);
  assert(std::strcmp(c.filename.data(), "B37B41D6.JL") == 0);
  assert(c.offset == 0U && c.length == 384U);
  assert(parseServiceConsoleCommand("sdlog read ../secret 0 10").kind ==
         ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("sdlog read B37B41D6.JL 0 0").kind ==
         ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("sdlog read B37B41D6.JL 0 385").kind ==
         ServiceConsoleCommandKind::Invalid);
}
void testInvalidCommandsFailClosed() {
  assert(parseServiceConsoleCommand(nullptr).kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("").kind == ServiceConsoleCommandKind::None);
  assert(parseServiceConsoleCommand("rf lamp maybe").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("sdlog erase all").kind == ServiceConsoleCommandKind::Invalid);
}
} // namespace
int main() {
  testReadOnlyMenuCommands();
  testAutomationCommands();
  testMaintenanceCommands();
  testSupervisedManualOutputCommands();
  testRfReceiveTimeoutBounds();
  testRtcSetUnixCommand();
  testSdLogCommands();
  testInvalidCommandsFailClosed();
  return 0;
}
