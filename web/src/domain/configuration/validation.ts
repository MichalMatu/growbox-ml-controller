import { createSchemaDefaults, POT_COUNT } from "./defaults"
import { isJsonObject, getValueAtPath } from "../paths"
import { isAllowedEnumValue, schema } from "../schema"
import type { Configuration, JsonValue } from "../types"

const CONTRACT_ROOT_KEYS = [
  "environment",
  "sensors",
  "validity",
  "pseudo",
  "pots",
  "actuators",
  "targets",
  "previous",
] as const

const ROOT_META_KEYS = new Set(["seed", "profile_id", "title", "enclosure"])

function hasOwn(object: object, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(object, key)
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
}

function readEnclosure(value: JsonValue | undefined): { width_cm: number; depth_cm: number; height_cm: number } | null {
  if (!isJsonObject(value)) return null

  const keys = ["width_cm", "depth_cm", "height_cm"] as const
  if (
    Object.keys(value).length !== keys.length ||
    !keys.every((key) => hasOwn(value, key) && isFiniteNumber(value[key]) && value[key] > 0)
  ) {
    return null
  }

  return {
    width_cm: value.width_cm as number,
    depth_cm: value.depth_cm as number,
    height_cm: value.height_cm as number,
  }
}

function derivedVolume(dimensions: { width_cm: number; depth_cm: number; height_cm: number }): number {
  return (dimensions.width_cm * dimensions.depth_cm * dimensions.height_cm) / 1_000_000
}

function displayPath(path: string): string {
  return path.replace(/\.(\d+)(?=\.|$)/g, "[$1]")
}

function isGlobalCapabilityField(field: string): boolean {
  return (
    field === "efficiency" ||
    field.includes("dose") ||
    field.startsWith("max_") ||
    field.startsWith("maximum_")
  )
}

function validateShape(
  value: unknown,
  expected: JsonValue,
  path: string,
  errors: string[],
  isRoot = false,
): void {
  if (Array.isArray(expected)) {
    if (!Array.isArray(value)) {
      errors.push(`${path} must be an array.`)
      return
    }
    if (value.length !== expected.length) {
      errors.push(`${path} must contain exactly ${expected.length} entries.`)
    }
    expected.forEach((item, index) => {
      if (!hasOwn(value, String(index))) {
        errors.push(`${path}[${index}] is missing.`)
        return
      }
      validateShape(value[index], item, `${path}[${index}]`, errors)
    })
    return
  }

  if (isJsonObject(expected)) {
    if (!isJsonObject(value)) {
      errors.push(`${path} must be an object.`)
      return
    }
    for (const [key, expectedValue] of Object.entries(expected)) {
      if (!hasOwn(value, key)) {
        errors.push(`${path}.${key} is missing.`)
        continue
      }
      validateShape(value[key], expectedValue, `${path}.${key}`, errors)
    }
    for (const key of Object.keys(value)) {
      if (hasOwn(expected, key) || (isRoot && ROOT_META_KEYS.has(key))) continue
      errors.push(`${path}.${key} is not an allowed v4 export path.`)
    }
  }
}

function validateFeatureValues(configuration: Configuration, errors: string[]): void {
  for (const feature of schema.model.features) {
    const value = getValueAtPath(configuration, feature.path)
    if (feature.type === "boolean") {
      if (typeof value !== "boolean") {
        errors.push(`${displayPath(feature.path)} must be a boolean.`)
      }
      continue
    }

    if (feature.type === "enum") {
      if (!isAllowedEnumValue(feature, value)) {
        errors.push(`${displayPath(feature.path)} must be one of its enum strings.`)
      }
      continue
    }

    if (!isFiniteNumber(value)) {
      errors.push(`${displayPath(feature.path)} must be a finite number.`)
      continue
    }
    if (value < feature.minimum || value > feature.maximum) {
      errors.push(
        `${displayPath(feature.path)} must be within ${feature.minimum}–${feature.maximum}.`,
      )
    }
  }
}

