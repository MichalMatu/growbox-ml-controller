#include "climate/runtime/console/ServiceConsoleTextSink.h"

#include <array>
#include <cstdio>

namespace growbox::app::climate_io::runtime {

void ServiceConsoleTextSink::writeFormatted(const char* format, ...) noexcept {
  if (format == nullptr) {
    return;
  }
  std::array<char, 640U> buffer{};
  va_list arguments;
  va_start(arguments, format);
  const int written = std::vsnprintf(buffer.data(), buffer.size(), format, arguments);
  va_end(arguments);
  if (written <= 0) {
    return;
  }
  buffer.back() = '\0';
  writeText(buffer.data());
}

} // namespace growbox::app::climate_io::runtime
