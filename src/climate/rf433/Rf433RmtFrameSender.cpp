#include "climate/rf433/Rf433RmtFrameSender.h"

namespace growbox::app::climate_io::rf433 {

bool Rf433RmtFrameSender::transmitFrame(const FrameConfig& frame) noexcept {
  LoopbackEvidence evidence{};
  static_cast<void>(radio_.transmitAndReceive(frame, timeout_ms_, evidence));
  return evidence.tx_completed;
}

} // namespace growbox::app::climate_io::rf433
