#pragma once

#include <driver/spi_master.h>

namespace growbox::app::climate_io::storage::crowpanel {

bool runSdCmd0Precondition(spi_host_device_t host, int cs_pin) noexcept;

} // namespace growbox::app::climate_io::storage::crowpanel
