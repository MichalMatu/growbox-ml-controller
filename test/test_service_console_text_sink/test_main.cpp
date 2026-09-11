#include "climate/runtime/ServiceConsoleTextSink.h"

#include <cassert>
#include <string>

using growbox::app::climate_io::runtime::ServiceConsoleTextSink;

namespace {
class BufferSink final : public ServiceConsoleTextSink {
public:
  void writeText(const char* text) noexcept override {
    if (text != nullptr) {
      output += text;
    }
  }
  std::string output;
};
}

int main() {
  BufferSink sink;
  sink.writeFormatted("value=%d %s", 7, "ok");
  assert(sink.output == "value=7 ok");
  sink.writeFormatted(nullptr);
  assert(sink.output == "value=7 ok");
  sink.output.clear();
  const std::string oversized(700U, 'x');
  sink.writeFormatted("%s", oversized.c_str());
  assert(sink.output.size() == 639U);
  return 0;
}
