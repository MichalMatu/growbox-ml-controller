#pragma once

#include "DummyEnvironmentSimulator.h"

#include <Arduino.h>

#include <cstddef>
#include <cstdint>

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

  void poll(Stream& stream, DummyEnvironmentSimulator& simulator,
            DemoRuntimeState& runtime) noexcept;

 private:
  void processLine(Stream& stream, DummyEnvironmentSimulator& simulator,
                   DemoRuntimeState& runtime) noexcept;
  void emitError(Stream& stream, const char* code, const char* message) const noexcept;
  void emitAck(Stream& stream, const char* command) const noexcept;
  void emitStatus(Stream& stream, const DummyEnvironmentSimulator& simulator,
                  const DemoRuntimeState& runtime) const noexcept;

  char line_[kMaximumLineBytes + 1U]{};
  std::size_t length_ = 0U;
  bool discarding_ = false;
};

}  // namespace demo
}  // namespace growbox
