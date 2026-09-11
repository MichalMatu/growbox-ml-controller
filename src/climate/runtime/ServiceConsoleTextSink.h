#pragma once

#include <cstdarg>

namespace growbox::app::climate_io::runtime {

class ServiceConsoleTextSink {
public:
  virtual ~ServiceConsoleTextSink() = default;
  virtual void writeText(const char* text) noexcept = 0;
  void writeFormatted(const char* format, ...) noexcept;
};

class ServiceConsoleStatusContributor {
public:
  virtual ~ServiceConsoleStatusContributor() = default;
  virtual void printStatusDetails() noexcept = 0;
};

} // namespace growbox::app::climate_io::runtime
