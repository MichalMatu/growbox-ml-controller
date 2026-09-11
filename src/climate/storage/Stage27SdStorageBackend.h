#pragma once

#include "climate/storage/Stage27LogStorageBackend.h"

#include <sdmmc_cmd.h>

#include <cstdint>
#include <cstdio>

namespace growbox::app::climate_io::storage {

class Stage27SdStorageBackend final : public Stage27LogStorageBackend {
public:
  struct Pins {
    int mosi = 40;
    int miso = 13;
    int sclk = 39;
    int cs = 10;
    int power = -1;
  };

  Stage27SdStorageBackend(Pins pins, bool use_cmd0_precondition) noexcept
      : pins_(pins), use_cmd0_precondition_(use_cmd0_precondition) {}

  Stage27StorageBackendKind kind() const noexcept override {
    return Stage27StorageBackendKind::Sd;
  }

  bool initialize() noexcept override;
  bool mount() noexcept override;
  bool beginSession(const char* session_header, std::uint32_t session_id) noexcept override;
  bool appendLine(const char* data, std::size_t length) noexcept override;
  void close() noexcept override;

private:
  bool enablePower() noexcept;
  void disablePower() noexcept;
  void releaseSpiBus() noexcept;
  void closeFile() noexcept;

  Pins pins_{};
  bool use_cmd0_precondition_ = false;
  bool power_configured_ = false;
  bool spi_initialized_ = false;
  sdmmc_card_t* card_ = nullptr;
  std::FILE* file_ = nullptr;
  char session_path_[64]{};
};

} // namespace growbox::app::climate_io::storage
