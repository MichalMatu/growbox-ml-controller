#pragma once

#include "DummyEnvironmentSimulator.h"

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
  bool paused = true;
  bool step_requested = false;
  bool controller_reset_requested = true;
  std::uint32_t step = 0U;
};

class SerialJsonProtocol {
public:
  // Full v3 load_scenario JSON is ~4.2 KiB; keep headroom for future fields.
  static constexpr std::size_t kMaximumLineBytes = 8192U;

  SerialJsonProtocol() noexcept = default;
  ~SerialJsonProtocol() noexcept;

  SerialJsonProtocol(const SerialJsonProtocol&) = delete;
  SerialJsonProtocol& operator=(const SerialJsonProtocol&) = delete;

  esp_err_t begin() noexcept;
  void poll(DummyEnvironmentSimulator& simulator, DemoRuntimeState& runtime) noexcept;

private:
  void processLine(DummyEnvironmentSimulator& simulator, DemoRuntimeState& runtime) noexcept;
  void emitError(const char* code, const char* message) const noexcept;
  void emitAck(const char* command) const noexcept;
  void emitStatus(const DummyEnvironmentSimulator& simulator,
                  const DemoRuntimeState& runtime) const noexcept;
  void writeJson(cJSON* document) const noexcept;

  char* line_ = nullptr;
  std::size_t length_ = 0U;
  bool discarding_ = false;
};

} // namespace demo
} // namespace growbox
