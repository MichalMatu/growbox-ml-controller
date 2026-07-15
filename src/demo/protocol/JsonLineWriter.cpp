#include "JsonLineWriter.h"

#include <cJSON.h>
#include <driver/usb_serial_jtag.h>

#include <cstring>

namespace growbox {
namespace demo {
namespace wire {

void emitJsonDocument(cJSON* document) noexcept {
  if (document == nullptr) {
    return;
  }
  char* encoded = cJSON_PrintUnformatted(document);
  if (encoded != nullptr) {
    usb_serial_jtag_write_bytes(encoded, std::strlen(encoded), 0);
    usb_serial_jtag_write_bytes("\n", 1U, 0);
    cJSON_free(encoded);
  }
  cJSON_Delete(document);
}

}  // namespace wire
}  // namespace demo
}  // namespace growbox