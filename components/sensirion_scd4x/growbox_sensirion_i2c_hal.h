#pragma once

#include <driver/i2c_master.h>

#ifdef __cplusplus
extern "C" {
#endif

void growbox_sensirion_i2c_bind_device(i2c_master_dev_handle_t device);

#ifdef __cplusplus
}
#endif
