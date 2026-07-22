import type { Configuration } from "../types"
import { normalizeConfiguration } from "./normalize"

export function buildExportConfiguration(configuration: Configuration): Configuration {
  return normalizeConfiguration(configuration)
}
