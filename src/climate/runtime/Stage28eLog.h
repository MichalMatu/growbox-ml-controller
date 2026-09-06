#pragma once

#include "climate/runtime/Stage28eDiagnosticsCore.h"

#include <cstdint>

#ifndef GROWBOX_STAGE28E_LOG_COMPILE_LEVEL
#define GROWBOX_STAGE28E_LOG_COMPILE_LEVEL 2
#endif

static_assert(GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 0 && GROWBOX_STAGE28E_LOG_COMPILE_LEVEL <= 4,
              "GROWBOX_STAGE28E_LOG_COMPILE_LEVEL must be 0..4");

namespace growbox::app::climate_io::runtime {

void configureStage28eLogging(const BootIdentity& boot) noexcept;
void setStage28eLogLevel(DiagnosticLogModule module, DiagnosticLogLevel level) noexcept;
DiagnosticLogLevel stage28eLogLevel(DiagnosticLogModule module) noexcept;
void stage28eLogWrite(DiagnosticLogModule module, DiagnosticLogLevel level,
                      const char* format, ...) noexcept;

} // namespace growbox::app::climate_io::runtime

#if GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 0
#define GROWBOX_STAGE28E_LOG_ERROR(module, ...) \
  do { ::growbox::app::climate_io::runtime::stage28eLogWrite( \
      (module), ::growbox::app::climate_io::runtime::DiagnosticLogLevel::Error, __VA_ARGS__); } while (0)
#else
#define GROWBOX_STAGE28E_LOG_ERROR(module, ...) do { } while (0)
#endif

#if GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 1
#define GROWBOX_STAGE28E_LOG_WARN(module, ...) \
  do { ::growbox::app::climate_io::runtime::stage28eLogWrite( \
      (module), ::growbox::app::climate_io::runtime::DiagnosticLogLevel::Warn, __VA_ARGS__); } while (0)
#else
#define GROWBOX_STAGE28E_LOG_WARN(module, ...) do { } while (0)
#endif

#if GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 2
#define GROWBOX_STAGE28E_LOG_INFO(module, ...) \
  do { ::growbox::app::climate_io::runtime::stage28eLogWrite( \
      (module), ::growbox::app::climate_io::runtime::DiagnosticLogLevel::Info, __VA_ARGS__); } while (0)
#else
#define GROWBOX_STAGE28E_LOG_INFO(module, ...) do { } while (0)
#endif

#if GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 3
#define GROWBOX_STAGE28E_LOG_DEBUG(module, ...) \
  do { ::growbox::app::climate_io::runtime::stage28eLogWrite( \
      (module), ::growbox::app::climate_io::runtime::DiagnosticLogLevel::Debug, __VA_ARGS__); } while (0)
#else
#define GROWBOX_STAGE28E_LOG_DEBUG(module, ...) do { } while (0)
#endif

#if GROWBOX_STAGE28E_LOG_COMPILE_LEVEL >= 4
#define GROWBOX_STAGE28E_LOG_TRACE(module, ...) \
  do { ::growbox::app::climate_io::runtime::stage28eLogWrite( \
      (module), ::growbox::app::climate_io::runtime::DiagnosticLogLevel::Trace, __VA_ARGS__); } while (0)
#else
#define GROWBOX_STAGE28E_LOG_TRACE(module, ...) do { } while (0)
#endif
