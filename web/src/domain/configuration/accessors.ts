import { getFeature } from "../schema"
import { getValueAtPath, setValueAtPath, copyConfiguration } from "../paths"
import type { Configuration, FeatureDefinition, JsonValue } from "../types"
import { normalizeConfiguration } from "./normalize"

export type EditableMetadataKey = "title" | "profile_id" | "seed"

export function getConfigurationFeatureValue(
  configuration: Configuration,
  feature: FeatureDefinition,
): JsonValue {
  return getValueAtPath(configuration, feature.path) ?? getFeature(feature.path).default
}

export function updateFeatureValue(
  configuration: Configuration,
  path: string,
  value: JsonValue,
): Configuration {
  getFeature(path)
  return normalizeConfiguration(setValueAtPath(configuration, path, value))
}

export function updateMetadata(
  configuration: Configuration,
  key: EditableMetadataKey,
  value: string | number | undefined,
): Configuration {
  const updated = copyConfiguration(configuration)
  if (value === undefined) {
    delete updated[key]
  } else {
    updated[key] = value
  }
  return normalizeConfiguration(updated)
}
