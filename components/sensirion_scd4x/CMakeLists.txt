idf_component_register(
  SRCS
    "scd4x_i2c.c"
    "sensirion_common.c"
    "sensirion_i2c.c"
    "sensirion_i2c_hal.c"
  INCLUDE_DIRS "."
  REQUIRES esp_driver_i2c freertos
)
