# Vendored Sensirion SCD4x driver

Upstream: `https://github.com/Sensirion/embedded-i2c-scd4x`

Pinned upstream revision: `b52cebe1bb1b7050feaac75d7cd33e56c6a8a4e9`

The generated SCD4x protocol driver and Sensirion common I2C helpers are copied without
protocol changes. `sensirion_i2c_hal.c` is the growbox native ESP-IDF HAL binding and is
therefore intentionally maintained locally.

License: BSD-3-Clause; see `LICENSE`.
