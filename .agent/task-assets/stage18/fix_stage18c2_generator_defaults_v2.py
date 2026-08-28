from __future__ import annotations

from pathlib import Path

path = Path("tools/ml/generate_climate_runtime_parity.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "from dataclasses import dataclass, replace",
    "from dataclasses import dataclass, field, replace",
    1,
)
start = "    state: ClimateState = ClimateState(\n"
end = "        light_level=0.6,\n    )\n    humidity_mode: str = \"RH\"\n"
if start not in text:
    raise SystemExit("Stage18C2 ClimateState default start not found")
if end not in text:
    raise SystemExit("Stage18C2 ClimateState default end not found")
text = text.replace(
    start,
    "    state: ClimateState = field(default_factory=lambda: ClimateState(\n",
    1,
)
text = text.replace(
    end,
    "        light_level=0.6,\n    ))\n    humidity_mode: str = \"RH\"\n",
    1,
)
path.write_text(text, encoding="utf-8")
