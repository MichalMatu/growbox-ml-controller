// Re-export from modular structure — backward-compatible public API.
export {
  createDefaultConfiguration,
  normalizeConfiguration,
  getConfigurationFeatureValue,
  updateFeatureValue,
  updateMetadata,
  parseConfigurationJson,
  importConfiguration,
  validateImportedConfiguration,
  buildExportConfiguration,
  POT_COUNT,
} from "./configuration/index"

export type { EditableMetadataKey } from "./configuration/index"
