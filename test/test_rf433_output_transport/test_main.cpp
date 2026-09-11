#include "climate/output/OutputTypes.h"
#include "climate/rf433/ClimateRf433EndpointRegistry.h"
#include "climate/rf433/Rf433HardwareConfig.h"
#include "climate/rf433/Rf433OutputTransport.h"

#include <cassert>
#include <cstddef>

namespace {

using growbox::app::climate_io::rf433::FrameConfig;
using growbox::app::climate_io::rf433::Rf433FrameSender;
using growbox::app::climate_io::rf433::Rf433OutputTransport;
using growbox::app::output::BinaryOutputState;
using growbox::app::output::OutputCommand;
using growbox::app::output::TransportError;
using growbox::app::output::TransportStatus;

bool sameFrame(const FrameConfig& lhs, const FrameConfig& rhs) {
  return lhs.key == rhs.key && lhs.repeat == rhs.repeat && lhs.pulse_us == rhs.pulse_us;
}

class FakeFrameSender final : public Rf433FrameSender {
public:
  bool transmitFrame(const FrameConfig& frame) noexcept override {
    ++calls;
    last = frame;
    return result;
  }

  bool result{true};
  std::size_t calls{0U};
  FrameConfig last{};
};

void expectMapping(Rf433OutputTransport& transport, FakeFrameSender& sender,
                   growbox::app::output::OutputEndpointId endpoint, BinaryOutputState state,
                   const FrameConfig& expected) {
  const auto before = sender.calls;
  const auto result = transport.send(OutputCommand{endpoint, state});
  assert(result.status == TransportStatus::Completed);
  assert(result.error == TransportError::None);
  assert(sender.calls == before + 1U);
  assert(sameFrame(sender.last, expected));
}

} // namespace

int main() {
  using namespace growbox::app::climate_io::rf433;

  FakeFrameSender sender;
  Rf433OutputTransport transport(sender);

  expectMapping(transport, sender, kRemoteSocket1ClimateEndpoint, BinaryOutputState::On,
                kRemoteSocket1On);
  expectMapping(transport, sender, kRemoteSocket1ClimateEndpoint, BinaryOutputState::Off,
                kRemoteSocket1Off);
  expectMapping(transport, sender, kRemoteSocket2ClimateEndpoint, BinaryOutputState::On,
                kRemoteSocket2On);
  expectMapping(transport, sender, kRemoteSocket2ClimateEndpoint, BinaryOutputState::Off,
                kRemoteSocket2Off);
  expectMapping(transport, sender, kRemoteSocket3ClimateEndpoint, BinaryOutputState::On,
                kRemoteSocket3On);
  expectMapping(transport, sender, kRemoteSocket3ClimateEndpoint, BinaryOutputState::Off,
                kRemoteSocket3Off);

  const auto before_invalid = sender.calls;
  auto result = transport.send(
      OutputCommand{growbox::app::output::kInvalidOutputEndpoint, BinaryOutputState::On});
  assert(result.status == TransportStatus::Failed);
  assert(result.error == TransportError::InvalidEndpoint);
  assert(sender.calls == before_invalid);

  result = transport.send(OutputCommand{99U, BinaryOutputState::Off});
  assert(result.status == TransportStatus::Failed);
  assert(result.error == TransportError::InvalidEndpoint);
  assert(sender.calls == before_invalid);

  result = transport.send(
      OutputCommand{kRemoteSocket1ClimateEndpoint, static_cast<BinaryOutputState>(0x7fU)});
  assert(result.status == TransportStatus::Failed);
  assert(result.error == TransportError::InvalidCommand);
  assert(sender.calls == before_invalid);

  sender.result = false;
  result = transport.send(OutputCommand{kRemoteSocket1ClimateEndpoint, BinaryOutputState::On});
  assert(result.status == TransportStatus::Failed);
  assert(result.error == TransportError::IoFailure);
  assert(sender.calls == before_invalid + 1U);

  return 0;
}
