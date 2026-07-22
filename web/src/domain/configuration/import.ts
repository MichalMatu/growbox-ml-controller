import { isJsonObject } from "../paths"
import type { ImportResult } from "../types"
import { validateImportedConfiguration } from "./validation"
import { normalizeConfiguration } from "./normalize"

export function importConfiguration(value: unknown): ImportResult {
  const errors = validateImportedConfiguration(value)
  if (errors.length > 0 || !isJsonObject(value)) {
    return { success: false, errors }
  }
  return { success: true, configuration: normalizeConfiguration(value) }
}

export function parseConfigurationJson(text: string): ImportResult {
  try {
    return importConfiguration(JSON.parse(text) as unknown)
  } catch {
    return { success: false, errors: ["The selected file is not valid JSON."] }
  }
}
