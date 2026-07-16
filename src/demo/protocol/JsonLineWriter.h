#pragma once

struct cJSON;

namespace growbox {
namespace demo {
namespace wire {

void emitJsonDocument(cJSON* document) noexcept;

} // namespace wire
} // namespace demo
} // namespace growbox
