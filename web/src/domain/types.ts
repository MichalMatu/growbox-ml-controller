export type JsonPrimitive = boolean | number | string | null

export type JsonValue = JsonPrimitive | JsonObject | JsonValue[]

export type JsonObject = { [key: string]: JsonValue }

export type FeatureType = "boolean" | "number" | "enum"

export interface FeatureDefinition {
  name: string
  path: string
  type: FeatureType
  unit: string
  minimum: number
  maximum: number
  default: number
  encoding?: Record<string, number>
}

export interface OutputDefinition {
  name: string
  unit: string
  minimum: number
  maximum: number
  default: number
}

export interface ControllerSchema {
  schema_version: number
  model: {
    normalization: string
    features: FeatureDefinition[]
    outputs: OutputDefinition[]
  }
}

export type Configuration = JsonObject

export interface ImportSuccess {
  success: true
  configuration: Configuration
}

export interface ImportFailure {
  success: false
  errors: string[]
}

export type ImportResult = ImportSuccess | ImportFailure

export interface EnclosureDimensions {
  width_cm: number
  depth_cm: number
  height_cm: number
}

export function enclosureAsJson(dimensions: EnclosureDimensions): JsonObject {
  return {
    width_cm: dimensions.width_cm,
    depth_cm: dimensions.depth_cm,
    height_cm: dimensions.height_cm,
  }
}
