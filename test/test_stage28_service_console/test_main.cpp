#include "climate/runtime/Stage28ServiceConsoleCommand.h"

#include <cassert>

using namespace growbox::app::climate_io::runtime;

namespace {

void testReadOnlyMenuCommands() {
  assert(parseServiceConsoleCommand("help").kind == ServiceConsoleCommandKind::Help);
  assert(parseServiceConsoleCommand("?").kind == ServiceConsoleCommandKind::Help);
  assert(parseServiceConsoleCommand("0").kind == ServiceConsoleCommandKind::Help);
  assert(parseServiceConsoleCommand("status").kind == ServiceConsoleCommandKind::Status);
  assert(parseServiceConsoleCommand("1").kind == ServiceConsoleCommandKind::Status);
  assert(parseServiceConsoleCommand("sensors").kind == ServiceConsoleCommandKind::Sensors);
  assert(parseServiceConsoleCommand("2").kind == ServiceConsoleCommandKind::Sensors);
  assert(parseServiceConsoleCommand("rf").kind == ServiceConsoleCommandKind::RfList);
  assert(parseServiceConsoleCommand("rf list").kind == ServiceConsoleCommandKind::RfList);
  assert(parseServiceConsoleCommand("3").kind == ServiceConsoleCommandKind::RfList);
}

void testNamedRfTransmitCommands() {
  const auto lamp = parseServiceConsoleCommand("rf lamp on");
  assert(lamp.kind == ServiceConsoleCommandKind::RfTransmit);
  assert(lamp.device == ServiceConsoleRfDevice::Lamp);
  assert(lamp.state == ServiceConsoleRfState::On);

  const auto fan = parseServiceConsoleCommand("RF FAN OFF");
  assert(fan.kind == ServiceConsoleCommandKind::RfTransmit);
  assert(fan.device == ServiceConsoleRfDevice::Fan);
  assert(fan.state == ServiceConsoleRfState::Off);

  const auto humidifier = parseServiceConsoleCommand("  rf   humidifier   on  ");
  assert(humidifier.kind == ServiceConsoleCommandKind::RfTransmit);
  assert(humidifier.device == ServiceConsoleRfDevice::Humidifier);
  assert(humidifier.state == ServiceConsoleRfState::On);
}

void testRfReceiveTimeoutBounds() {
  const auto default_rx = parseServiceConsoleCommand("rf rx");
  assert(default_rx.kind == ServiceConsoleCommandKind::RfReceive);
  assert(default_rx.timeout_ms == 1000U);

  const auto bounded_rx = parseServiceConsoleCommand("rf rx 2500");
  assert(bounded_rx.kind == ServiceConsoleCommandKind::RfReceive);
  assert(bounded_rx.timeout_ms == 2500U);

  assert(parseServiceConsoleCommand("rf rx 49").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("rf rx 5001").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("rf rx nope").kind == ServiceConsoleCommandKind::Invalid);
}

void testInvalidCommandsFailClosed() {
  assert(parseServiceConsoleCommand(nullptr).kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("").kind == ServiceConsoleCommandKind::None);
  assert(parseServiceConsoleCommand("rf lamp maybe").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("rf unknown on").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("fan on").kind == ServiceConsoleCommandKind::Invalid);
  assert(parseServiceConsoleCommand("rf lamp on extra").kind == ServiceConsoleCommandKind::Invalid);
}

} // namespace

int main() {
  testReadOnlyMenuCommands();
  testNamedRfTransmitCommands();
  testRfReceiveTimeoutBounds();
  testInvalidCommandsFailClosed();
  return 0;
}
