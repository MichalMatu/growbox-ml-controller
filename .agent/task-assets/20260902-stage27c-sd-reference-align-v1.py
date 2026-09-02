from pathlib import Path

cpp = Path('src/climate/storage/Stage27SdDataLogger.cpp')
hdr = Path('src/climate/storage/Stage27SdDataLogger.h')

cpp_text = cpp.read_text()
hdr_text = hdr.read_text()


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)

cpp_text = replace_once(
    cpp_text,
    '''constexpr std::uint32_t kTaskStackBytes = 6144U;\n''',
    '''constexpr std::uint32_t kTaskStackBytes = 6144U;\nconstexpr spi_host_device_t kSdSpiHost = SPI3_HOST;\nconstexpr std::uint32_t kPowerOnDelayMs = 100U;\n''',
    'constants',
)

cpp_text = replace_once(
    cpp_text,
    '''    const esp_err_t level_error = gpio_set_level(power_gpio, 1);\n    if (level_error != ESP_OK) {\n      ESP_LOGE(kTag, "Failed to enable SD power GPIO %d: %s", pins_.power,\n               esp_err_to_name(level_error));\n      return false;\n    }\n    vTaskDelay(pdMS_TO_TICKS(10));\n    ESP_LOGI(kTag, "SD power enabled on GPIO%d", pins_.power);\n''',
    '''    const esp_err_t level_error = gpio_set_level(power_gpio, 0);\n    if (level_error != ESP_OK) {\n      ESP_LOGE(kTag, "Failed to initialize SD power GPIO %d low: %s", pins_.power,\n               esp_err_to_name(level_error));\n      return false;\n    }\n    ESP_LOGI(kTag, "SD power control initialized on GPIO%d", pins_.power);\n''',
    'begin power state',
)

old_mount = '''bool Stage27SdDataLogger::mountStorage(\n    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {\n  if (!spi_initialized_) {\n    spi_bus_config_t bus_config{};\n    bus_config.mosi_io_num = pins_.mosi;\n    bus_config.miso_io_num = pins_.miso;\n    bus_config.sclk_io_num = pins_.sclk;\n    bus_config.quadwp_io_num = -1;\n    bus_config.quadhd_io_num = -1;\n    bus_config.max_transfer_sz = 4096;\n\n    const esp_err_t spi_error = spi_bus_initialize(SPI2_HOST, &bus_config, SPI_DMA_CH_AUTO);\n    if (spi_error != ESP_OK && spi_error != ESP_ERR_INVALID_STATE) {\n      mount_errors_.fetch_add(1U, std::memory_order_relaxed);\n      ESP_LOGW(kTag, "SPI bus init failed: %s", esp_err_to_name(spi_error));\n      return false;\n    }\n    spi_initialized_ = true;\n  }\n\n  sdmmc_host_t host = SDSPI_HOST_DEFAULT();\n  host.slot = SPI2_HOST;\n  sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();\n  slot_config.gpio_cs = static_cast<gpio_num_t>(pins_.cs);\n  slot_config.host_id = SPI2_HOST;\n  esp_vfs_fat_sdmmc_mount_config_t mount_config{};\n  mount_config.format_if_mount_failed = false;\n  mount_config.max_files = 2;\n  mount_config.allocation_unit_size = 16U * 1024U;\n\n  card_ = nullptr;\n  const esp_err_t mount_error =\n      esp_vfs_fat_sdspi_mount(kMountPoint, &host, &slot_config, &mount_config, &card_);\n  if (mount_error != ESP_OK) {\n    mount_errors_.fetch_add(1U, std::memory_order_relaxed);\n    ESP_LOGW(kTag, "SD mount failed at uptime=%llu: %s",\n             static_cast<unsigned long long>(snapshot.uptime_ms), esp_err_to_name(mount_error));\n    card_ = nullptr;\n    return false;\n  }\n\n  if (mkdir(kDataDirectory, 0775) != 0 && errno != EEXIST) {\n    write_errors_.fetch_add(1U, std::memory_order_relaxed);\n    ESP_LOGW(kTag, "Failed to create %s: errno=%d", kDataDirectory, errno);\n    closeMountedStorage();\n    return false;\n  }\n\n  mounted_.store(true, std::memory_order_relaxed);\n  ESP_LOGI(kTag, "SD mounted on SPI2 MOSI=%d MISO=%d CLK=%d CS=%d POWER=%d", pins_.mosi, pins_.miso,\n           pins_.sclk, pins_.cs, pins_.power);\n  return openSession(snapshot);\n}\n'''

