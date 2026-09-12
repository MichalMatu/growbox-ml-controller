from pathlib import Path

for path in (
    Path("src/climate/ClimateObservabilityMetrics.cpp"),
    Path("src/climate/ClimateObservabilityMetrics.h"),
    Path("test/test_climate_observability_metrics/test_main.cpp"),
):
    if not path.is_file():
        raise SystemExit(f"expected file missing: {path}")
    path.unlink()

Path("test/test_climate_observability_metrics").rmdir()

src_cmake = Path("src/CMakeLists.txt")
text = src_cmake.read_text()
line = '    "climate/ClimateObservabilityMetrics.cpp"\n'
if text.count(line) != 1:
    raise SystemExit("unexpected src/CMakeLists.txt observability source count")
src_cmake.write_text(text.replace(line, ""))

host_cmake = Path("test/host/CMakeLists.txt")
text = host_cmake.read_text()
start_marker = "add_executable(\n  climate_observability_metrics_tests"
next_marker = "add_executable(\n  europe_warsaw_time_tests"
if text.count(start_marker) != 1 or text.count(next_marker) != 1:
    raise SystemExit("unexpected host CMake observability block")
start = text.index(start_marker)
end = text.index(next_marker, start)
text = text[:start] + text[end:]
for line in (
    "  target_link_libraries(climate_observability_metrics_tests PRIVATE m)\n",
    "add_test(NAME climate_observability_metrics_tests COMMAND climate_observability_metrics_tests)\n",
):
    if text.count(line) != 1:
        raise SystemExit(f"unexpected host CMake line count: {line.strip()}")
    text = text.replace(line, "")
host_cmake.write_text(text)
