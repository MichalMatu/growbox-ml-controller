#include "sensirion_i2c_hal.h"
#include "growbox_sensirion_i2c_hal.h"

#include <driver/i2c_master.h>
#include <esp_rom_sys.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

static i2c_master_dev_handle_t g_device = NULL;

void growbox_sensirion_i2c_bind_device(i2c_master_dev_handle_t device) {
    g_device = device;
}

int16_t sensirion_i2c_hal_select_bus(uint8_t bus_idx) {
    return bus_idx == 0U ? 0 : -1;
}

void sensirion_i2c_hal_init(void) {
}

void sensirion_i2c_hal_free(void) {
}

int8_t sensirion_i2c_hal_read(uint8_t address, uint8_t* data, uint8_t count) {
    (void)address;
    if (g_device == NULL || data == NULL || count == 0U) {
        return -1;
    }
    return i2c_master_receive(g_device, data, count, 1000) == ESP_OK ? 0 : -1;
}

int8_t sensirion_i2c_hal_write(uint8_t address, const uint8_t* data, uint8_t count) {
    (void)address;
    if (g_device == NULL || data == NULL || count == 0U) {
        return -1;
    }
    return i2c_master_transmit(g_device, data, count, 1000) == ESP_OK ? 0 : -1;
}

void sensirion_i2c_hal_sleep_usec(uint32_t useconds) {
    if (useconds < 1000U) {
        esp_rom_delay_us(useconds);
        return;
    }
    const TickType_t ticks = pdMS_TO_TICKS((useconds + 999U) / 1000U);
    vTaskDelay(ticks > 0 ? ticks : 1);
}