new_mount = '''bool Stage27SdDataLogger::mountStorage(\n    const telemetry::Stage27TelemetrySnapshot& snapshot) noexcept {\n  if (!enableStoragePower()) {\n    mount_errors_.fetch_add(1U, std::memory_order_relaxed);\n    return false;\n  }\n\n  if (!spi_initialized_) {\n    spi_bus_config_t bus_config{};\n    bus_config.mosi_io_num = pins_.mosi;\n    bus_config.miso_io_num = pins_.miso;\n    bus_config.sclk_io_num = pins_.sclk;\n    bus_config.quadwp_io_num = -1;\n    bus_config.quadhd_io_num = -1;\n    bus_config.max_transfer_sz = 4096;\n\n    const esp_err_t spi_error = spi_bus_initialize(kSdSpiHost, &bus_config, SPI_DMA_CH_AUTO);\n    if (spi_error != ESP_OK) {\n      mount_errors_.fetch_add(1U, std::memory_order_relaxed);\n      ESP_LOGW(kTag, "SPI3 bus init failed: %s", esp_err_to_name(spi_error));\n      disableStoragePower();\n      return false;\n    }\n    spi_initialized_ = true;\n  }\n\n  sdmmc_host_t host = SDSPI_HOST_DEFAULT();\n  host.slot = kSdSpiHost;\n  sdspi_device_config_t slot_config = SDSPI_DEVICE_CONFIG_DEFAULT();\n  slot_config.gpio_cs = static_cast<gpio_num_t>(pins_.cs);\n  slot_config.host_id = kSdSpiHost;\n  esp_vfs_fat_sdmmc_mount_config_t mount_config{};\n  mount_config.format_if_mount_failed = false;\n  mount_config.max_files = 2;\n  mount_config.allocation_unit_size = 16U * 1024U;\n\n  card_ = nullptr;\n  const esp_err_t mount_error =\n      esp_vfs_fat_sdspi_mount(kMountPoint, &host, &slot_config, &mount_config, &card_);\n  if (mount_error != ESP_OK) {\n    mount_errors_.fetch_add(1U, std::memory_order_relaxed);\n    ESP_LOGW(kTag, "SD mount failed at uptime=%llu: %s",\n             static_cast<unsigned long long>(snapshot.uptime_ms), esp_err_to_name(mount_error));\n    card_ = nullptr;\n    releaseSpiBus();\n    disableStoragePower();\n    return false;\n  }\n\n  if (mkdir(kDataDirectory, 0775) != 0 && errno != EEXIST) {\n    write_errors_.fetch_add(1U, std::memory_order_relaxed);\n    ESP_LOGW(kTag, "Failed to create %s: errno=%d", kDataDirectory, errno);\n    closeMountedStorage();\n    return false;\n  }\n\n  mounted_.store(true, std::memory_order_relaxed);\n  ESP_LOGI(kTag, "SD mounted on SPI3 MOSI=%d MISO=%d CLK=%d CS=%d POWER=%d", pins_.mosi, pins_.miso,\n           pins_.sclk, pins_.cs, pins_.power);\n  return openSession(snapshot);\n}\n'''
cpp_text = replace_once(cpp_text, old_mount, new_mount, 'mountStorage')