function validateMetadata(configuration: Configuration, errors: string[]): void {
  if (hasOwn(configuration, "seed") && !Number.isInteger(configuration.seed)) {
    errors.push("seed must be an integer when present.")
  }
  for (const key of ["title", "profile_id"] as const) {
    if (hasOwn(configuration, key) && typeof configuration[key] !== "string") {
      errors.push(`${key} must be a string when present.`)
    }
  }

  if (!hasOwn(configuration, "enclosure")) return

  const enclosure = readEnclosure(configuration.enclosure)
  if (!enclosure) {
    errors.push("enclosure must contain only positive width_cm, depth_cm, and height_cm values.")
    return
  }

  const volume = getValueAtPath(configuration, "environment.growbox_volume_m3")
  const requiredVolume = derivedVolume(enclosure)
  const tolerance = Math.max(1e-9, Math.abs(requiredVolume) * 1e-9)
  if (!isFiniteNumber(volume) || Math.abs(volume - requiredVolume) > tolerance) {
    errors.push("environment.growbox_volume_m3 must equal the enclosure-derived volume.")
  }
}

function validateZero(value: JsonValue | undefined, path: string, errors: string[]): void {
  if (value !== 0) errors.push(`${path} must be 0 for a hardware-template export.`)
}

function validateSafetyInvariants(configuration: Configuration, errors: string[]): void {

  for (const feature of schema.model.features) {
    if (feature.path.startsWith("previous.") || /^pots\.\d+\.previous\./.test(feature.path)) {
      validateZero(getValueAtPath(configuration, feature.path), displayPath(feature.path), errors)
    }
  }

  for (let index = 0; index < POT_COUNT; index += 1) {
    const prefix = `pots.${index}`
    const displayPrefix = `pots[${index}]`
    const irrigationPrefix = `${prefix}.irrigation`
    const heatMatPrefix = `${prefix}.heat_mat`
    const irrigationUnavailable =
      getValueAtPath(configuration, `${irrigationPrefix}.available`) === false
    const heatMatUnavailable = getValueAtPath(configuration, `${heatMatPrefix}.available`) === false

    if (irrigationUnavailable) {
      for (const field of ["flow_ml_s", "maximum_pulse_s", "minimum_interval_s"]) {
        validateZero(
          getValueAtPath(configuration, `${irrigationPrefix}.${field}`),
          `${displayPrefix}.irrigation.${field}`,
          errors,
        )
      }
    }
    if (heatMatUnavailable) {
      validateZero(
        getValueAtPath(configuration, `${heatMatPrefix}.max_power_w`),
        `${displayPrefix}.heat_mat.max_power_w`,
        errors,
      )
    }

    if (getValueAtPath(configuration, `${prefix}.available`) !== false) continue
    if (getValueAtPath(configuration, `${prefix}.validity.soil_moisture_pct`) !== false) {
      errors.push(`${displayPrefix}.validity.soil_moisture_pct must be false when the pot is inactive.`)
    }
    if (getValueAtPath(configuration, `${prefix}.validity.soil_temperature_c`) !== false) {
      errors.push(`${displayPrefix}.validity.soil_temperature_c must be false when the pot is inactive.`)
    }
    if (!irrigationUnavailable) {
      errors.push(`${displayPrefix}.irrigation.available must be false when the pot is inactive.`)
    }
    if (!heatMatUnavailable) {
      errors.push(`${displayPrefix}.heat_mat.available must be false when the pot is inactive.`)
    }
  }

  const actuatorIds = new Set<string>()
  for (const feature of schema.model.features) {
    const match = /^actuators\.([^.]+)\./.exec(feature.path)
    if (match?.[1]) actuatorIds.add(match[1])
  }
  for (const actuatorId of actuatorIds) {
    if (getValueAtPath(configuration, `actuators.${actuatorId}.available`) !== false) continue
    for (const feature of schema.model.features) {
      const prefix = `actuators.${actuatorId}.`
      if (!feature.path.startsWith(prefix)) continue
      const field = feature.path.slice(prefix.length)
      if (isGlobalCapabilityField(field)) {
        validateZero(getValueAtPath(configuration, feature.path), displayPath(feature.path), errors)
      }
    }
  }
}

/** Validate the exact shape, ranges, metadata, and safety rules accepted on import. */
export function validateImportedConfiguration(value: unknown): string[] {
  if (!isJsonObject(value)) return ["The imported JSON root must be an object."]

  const errors: string[] = []
  const expected = createSchemaDefaults()
  validateShape(value, expected, "root", errors, true)

  for (const key of CONTRACT_ROOT_KEYS) {
    if (!hasOwn(value, key)) errors.push(`Required root key ${key} is missing.`)
  }

  validateFeatureValues(value, errors)
  validateMetadata(value, errors)
  validateSafetyInvariants(value, errors)
  return errors
}
