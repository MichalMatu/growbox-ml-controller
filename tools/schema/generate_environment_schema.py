#!/usr/bin/env python3
"""Generate the deterministic C++ environment schema contract header."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = ROOT / "schemas" / "environment-controller.json"
DEFAULT_OUTPUT = ROOT / "lib" / "environment_control" / "src" / "EnvironmentSchema.h"
MAX_FEATURE_COUNT = 128


def canonical_bytes(document: dict[str, Any]) -> bytes:
    """Return the canonical bytes used everywhere to identify the contract."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def schema_hash(document: dict[str, Any]) -> str:
    length = int(document["hash"]["short_hex_characters"])
    return hashlib.sha256(canonical_bytes(document)).hexdigest()[:length]


def cpp_identifier(name: str) -> str:
    pieces = re.findall(r"[A-Za-z0-9]+", name)
    identifier = "".join(piece[:1].upper() + piece[1:] for piece in pieces)
    if not identifier:
        raise ValueError(f"cannot form C++ identifier from {name!r}")
    if identifier[0].isdigit():
        identifier = f"N{identifier}"
    return identifier


def cpp_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def cpp_float(value: float) -> str:
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError("schema numeric literals must be finite")
    rendered = f"{numeric:.9g}"
    if "." not in rendered and "e" not in rendered.lower():
        rendered += ".0"
    return rendered + "f"


def _validate_ranges(entries: list[dict[str, Any]]) -> None:
    for item in entries:
        minimum = float(item["minimum"])
        maximum = float(item["maximum"])
        default = float(item["default"])
        if not all(math.isfinite(value) for value in (minimum, maximum, default)):
            raise ValueError(f"non-finite range for {item.get('name')!r}")
        if minimum > maximum:
            raise ValueError(f"invalid range for {item.get('name')!r}")
        if not minimum <= default <= maximum:
            raise ValueError(f"default out of range for {item.get('name')!r}")


def _validate_hash_contract(document: dict[str, Any]) -> None:
    hash_contract = document.get("hash")
    if not isinstance(hash_contract, dict):
        raise ValueError("hash contract metadata is required")
    if hash_contract.get("algorithm") != "sha256":
        raise ValueError("hash.algorithm must be sha256")
    if hash_contract.get("canonicalization") != (
        "UTF-8 JSON with lexicographically sorted keys and separators ',' and ':'"
    ):
        raise ValueError("unsupported hash canonicalization")
    hash_length = hash_contract.get("short_hex_characters")
    if not isinstance(hash_length, int) or not 1 <= hash_length <= 64:
        raise ValueError("hash.short_hex_characters must be in [1, 64]")


