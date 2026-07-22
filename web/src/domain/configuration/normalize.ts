import { getFeature, schema } from "../schema"
import {
  isJsonObject,
  getValueAtPath,
  setValueAtPath,
} from "../paths"
import type {
  Configuration,
  EnclosureDimensions,
  JsonValue,
} from "../types"
import { enclosureAsJson } from "../types"
import { createSchemaDefaults, normalizeFeatureValue, POT_COUNT } from "./defaults"

function hasOwn(object: object, key: string): boolean {
  return Object.prototype.hasOwnProperty.call(object, key)
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
}

function readEnclosure(value: JsonValue | undefined): EnclosureDimensions | null {
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

function derivedVolume(dimensions: EnclosureDimensions): number {
  return (dimensions.width_cm * dimensions.depth_cm * dimensions.height_cm) / 1_000_000
}

function isGlobalCapabilityField(field: string): boolean {
  return (
    field === "efficiency" ||
    field.includes("dose") ||
    field.startsWith("max_") ||
    field.startsWith("maximum_")
  )
}

function enforceSafetyInvariants(configuration: Configuration): Configuration {
  let normalized = configuration

  for (const feature of schema.model.features) {
    if (feature.path.startsWith("previous.") || /^pots\.\d+\.previous\./.test(feature.path)) {
      normalized = setValueAtPath(normalized, feature.path, 0)
    }
  }

  for (let index = 0; index < POT_COUNT; index += 1) {
    const prefix = `pots.${index}`
    const irrigationPrefix = `${prefix}.irrigation`
    const heatMatPrefix = `${prefix}.heat_mat`
    const potUnavailable = getValueAtPath(normalized, `${prefix}.available`) === false

    if (potUnavailable) {
      normalized = setValueAtPath(normalized, `${prefix}.validity.soil_moisture_pct`, false)
      normalized = setValueAtPath(normalized, `${prefix}.validity.soil_temperature_c`, false)
      normalized = setValueAtPath(normalized, `${irrigationPrefix}.available`, false)
      normalized = setValueAtPath(normalized, `${heatMatPrefix}.available`, false)
    }

    if (getValueAtPath(normalized, `${irrigationPrefix}.available`) === false) {
      for (const field of ["flow_ml_s", "maximum_pulse_s", "minimum_interval_s"]) {
        normalized = setValueAtPath(normalized, `${irrigationPrefix}.${field}`, 0)
      }
    }

    if (getValueAtPath(normalized, `${heatMatPrefix}.available`) === false) {
      normalized = setValueAtPath(normalized, `${heatMatPrefix}.max_power_w`, 0)
    }
  }

  const actuatorIds = new Set<string>()
  for (const feature of schema.model.features) {
    const match = /^actuators\.([^.]+)\./.exec(feature.path)
    if (match?.[1]) actuatorIds.add(match[1])
  }

  for (const actuatorId of actuatorIds) {
    if (getValueAtPath(normalized, `actuators.${actuatorId}.available`) !== false) continue

    for (const feature of schema.model.features) {
      const prefix = `actuators.${actuatorId}.`
      if (!feature.path.startsWith(prefix)) continue
      const field = feature.path.slice(prefix.length)
      if (isGlobalCapabilityField(field)) {
        normalized = setValueAtPath(normalized, feature.path, 0)
      }
    }
  }

  return normalized
}

/**
 * Produce the one canonical shape used by the editor and by JSON export.
 * Unknown paths are intentionally omitted; import validation rejects them.
 */
export function normalizeConfiguration(source: Configuration): Configuration {
  let normalized = createSchemaDefaults()

  for (const feature of schema.model.features) {
    normalized = setValueAtPath(
      normalized,
      feature.path,
      normalizeFeatureValue(feature, getValueAtPath(source, feature.path)),
    )
  }

  if (typeof source.title === "string") normalized.title = source.title
  if (typeof source.profile_id === "string") normalized.profile_id = source.profile_id
  if (Number.isInteger(source.seed)) normalized.seed = source.seed

  const enclosure = readEnclosure(source.enclosure)
  if (enclosure) {
    const volume = derivedVolume(enclosure)
    const volumeFeature = getFeature("environment.growbox_volume_m3")
    if (volume >= volumeFeature.minimum && volume <= volumeFeature.maximum) {
      normalized.enclosure = enclosureAsJson(enclosure)
      normalized = setValueAtPath(normalized, volumeFeature.path, volume)
    }
  }

  return enforceSafetyInvariants(normalized)
}

export function createDefaultConfiguration(): Configuration {
  const configuration = normalizeConfiguration(createSchemaDefaults())
  configuration.title = "Nowa konfiguracja growbox"
  configuration.profile_id = "growbox-v4"
  configuration.seed = 0
  return configuration
}

export { enforceSafetyInvariants }