cpp_text = replace_once(
    cpp_text,
    '''      ",\\\"sd_spi\\\":{\\\"host\\\":2,\\\"mosi\\\":%d,\\\"miso\\\":%d,\\\"clk\\\":%d,\\\"cs\\\":%d,\\\"power\\\":%d}}\\n",\n      firmware_sha_, session_id_, snapshot.reset_reason, snapshot.uptime_ms,\n      snapshot.rtc_trusted ? "true" : "false", snapshot.unix_time_s, pins_.mosi, pins_.miso,\n''',
    '''      ",\\\"sd_spi\\\":{\\\"host\\\":%d,\\\"mosi\\\":%d,\\\"miso\\\":%d,\\\"clk\\\":%d,\\\"cs\\\":%d,\\\"power\\\":%d}}\\n",\n      firmware_sha_, session_id_, snapshot.reset_reason, snapshot.uptime_ms,\n      snapshot.rtc_trusted ? "true" : "false", snapshot.unix_time_s, static_cast<int>(kSdSpiHost), pins_.mosi, pins_.miso,\n''',
    'session host metadata',
)

old_close = '''void Stage27SdDataLogger::closeMountedStorage() noexcept {\n  if (file_ != nullptr) {\n    std::fclose(file_);\n    file_ = nullptr;\n  }\n  if (card_ != nullptr) {\n    esp_vfs_fat_sdcard_unmount(kMountPoint, card_);\n    card_ = nullptr;\n  }\n  mounted_.store(false, std::memory_order_relaxed);\n}\n'''

new_close = '''void Stage27SdDataLogger::closeMountedStorage() noexcept {\n  if (file_ != nullptr) {\n    std::fclose(file_);\n    file_ = nullptr;\n  }\n  if (card_ != nullptr) {\n    esp_vfs_fat_sdcard_unmount(kMountPoint, card_);\n    card_ = nullptr;\n  }\n  mounted_.store(false, std::memory_order_relaxed);\n  releaseSpiBus();\n  disableStoragePower();\n}\n\nbool Stage27SdDataLogger::enableStoragePower() noexcept {\n  if (pins_.power < 0) {\n    return true;\n  }\n  const esp_err_t error = gpio_set_level(static_cast<gpio_num_t>(pins_.power), 1);\n  if (error != ESP_OK) {\n    ESP_LOGW(kTag, "Failed to enable SD power GPIO %d: %s", pins_.power, esp_err_to_name(error));\n    return false;\n  }\n  vTaskDelay(pdMS_TO_TICKS(kPowerOnDelayMs));\n  return true;\n}\n\nvoid Stage27SdDataLogger::disableStoragePower() noexcept {\n  if (pins_.power < 0) {\n    return;\n  }\n  const esp_err_t error = gpio_set_level(static_cast<gpio_num_t>(pins_.power), 0);\n  if (error != ESP_OK) {\n    ESP_LOGW(kTag, "Failed to disable SD power GPIO %d: %s", pins_.power, esp_err_to_name(error));\n  }\n}\n\nvoid Stage27SdDataLogger::releaseSpiBus() noexcept {\n  if (!spi_initialized_) {\n    return;\n  }\n  const esp_err_t error = spi_bus_free(kSdSpiHost);\n  if (error == ESP_OK) {\n    spi_initialized_ = false;\n    return;\n  }\n  ESP_LOGW(kTag, "SPI3 bus release failed: %s", esp_err_to_name(error));\n}\n'''
cpp_text = replace_once(cpp_text, old_close, new_close, 'closeMountedStorage')

hdr_text = replace_once(
    hdr_text,
    '''  void closeMountedStorage() noexcept;\n''',
    '''  void closeMountedStorage() noexcept;\n  bool enableStoragePower() noexcept;\n  void disableStoragePower() noexcept;\n  void releaseSpiBus() noexcept;\n''',
    'header helpers',
)

cpp.write_text(cpp_text)
hdr.write_text(hdr_text)
