import rawSchema from "../../../schemas/environment-controller.json"

import type {
  ControllerSchema,
  FeatureDefinition,
  JsonValue,
} from "./types"

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
}

function isFeatureDefinition(value: unknown): value is FeatureDefinition {
  if (!isRecord(value)) return false

  return (
    typeof value.name === "string" &&
    typeof value.path === "string" &&
    (value.type === "boolean" || value.type === "number" || value.type === "enum") &&
    typeof value.unit === "string" &&
    typeof value.minimum === "number" &&
    typeof value.maximum === "number" &&
    typeof value.default === "number"
  )
}

function isControllerSchema(value: unknown): value is ControllerSchema {
  if (!isRecord(value) || value.schema_version !== 5 || !isRecord(value.model)) {
    return false
  }

  return Array.isArray(value.model.features) && value.model.features.every(isFeatureDefinition)
}

if (!isControllerSchema(rawSchema)) {
  throw new Error("The shared environment-controller schema is not a valid v5 controller schema.")
}

export const schema: ControllerSchema = rawSchema

if (schema.model.features.length !== 228 || schema.model.outputs.length !== 25) {
  throw new Error("The shared v5 schema must contain 228 features and 25 outputs.")
}

/** Number of pot slots derived from schema feature paths. */
export const POT_COUNT = Math.max(
  ...schema.model.features
    .filter((f) => /^pots\.\d+\./.test(f.path))
    .map((f) => {
      const m = f.path.match(/^pots\.(\d+)\./)
      return m ? parseInt(m[1], 10) + 1 : 0
    }),
  0,
)

const featureIndex = new Map(schema.model.features.map((feature) => [feature.path, feature]))

export function getFeature(path: string): FeatureDefinition {
  const feature = featureIndex.get(path)
  if (!feature) {
    throw new Error(`Unknown schema feature path: ${path}`)
  }
  return feature
}

export function getInitialFeatureValue(feature: FeatureDefinition): JsonValue {
  if (feature.type === "boolean") {
    return feature.default === 1
  }

  if (feature.type === "number") {
    return feature.default
  }

  const encodedValue = Object.entries(feature.encoding ?? {}).find(
    ([, value]) => value === feature.default,
  )
  if (!encodedValue) {
    throw new Error(`Enum ${feature.path} has no string for default ${feature.default}.`)
  }
  return encodedValue[0]
}

export function isAllowedEnumValue(feature: FeatureDefinition, value: unknown): value is string {
  return (
    feature.type === "enum" &&
    typeof value === "string" &&
    Object.prototype.hasOwnProperty.call(feature.encoding, value)
  )
}
