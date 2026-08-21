import { getInitialFeatureValue, isAllowedEnumValue, POT_COUNT, schema } from "../schema"
import { setValueAtPath } from "../paths"
import type { Configuration, FeatureDefinition, JsonValue } from "../types"

export { POT_COUNT }

export function createSchemaDefaults(): Configuration {
  let configuration: Configuration = {}
  for (const feature of schema.model.features) {
    configuration = setValueAtPath(
      configuration,
      feature.path,
      getInitialFeatureValue(feature),
    )
  }
  return configuration
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
}

export function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(Math.max(value, minimum), maximum)
}

export function normalizeFeatureValue(
  feature: FeatureDefinition,
  value: JsonValue | undefined,
): JsonValue {
  if (feature.type === "boolean") {
    return typeof value === "boolean" ? value : getInitialFeatureValue(feature)
  }

  if (feature.type === "number") {
    if (!isFiniteNumber(value)) return getInitialFeatureValue(feature)
    return clamp(value, feature.minimum, feature.maximum)
  }

  return isAllowedEnumValue(feature, value) ? value : getInitialFeatureValue(feature)
}
