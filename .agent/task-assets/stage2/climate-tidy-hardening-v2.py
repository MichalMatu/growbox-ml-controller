#!/usr/bin/env python3
from pathlib import Path

root = Path.cwd()
encoder = root / "lib/environment_control/src/climate/ClimateFeatureEncoder.cpp"
text = encoder.read_text(encoding="utf-8")
for old, new in {
    """    if (clipped != raw)\n      r_.clamped_feature_mask |= std::uint64_t{1U} << i;\n""": """    if (clipped != raw) {\n      r_.clamped_feature_mask |= std::uint64_t{1U} << i;\n    }\n""",
    """  if (report)\n    *report = local;\n""": """  if (report) {\n    *report = local;\n  }\n""",
}.items():
    if old not in text:
        raise SystemExit(f"encoder tidy anchor not found: {old!r}")
    text = text.replace(old, new)
encoder.write_text(text, encoding="utf-8")

trend = root / "lib/environment_control/src/climate/ClimateTrendEstimator.cpp"
text = trend.read_text(encoding="utf-8")
replacements = {
    """  while (first < size_ && newest - samples_[first].timestamp_ms > kWindowMs)\n    ++first;\n""": """  while (first < size_ && newest - samples_[first].timestamp_ms > kWindowMs) {\n    ++first;\n  }\n""",
    """  for (std::size_t i = first; i < size_; ++i)\n    samples_[i - first] = samples_[i];\n""": """  for (std::size_t i = first; i < size_; ++i) {\n    samples_[i - first] = samples_[i];\n  }\n""",
    """  if (size_ > 0U && ts < samples_[size_ - 1U].timestamp_ms)\n    reset();\n""": """  if (size_ > 0U && ts < samples_[size_ - 1U].timestamp_ms) {\n    reset();\n  }\n""",
    """    if (ts - last.timestamp_ms < kMinimumSampleSpacingMs)\n      return;\n""": """    if (ts - last.timestamp_ms < kMinimumSampleSpacingMs) {\n      return;\n    }\n""",
    """    for (std::size_t i = 1U; i < size_; ++i)\n      samples_[i - 1U] = samples_[i];\n""": """    for (std::size_t i = 1U; i < size_; ++i) {\n      samples_[i - 1U] = samples_[i];\n    }\n""",
    """  if (size_ < 2U)\n    return {};\n""": """  if (size_ < 2U) {\n    return {};\n  }\n""",
    """  if (span < kMinimumTrendSpanMs)\n    return {};\n""": """  if (span < kMinimumTrendSpanMs) {\n    return {};\n  }\n""",
    """  if (std::abs(d) < 1e-12)\n    return {};\n""": """  if (std::abs(d) < 1e-12) {\n    return {};\n  }\n""",
    """  if (!m.valid || m.age_ms > timeout || !std::isfinite(m.value) || m.age_ms > now)\n    return {};\n""": """  if (!m.valid || m.age_ms > timeout || !std::isfinite(m.value) || m.age_ms > now) {\n    return {};\n  }\n""",
    """  if (has_monotonic_ && now < last_monotonic_ms_)\n    reset();\n""": """  if (has_monotonic_ && now < last_monotonic_ms_) {\n    reset();\n  }\n""",
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f"trend tidy anchor not found: {old!r}")
    text = text.replace(old, new)
trend.write_text(text, encoding="utf-8")

script = root / "scripts/run_clang_tidy_host.sh"
text = script.read_text(encoding="utf-8")
old = '''for file in "${SOURCES[@]}"; do\n  echo "clang-tidy: ${file}"\n  "${CLANG_TIDY_BIN}" -p "${BUILD_DIR}" "${file}" --quiet "${EXTRA_TIDY_ARGS[@]}"\ndone\n'''
new = '''for file in "${SOURCES[@]}"; do\n  echo "clang-tidy: ${file}"\n  if [[ "${file}" == lib/environment_control/src/climate/* ]]; then\n    "${CLANG_TIDY_BIN}" -p "${BUILD_DIR}" "${file}" --quiet \\\n      --warnings-as-errors=readability-braces-around-statements "${EXTRA_TIDY_ARGS[@]}"\n  else\n    "${CLANG_TIDY_BIN}" -p "${BUILD_DIR}" "${file}" --quiet "${EXTRA_TIDY_ARGS[@]}"\n  fi\ndone\n'''
if old not in text:
    raise SystemExit("clang-tidy loop anchor not found")
script.write_text(text.replace(old, new), encoding="utf-8")
print("climate v6 clang-tidy hardening v2 applied")
