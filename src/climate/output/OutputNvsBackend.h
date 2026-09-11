#pragma once

#include "climate/output/OutputPersistenceStore.h"

namespace growbox::app::output {

inline constexpr char kOutputNvsNamespace[] = "growbox_out";
inline constexpr char kOutputNvsSnapshotKey[] = "snapshot";

class OutputNvsBackend final : public OutputPersistenceBackend {
public:
  OutputPersistenceBackendStatus read(OutputPersistenceBlob& blob,
                                      std::size_t& stored_size) noexcept override;
  OutputPersistenceBackendStatus write(const OutputPersistenceBlob& blob) noexcept override;
};

} // namespace growbox::app::output
