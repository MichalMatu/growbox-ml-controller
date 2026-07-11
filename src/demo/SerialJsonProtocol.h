#pragma once

#include "DummyEnvironmentSimulator.h"

#include <driver/uart.h>
#include <esp_err.h>

#include <cstddef>
#include <cstdint>

struct cJSON;

namespace growbox {
namespace demo {

enum class DemoMode : std::uint8_t {
  ClosedLoop = 0,
  Replay,
};

struct DemoRuntimeState {
  DemoMode mode = DemoMode::ClosedLoop;
  bool paused = false;
  bool step_requested = false;
  bool controller_reset_requested = true;
  std::uint32_t step = 0U;
};

class SerialJsonProtocol {
 public:
  static constexpr std::size_t kMaximumLineBytes = 1536U;

  explicit SerialJsonProtocol(uart_port_t port = UART_NUM_0) noexcept : port_(port) {}

  esp_err_t begin(int baud_rate = 115200) noexcept;
  void poll(DummyEnvironmentSimulator& simulator, DemoRuntimeState& runtime) noexcept;

 private:
  void processLine(DummyEnvironmentSimulator& simulator, DemoRuntimeState& runtime) noexcept;
  void emitError(const char* code, const char* message) const noexcept;
  void emitAck(const char* command) const noexcept;
  void emitStatus(const DummyEnvironmentSimulator& simulator,
                  const DemoRuntimeState& runtime) const noexcept;
  void writeJson(cJSON* document) const noexcept;

  uart_port_t port_;
  char line_[kMaximumLineBytes + 1U]{};
  std::size_t length_ = 0U;
  bool discarding_ = false;
};

}  // namespace demo
}  // namespace growbox