def validate(document: dict[str, Any]) -> None:
    version = document.get("schema_version")
    if version != 4:
        raise ValueError("schema_version must be 4 (active pots contract)")
    _validate_hash_contract(document)

    features = document["model"]["features"]
    outputs = document["model"]["outputs"]
    feature_names = [item["name"] for item in features]
    feature_paths = [item.get("path") for item in features]
    output_names = [item["name"] for item in outputs]
    if len(feature_names) != len(set(feature_names)):
        raise ValueError("model feature names must be unique")
    if len(output_names) != len(set(output_names)):
        raise ValueError("model output names must be unique")
    if any(not isinstance(path, str) or not path for path in feature_paths):
        raise ValueError("every model feature must have a non-empty path")
    if len(feature_paths) != len(set(feature_paths)):
        raise ValueError("model feature paths must be unique")
    if any("source" in item for item in features):
        raise ValueError("model features must use path, not source")
    if len(features) > MAX_FEATURE_COUNT:
        raise ValueError(f"feature count must be <= {MAX_FEATURE_COUNT}")

    features_by_name = {item["name"]: item for item in features}
    sections = document.get("group_sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("contract must define group_sections")
    grouped = [name for section in sections for name in section["features"]]
    if grouped != feature_names:
        raise ValueError("group_sections must enumerate features once and in model order")
    for section in sections:
        group_path = section["path"]
        expected_prefix = group_path.split(".")
        for name in section["features"]:
            path = features_by_name[name]["path"]
            if path.split(".")[:-1] != expected_prefix:
                raise ValueError(f"feature path {path!r} does not match group {group_path!r}")

    _validate_ranges(features)
    _validate_ranges(outputs)


def array(values: list[str], indentation: str = "    ") -> str:
    return "\n".join(f"{indentation}{value}," for value in values)


def _binary_pwm_encoding(features: list[dict[str, Any]]) -> dict[str, float]:
    for item in features:
        if item.get("type") != "enum":
            continue
        encoding = item.get("encoding")
        if isinstance(encoding, dict) and "binary" in encoding and "pwm" in encoding:
            return encoding
    return {"binary": 0.0, "pwm": 1.0}


def _safety_constant_lines(safety: dict[str, Any]) -> str:
    lines = [
        f"inline constexpr float kDefaultMaximumAirTemperatureC = "
        f"{cpp_float(safety['maximum_air_temperature_c'])};",
        f"inline constexpr float kDefaultAlarmAirTemperatureC = "
        f"{cpp_float(safety['alarm_air_temperature_c'])};",
        f"inline constexpr float kDefaultAlarmMinimumFan = "
        f"{cpp_float(safety['alarm_minimum_fan'])};",
        f"inline constexpr float kDefaultBinaryThreshold = "
        f"{cpp_float(safety['binary_threshold'])};",
        f"inline constexpr float kDefaultHeaterMinimumOnS = "
        f"{cpp_float(safety['heater_minimum_on_s'])};",
        f"inline constexpr float kDefaultHeaterMinimumOffS = "
        f"{cpp_float(safety['heater_minimum_off_s'])};",
        f"inline constexpr float kDefaultHumidifierMinimumOnS = "
        f"{cpp_float(safety['humidifier_minimum_on_s'])};",
        f"inline constexpr float kDefaultHumidifierMinimumOffS = "
        f"{cpp_float(safety['humidifier_minimum_off_s'])};",
    ]
    optional = (
        ("dehumidifier_minimum_on_s", "DehumidifierMinimumOnS"),
        ("dehumidifier_minimum_off_s", "DehumidifierMinimumOffS"),
        ("cooler_minimum_on_s", "CoolerMinimumOnS"),
        ("cooler_minimum_off_s", "CoolerMinimumOffS"),
        ("co2_doser_minimum_interval_s", "Co2DoserMinimumIntervalS"),
        ("co2_doser_maximum_pulse_s", "Co2DoserMaximumPulseS"),
        ("fan_venting_co2_threshold", "FanVentingCo2Threshold"),
        ("maximum_nutrient_soil_delta_c", "MaximumNutrientSoilDeltaC"),
        ("minimum_nutrient_solution_temperature_c", "MinimumNutrientSolutionTemperatureC"),
    )
    for key, suffix in optional:
        if key in safety:
            lines.append(f"inline constexpr float kDefault{suffix} = {cpp_float(safety[key])};")
    return "\n".join(lines)


def render(document: dict[str, Any]) -> str:
    validate(document)
    features = document["model"]["features"]
    outputs = document["model"]["outputs"]
    digest = schema_hash(document)

    feature_enum = array(
        [f"{cpp_identifier(item['name'])} = {index}" for index, item in enumerate(features)]
    )
    output_enum = array(
        [f"{cpp_identifier(item['name'])} = {index}" for index, item in enumerate(outputs)]
    )
    feature_names = array([cpp_string(item["name"]) for item in features], "        ")
    feature_paths = array([cpp_string(item["path"]) for item in features], "        ")
    feature_wire_keys = array(
        [cpp_string(item["path"].rsplit(".", 1)[1]) for item in features], "        "
    )
    feature_units = array([cpp_string(item["unit"]) for item in features], "        ")
    feature_mins = array([cpp_float(item["minimum"]) for item in features], "        ")
    feature_maxes = array([cpp_float(item["maximum"]) for item in features], "        ")
    feature_defaults = array([cpp_float(item["default"]) for item in features], "        ")
    output_names = array([cpp_string(item["name"]) for item in outputs], "        ")
    output_mins = array([cpp_float(item["minimum"]) for item in outputs], "        ")
    output_maxes = array([cpp_float(item["maximum"]) for item in outputs], "        ")
    output_defaults = array([cpp_float(item["default"]) for item in outputs], "        ")

    path_parts = [item["path"].split(".") for item in features]
    wire_roots = list(dict.fromkeys(parts[0] for parts in path_parts))
    wire_objects = list(
        dict.fromkeys(
            parts[1] for parts in path_parts if len(parts) >= 3 and not parts[1].isdigit()
        )
    )
    wire_root_constants = "\n".join(
        f"inline constexpr char kWireRoot{cpp_identifier(key)}[] = {cpp_string(key)};"
        for key in wire_roots
    )
    wire_object_constants = "\n".join(
        f"inline constexpr char kWireObject{cpp_identifier(key)}[] = {cpp_string(key)};"
        for key in wire_objects
    )

    safety = document["safety_defaults"]
    heater_control = _binary_pwm_encoding(features)
    heater_binary = int(heater_control["binary"])
    heater_pwm = int(heater_control["pwm"])
    if float(heater_binary) != float(heater_control["binary"]) or not 0 <= heater_binary <= 255:
        raise ValueError("binary encoding must be an unsigned 8-bit integer")
    if float(heater_pwm) != float(heater_control["pwm"]) or not 0 <= heater_pwm <= 255:
        raise ValueError("pwm encoding must be an unsigned 8-bit integer")

    return f"""// Generated by tools/schema/generate_environment_schema.py. Do not edit.
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace growbox {{
namespace control {{
namespace schema {{

inline constexpr std::uint32_t kSchemaVersion = {document["schema_version"]}U;
inline constexpr char kSchemaId[] = {cpp_string(document["schema_id"])};
inline constexpr char kSchemaHash[] = {cpp_string(digest)};
inline constexpr std::size_t kFeatureCount = {len(features)}U;
inline constexpr std::size_t kOutputCount = {len(outputs)}U;
inline constexpr std::size_t kFeatureDiagnosticsMaskBits = 128U;
inline constexpr std::uint8_t kHeaterControlTypeBinary = {heater_binary}U;
inline constexpr std::uint8_t kHeaterControlTypePwm = {heater_pwm}U;

{wire_root_constants}
{wire_object_constants}

enum class FeatureIndex : std::size_t {{
{feature_enum}
}};

enum class OutputIndex : std::size_t {{
{output_enum}
}};

inline constexpr std::array<const char*, kFeatureCount> kFeatureNames{{{{
{feature_names}
}}}};

inline constexpr std::array<const char*, kFeatureCount> kFeaturePaths{{{{
{feature_paths}
}}}};

inline constexpr std::array<const char*, kFeatureCount> kFeatureWireKeys{{{{
{feature_wire_keys}
}}}};

inline constexpr std::array<const char*, kFeatureCount> kFeatureUnits{{{{
{feature_units}
}}}};

inline constexpr std::array<float, kFeatureCount> kFeatureMinimums{{{{
{feature_mins}
}}}};

inline constexpr std::array<float, kFeatureCount> kFeatureMaximums{{{{
{feature_maxes}
}}}};

inline constexpr std::array<float, kFeatureCount> kFeatureDefaults{{{{
{feature_defaults}
}}}};

inline constexpr std::array<const char*, kOutputCount> kOutputNames{{{{
{output_names}
}}}};

inline constexpr std::array<float, kOutputCount> kOutputMinimums{{{{
{output_mins}
}}}};

inline constexpr std::array<float, kOutputCount> kOutputMaximums{{{{
{output_maxes}
}}}};

inline constexpr std::array<float, kOutputCount> kOutputDefaults{{{{
{output_defaults}
}}}};

{_safety_constant_lines(safety)}

constexpr std::size_t index(FeatureIndex value) noexcept {{
    return static_cast<std::size_t>(value);
}}

constexpr std::size_t index(OutputIndex value) noexcept {{
    return static_cast<std::size_t>(value);
}}

constexpr const char* wireKey(FeatureIndex value) noexcept {{
    return kFeatureWireKeys[index(value)];
}}

}}  // namespace schema
}}  // namespace control
}}  // namespace growbox
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    document = json.loads(args.schema.read_text(encoding="utf-8"))
    generated = render(document)
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != generated:
            raise SystemExit(f"generated schema header is stale: {args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    print(f"wrote {args.output} hash={schema_hash(document)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
