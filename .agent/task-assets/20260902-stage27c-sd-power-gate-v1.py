from pathlib import Path


def replace(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"expected text not found in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1))

replace(
    "src/climate/storage/Stage27SdDataLogger.h",
    "    int cs = 10;\n",
    "    int cs = 10;\n    int power = -1;\n",
)

replace(
    "src/climate/storage/Stage27SdDataLogger.cpp",
    "#include <driver/sdspi_host.h>\n#include <driver/spi_master.h>\n",
    "#include <driver/gpio.h>\n#include <driver/sdspi_host.h>\n#include <driver/spi_master.h>\n",
)

replace(
    "src/climate/storage/Stage27SdDataLogger.cpp",
    "bool Stage27SdDataLogger::begin(const char* firmware_sha) noexcept {\n  if (queue_ != nullptr || task_ != nullptr) {\n    return true;\n  }\n\n",
    "bool Stage27SdDataLogger::begin(const char* firmware_sha) noexcept {\n  if (queue_ != nullptr || task_ != nullptr) {\n    return true;\n  }\n\n  if (pins_.power >= 0) {\n    const auto power_gpio = static_cast<gpio_num_t>(pins_.power);\n    const esp_err_t direction_error = gpio_set_direction(power_gpio, GPIO_MODE_OUTPUT);\n    if (direction_error != ESP_OK) {\n      ESP_LOGE(kTag, \"Failed to configure SD power GPIO %d: %s\", pins_.power,\n               esp_err_to_name(direction_error));\n      return false;\n    }\n    const esp_err_t level_error = gpio_set_level(power_gpio, 1);\n    if (level_error != ESP_OK) {\n      ESP_LOGE(kTag, \"Failed to enable SD power GPIO %d: %s\", pins_.power,\n               esp_err_to_name(level_error));\n      return false;\n    }\n    vTaskDelay(pdMS_TO_TICKS(10));\n    ESP_LOGI(kTag, \"SD power enabled on GPIO%d\", pins_.power);\n  }\n\n",
)

replace(
    "src/climate/storage/Stage27SdDataLogger.cpp",
    "  ESP_LOGI(kTag, \"SD mounted on SPI2 MOSI=%d MISO=%d CLK=%d CS=%d\", pins_.mosi, pins_.miso,\n           pins_.sclk, pins_.cs);\n",
    "  ESP_LOGI(kTag, \"SD mounted on SPI2 MOSI=%d MISO=%d CLK=%d CS=%d POWER=%d\", pins_.mosi,\n           pins_.miso, pins_.sclk, pins_.cs, pins_.power);\n",
)

replace(
    "src/climate/storage/Stage27SdDataLogger.cpp",
    "      \",\\\"sd_spi\\\":{\\\"host\\\":2,\\\"mosi\\\":%d,\\\"miso\\\":%d,\\\"clk\\\":%d,\\\"cs\\\":%d}}\\n\",\n      firmware_sha_, session_id_, snapshot.reset_reason, snapshot.uptime_ms,\n      snapshot.rtc_trusted ? \"true\" : \"false\", snapshot.unix_time_s, pins_.mosi, pins_.miso,\n      pins_.sclk, pins_.cs);\n",
    "      \",\\\"sd_spi\\\":{\\\"host\\\":2,\\\"mosi\\\":%d,\\\"miso\\\":%d,\\\"clk\\\":%d,\\\"cs\\\":%d,\\\"power\\\":%d}}\\n\",\n      firmware_sha_, session_id_, snapshot.reset_reason, snapshot.uptime_ms,\n      snapshot.rtc_trusted ? \"true\" : \"false\", snapshot.unix_time_s, pins_.mosi, pins_.miso,\n      pins_.sclk, pins_.cs, pins_.power);\n",
)

replace(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    "#ifndef GROWBOX_SD_CS_GPIO\n#define GROWBOX_SD_CS_GPIO 10\n#endif\n",
    "#ifndef GROWBOX_SD_CS_GPIO\n#define GROWBOX_SD_CS_GPIO 10\n#endif\n#ifndef GROWBOX_SD_POWER_GPIO\n#define GROWBOX_SD_POWER_GPIO -1\n#endif\n",
)

replace(
    "src/climate/ClimateV6RealInputRuntime.cpp",
    "      {GROWBOX_SD_MOSI_GPIO, GROWBOX_SD_MISO_GPIO, GROWBOX_SD_SCLK_GPIO, GROWBOX_SD_CS_GPIO});\n",
    "      {GROWBOX_SD_MOSI_GPIO, GROWBOX_SD_MISO_GPIO, GROWBOX_SD_SCLK_GPIO, GROWBOX_SD_CS_GPIO,\n       GROWBOX_SD_POWER_GPIO});\n",
)

replace(
    "scripts/stage27c_crowpanel.sh",
    "  -D \"GROWBOX_SD_CS_GPIO=10\"\n",
    "  -D \"GROWBOX_SD_CS_GPIO=10\"\n  -D \"GROWBOX_SD_POWER_GPIO=42\"\n",
)
