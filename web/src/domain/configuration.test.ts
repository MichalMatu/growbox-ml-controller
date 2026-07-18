import { readFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { describe, expect, it } from "vitest"

import {
  buildExportConfiguration,
  createDefaultConfiguration,
  importConfiguration,
  normalizeConfiguration,
  parseConfigurationJson,
  updateFeatureValue,
  validateImportedConfiguration,
} from "./configuration"
import { getValueAtPath, setValueAtPath } from "./paths"
import { schema } from "./schema"
import type { Configuration, JsonValue } from "./types"

const root = join(dirname(fileURLToPath(import.meta.url)), "../../..")
const golden = JSON.parse(
  readFileSync(join(root, "docs/examples/minimal-single-pot.json"), "utf8"),
) as Configuration

function clone<T>(value: T): T {
  return structuredClone(value)
}

describe("default and golden export shape", () => {
  it("builds a default configuration covering every v4 feature path", () => {
    const configuration = createDefaultConfiguration()
    expect(Array.isArray(configuration.pots)).toBe(true)
    expect((configuration.pots as unknown[]).length).toBe(4)

    for (const feature of schema.model.features) {
      expect(getValueAtPath(configuration, feature.path)).toBeDefined()
    }
  })

  it("accepts the golden example without errors", () => {
    expect(validateImportedConfiguration(golden)).toEqual([])
    const result = importConfiguration(golden)
    expect(result.success).toBe(true)
  })

  it("round-trips golden through normalize without inventing forbidden keys", () => {
    const exported = buildExportConfiguration(golden)
    expect(exported.actuators && typeof exported.actuators === "object").toBe(true)
    expect(
      exported.actuators &&
        typeof exported.actuators === "object" &&
        "lights" in exported.actuators,
    ).toBe(false)

    for (const feature of schema.model.features) {
      if (feature.path.startsWith("previous.") || /^pots\.\d+\.previous\./.test(feature.path)) {
        expect(getValueAtPath(exported, feature.path)).toBe(0)
      }
    }
  })
})

describe("inactive pot and module rules", () => {
  it("zeros irrigation capability when irrigation is unavailable on an active pot", () => {
    let configuration = clone(golden)
    configuration = setValueAtPath(configuration, "pots.0.irrigation.available", false)
    configuration = setValueAtPath(configuration, "pots.0.irrigation.flow_ml_s", 18)
    configuration = setValueAtPath(configuration, "pots.0.irrigation.maximum_pulse_s", 4)
    configuration = setValueAtPath(configuration, "pots.0.irrigation.minimum_interval_s", 300)

    const exported = buildExportConfiguration(configuration)
    expect(getValueAtPath(exported, "pots.0.irrigation.available")).toBe(false)
    expect(getValueAtPath(exported, "pots.0.irrigation.flow_ml_s")).toBe(0)
    expect(getValueAtPath(exported, "pots.0.irrigation.maximum_pulse_s")).toBe(0)
    expect(getValueAtPath(exported, "pots.0.irrigation.minimum_interval_s")).toBe(0)
  })

  it("forces full inactive-pot cascade on export", () => {
    let configuration = clone(golden)
    configuration = setValueAtPath(configuration, "pots.0.available", false)
    configuration = setValueAtPath(configuration, "pots.0.validity.soil_moisture_pct", true)
    configuration = setValueAtPath(configuration, "pots.0.validity.soil_temperature_c", true)
    configuration = setValueAtPath(configuration, "pots.0.irrigation.available", true)
    configuration = setValueAtPath(configuration, "pots.0.irrigation.flow_ml_s", 12)
    configuration = setValueAtPath(configuration, "pots.0.heat_mat.available", true)
    configuration = setValueAtPath(configuration, "pots.0.heat_mat.max_power_w", 40)
    configuration = setValueAtPath(configuration, "pots.0.previous.irrigation", 0.5)

    const exported = buildExportConfiguration(configuration)
    expect(getValueAtPath(exported, "pots.0.available")).toBe(false)
    expect(getValueAtPath(exported, "pots.0.validity.soil_moisture_pct")).toBe(false)
    expect(getValueAtPath(exported, "pots.0.validity.soil_temperature_c")).toBe(false)
    expect(getValueAtPath(exported, "pots.0.irrigation.available")).toBe(false)
    expect(getValueAtPath(exported, "pots.0.irrigation.flow_ml_s")).toBe(0)
    expect(getValueAtPath(exported, "pots.0.heat_mat.available")).toBe(false)
    expect(getValueAtPath(exported, "pots.0.heat_mat.max_power_w")).toBe(0)
    expect(getValueAtPath(exported, "pots.0.previous.irrigation")).toBe(0)
    // cultivation may keep template numbers
    expect(getValueAtPath(exported, "pots.0.cultivation.pot_volume_l")).not.toBe(0)
  })

  it("rejects an import that violates inactive irrigation capability zeros", () => {
    const document = clone(golden)
    document.pots = clone(golden.pots)
    const pots = document.pots as Array<Record<string, JsonValue>>
    const pot0 = pots[0] as Record<string, JsonValue>
    pot0.irrigation = {
      available: false,
      flow_ml_s: 18,
      maximum_pulse_s: 0,
      minimum_interval_s: 0,
      control_type: "binary",
    }

    const errors = validateImportedConfiguration(document)
    expect(errors.some((error) => error.includes("flow_ml_s"))).toBe(true)
  })

  it("zeros global actuator capability fields when unavailable", () => {
    let configuration = clone(golden)
    configuration = setValueAtPath(configuration, "actuators.heater.available", false)
    configuration = setValueAtPath(configuration, "actuators.heater.max_power_w", 800)
    configuration = setValueAtPath(configuration, "actuators.heater.efficiency", 0.95)

    const exported = buildExportConfiguration(configuration)
    expect(getValueAtPath(exported, "actuators.heater.available")).toBe(false)
    expect(getValueAtPath(exported, "actuators.heater.max_power_w")).toBe(0)
    expect(getValueAtPath(exported, "actuators.heater.efficiency")).toBe(0)
  })
})

describe("clamps, enums, previous, and metadata", () => {
  it("clamps numeric feature updates to schema min/max", () => {
    const configuration = updateFeatureValue(
      createDefaultConfiguration(),
      "environment.growbox_volume_m3",
      9999,
    )
    const volume = getValueAtPath(configuration, "environment.growbox_volume_m3")
    const feature = schema.model.features.find(
      (item) => item.path === "environment.growbox_volume_m3",
    )
    expect(feature).toBeDefined()
    expect(volume).toBe(feature?.maximum)
  })

  it("preserves pot control_type enum strings", () => {
    const configuration = updateFeatureValue(
      createDefaultConfiguration(),
      "pots.0.irrigation.control_type",
      "pwm",
    )
    expect(getValueAtPath(configuration, "pots.0.irrigation.control_type")).toBe("pwm")
  })

  it("always zeros previous commands during normalize", () => {
    let configuration = clone(golden)
    configuration = setValueAtPath(configuration, "previous.heater", 0.4)
    configuration = setValueAtPath(configuration, "pots.0.previous.heat_mat", 0.2)
    const exported = normalizeConfiguration(configuration)
    expect(getValueAtPath(exported, "previous.heater")).toBe(0)
    expect(getValueAtPath(exported, "pots.0.previous.heat_mat")).toBe(0)
  })

  it("derives growbox volume from enclosure when present", () => {
    const configuration = normalizeConfiguration({
      ...clone(golden),
      enclosure: { width_cm: 100, depth_cm: 100, height_cm: 80 },
    })
    expect(getValueAtPath(configuration, "environment.growbox_volume_m3")).toBe(0.8)
    expect(configuration.enclosure).toEqual({
      width_cm: 100,
      depth_cm: 100,
      height_cm: 80,
    })
  })

  it("rejects unknown nested export paths on import", () => {
    const document = clone(golden) as Configuration & {
      actuators: Record<string, Record<string, JsonValue>>
    }
    document.actuators = {
      ...(document.actuators as Record<string, Record<string, JsonValue>>),
      heater: {
        ...(document.actuators.heater as Record<string, JsonValue>),
        control_type: "pwm",
      },
    }
    const errors = validateImportedConfiguration(document)
    expect(errors.some((error) => error.includes("control_type"))).toBe(true)
  })

  it("rejects invalid JSON text", () => {
    const result = parseConfigurationJson("{not-json")
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.errors[0]).toMatch(/valid JSON/i)
    }
  })
})
