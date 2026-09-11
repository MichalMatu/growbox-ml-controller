#include "climate/runtime/RuntimeOutputTransport.h"

#include <iostream>

namespace {

int failures = 0;

void check(bool condition, const char* message) {
  if (!condition) {
    ++failures;
    std::cerr << "FAIL: " << message << '\n';
  }
}

class FakeTransport final : public growbox::app::output::OutputTransport {
public:
  growbox::app::output::TxResult
  send(const growbox::app::output::OutputCommand&) noexcept override {
    ++calls;
    return result;
  }

  growbox::app::output::TxResult result{
      growbox::app::output::TransportStatus::Completed,
      growbox::app::output::TransportError::None,
  };
  int calls{0};
};

void lockedTransportDoesNotFabricateExecution() {
  using namespace growbox::app;

  FakeTransport real_transport;
  climate_io::runtime::RuntimeExecutionStatus status{};
  status.transport_available = false;
  climate_io::runtime::RuntimeOutputTransport transport(real_transport, status);

  output::OutputCommand command{};
  command.endpoint = 1U;
  command.state = output::BinaryOutputState::On;

  const auto result = transport.send(command);
  check(result.status == output::TransportStatus::NotAttempted,
        "locked transport must report NotAttempted");
  check(result.error == output::TransportError::Unavailable,
        "locked transport must report Unavailable");
  check(real_transport.calls == 0, "locked transport must not call physical transport");
  check(transport.transmitCount() == 0U, "locked transport must not count successful TX");
  check(transport.transmitErrorCount() == 0U,
        "locked transport must not count a non-attempt as TX error");
}

void availableTransportCountsCompletedSend() {
  using namespace growbox::app;

  FakeTransport real_transport;
  climate_io::runtime::RuntimeExecutionStatus status{};
  status.transport_available = true;
  climate_io::runtime::RuntimeOutputTransport transport(real_transport, status);

  output::OutputCommand command{};
  command.endpoint = 1U;

  const auto result = transport.send(command);
  check(result.status == output::TransportStatus::Completed, "completed send status");
  check(result.error == output::TransportError::None, "completed send error");
  check(real_transport.calls == 1, "available transport must delegate exactly once");
  check(transport.transmitCount() == 1U, "completed send must increment TX count");
  check(transport.transmitErrorCount() == 0U, "completed send must not increment error count");
}

void availableTransportCountsFailedSend() {
  using namespace growbox::app;

  FakeTransport real_transport;
  real_transport.result = {output::TransportStatus::Failed, output::TransportError::IoFailure};
  climate_io::runtime::RuntimeExecutionStatus status{};
  status.transport_available = true;
  climate_io::runtime::RuntimeOutputTransport transport(real_transport, status);

  output::OutputCommand command{};
  command.endpoint = 1U;

  const auto result = transport.send(command);
  check(result.status == output::TransportStatus::Failed, "failed send status");
  check(result.error == output::TransportError::IoFailure, "failed send error");
  check(real_transport.calls == 1, "failed transport must still delegate exactly once");
  check(transport.transmitCount() == 0U, "failed send must not increment TX count");
  check(transport.transmitErrorCount() == 1U, "failed send must increment error count");
}

} // namespace

int main() {
  lockedTransportDoesNotFabricateExecution();
  availableTransportCountsCompletedSend();
  availableTransportCountsFailedSend();
  if (failures != 0) {
    return 1;
  }
  std::cout << "runtime_output_transport_tests PASS\n";
  return 0;
}
