from pathlib import Path
import subprocess


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"expected one match in {path}, got {text.count(old)}")
    p.write_text(text.replace(old, new, 1))

# Reuse the already reviewed A4 v1 patch, then apply the exact ESP-IDF 5.5
# non-SMP core-ID correction proven by the API-contract task.
base = subprocess.check_output(
    ["git", "show", "origin/agent-control:.agent/payloads/20260906-growbox-stage28e-phase-a4-v1/run.py"],
    text=True,
)
exec(compile(base, "stage28e-a4-v1", "exec"))

replace_once(
    "src/climate/runtime/Stage28ServiceConsole.cpp",
    "#include <freertos/FreeRTOS.h>\n#include <freertos/task.h>\n",
    "#include <freertos/FreeRTOS.h>\n#include <freertos/idf_additions.h>\n#include <freertos/task.h>\n",
)
replace_once(
    "src/climate/runtime/Stage28ServiceConsole.cpp",
    "static_cast<unsigned long>(task.xTaskNumber), static_cast<long>(task.xCoreID),\n",
    "static_cast<unsigned long>(task.xTaskNumber),\n        static_cast<long>(xTaskGetCoreID(task.xHandle)),\n",
)
