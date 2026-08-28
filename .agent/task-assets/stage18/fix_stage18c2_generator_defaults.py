from __future__ import annotations

from pathlib import Path

path = Path("tools/ml/generate_climate_runtime_parity.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "from dataclasses import dataclass, replace",
    "from dataclasses import dataclass, field, replace",
    1,
)
old = '''        state: ClimateState = ClimateState(
            air_temperature_c=18.0,
            relative_humidity_pct=60.0,
            co2_ppm=500.0,
            outside_temperature_c=10.0,
            outside_humidity_pct=50.0,
            light_level=0.6,
        )
'''
new = '''        state: ClimateState = field(
            default_factory=lambda: ClimateState(
                air_temperature_c=18.0,
                relative_humidity_pct=60.0,
                co2_ppm=500.0,
                outside_temperature_c=10.0,
                outside_humidity_pct=50.0,
                light_level=0.6,
            )
        )
'''
if old not in text:
    raise SystemExit("Stage18C2 ClimateState default block not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
