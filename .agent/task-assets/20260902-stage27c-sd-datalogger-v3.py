from pathlib import Path

path = Path("src/climate/storage/Stage27SdDataLogger.cpp")
text = path.read_text(encoding="utf-8")
text = text.replace('#include <cerrno>\n', '#include <cerrno>\n#include <cinttypes>\n', 1)
text = text.replace('slot_config.gpio_cs = pins_.cs;', 'slot_config.gpio_cs = static_cast<gpio_num_t>(pins_.cs);', 1)
text = text.replace(
    '"%s/session-%llu-%08x.ndjson",\n                  kDataDirectory, static_cast<unsigned long long>(snapshot.unix_time_s),\n                  session_id_)',
    '"%s/session-%" PRIu64 "-%08" PRIx32 ".ndjson", kDataDirectory, snapshot.unix_time_s,\n                  session_id_)',
    1,
)
text = text.replace(
    '"%s/session-u%llu-%08x.ndjson",\n                  kDataDirectory, static_cast<unsigned long long>(snapshot.uptime_ms), session_id_)',
    '"%s/session-u%" PRIu64 "-%08" PRIx32 ".ndjson", kDataDirectory, snapshot.uptime_ms,\n                  session_id_)',
    1,
)
text = text.replace(
    '"{\\"type\\":\\"session\\",\\"schema\\":\\"growbox-log-v1\\",\\"firmware_sha\\":\\"%s\\","\n      "\\"session_id\\":\\"%08x\\",\\"reset_reason\\":%d,\\"start_uptime_ms\\":%llu,"\n      "\\"rtc_trusted\\":%s,\\"start_unix_time_s\\":%llu,"\n      "\\"sd_spi\\":{\\"host\\":2,\\"mosi\\":%d,\\"miso\\":%d,\\"clk\\":%d,\\"cs\\":%d}}\\n",\n      firmware_sha_, session_id_, snapshot.reset_reason,\n      static_cast<unsigned long long>(snapshot.uptime_ms), snapshot.rtc_trusted ? "true" : "false",\n      static_cast<unsigned long long>(snapshot.unix_time_s), pins_.mosi, pins_.miso, pins_.sclk,\n      pins_.cs)',
    '"{\\"type\\":\\"session\\",\\"schema\\":\\"growbox-log-v1\\",\\"firmware_sha\\":\\"%s\\","\n      "\\"session_id\\":\\"%08" PRIx32 "\\",\\"reset_reason\\":%" PRId32\n      ",\\"start_uptime_ms\\":%" PRIu64 ",\\"rtc_trusted\\":%s,\\"start_unix_time_s\\":%" PRIu64\n      ",\\"sd_spi\\":{\\"host\\":2,\\"mosi\\":%d,\\"miso\\":%d,\\"clk\\":%d,\\"cs\\":%d}}\\n",\n      firmware_sha_, session_id_, snapshot.reset_reason, snapshot.uptime_ms,\n      snapshot.rtc_trusted ? "true" : "false", snapshot.unix_time_s, pins_.mosi, pins_.miso,\n      pins_.sclk, pins_.cs)',
    1,
)
path.write_text(text, encoding="utf-8")

required = [
    '#include <cinttypes>',
    'static_cast<gpio_num_t>(pins_.cs)',
    'PRIu64',
    'PRIx32',
    'PRId32',
]
updated = path.read_text(encoding="utf-8")
for token in required:
    if token not in updated:
        raise RuntimeError(f"missing expected v3 token: {token}")
