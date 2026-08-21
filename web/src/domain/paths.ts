import type { Configuration, JsonObject, JsonValue } from "./types"

export function isJsonObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value)
}

export function isArrayIndex(segment: string): boolean {
  return /^\d+$/.test(segment)
}

export function getValueAtPath(
  configuration: Configuration,
  path: string,
): JsonValue | undefined {
  let current: JsonValue | undefined = configuration

  for (const segment of path.split(".")) {
    if (isArrayIndex(segment)) {
      if (!Array.isArray(current)) return undefined
      current = current[Number(segment)]
      continue
    }

    if (!isJsonObject(current)) return undefined
    current = current[segment]
  }

  return current
}

function updatePath(
  current: JsonValue | undefined,
  segments: string[],
  index: number,
  value: JsonValue,
): JsonValue {
  if (index === segments.length) return value

  const segment = segments[index]
  if (segment === undefined) return value

  if (isArrayIndex(segment)) {
    const array = Array.isArray(current) ? [...current] : []
    const arrayIndex = Number(segment)
    while (array.length <= arrayIndex) array.push(null)
    array[arrayIndex] = updatePath(array[arrayIndex], segments, index + 1, value)
    return array
  }

  const object: JsonObject = isJsonObject(current) ? { ...current } : {}
  object[segment] = updatePath(object[segment], segments, index + 1, value)
  return object
}

export function setValueAtPath(
  configuration: Configuration,
  path: string,
  value: JsonValue,
): Configuration {
  const updated = updatePath(configuration, path.split("."), 0, value)
  if (!isJsonObject(updated)) {
    throw new Error("A configuration root must remain an object.")
  }
  return updated
}

export function copyConfiguration(configuration: Configuration): Configuration {
  return structuredClone(configuration)
}
