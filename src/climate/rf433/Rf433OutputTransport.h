#pragma once

#include "climate/output/OutputTransport.h"
#include "climate/rf433/Rf433ProtocolCodec.h"

namespace growbox::app::climate_io::rf433 {

class Rf433FrameSender {
public:
  virtual ~Rf433FrameSender() = default;
  virtual bool transmitFrame(const FrameConfig& frame) noexcept = 0;
};

class Rf433OutputTransport final : public ::growbox::app::output::OutputTransport {
public:
  explicit Rf433OutputTransport(Rf433FrameSender& sender) noexcept : sender_(sender) {}

  ::growbox::app::output::TxResult
  send(const ::growbox::app::output::OutputCommand& command) noexcept override;

private:
  Rf433FrameSender& sender_;
};

} // namespace growbox::app::climate_io::rf433
