#!/usr/bin/env node
/**
 * Contract gate for the sparse configurator branch.
 *
 * It deliberately has no third-party dependencies so it can run before web/
 * exists. The validator is exported as well: future web-domain tests can use
 * the same invariants for an export candidate via `--input <file>`.
 */
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
export const ROOT = join(__dirname, "..");

const SCHEMA_PATH = join(ROOT, "schemas", "environment-controller.json");
const GOLDEN_PATH = join(ROOT, "docs", "examples", "minimal-single-pot.json");
const PACKAGE_PATH = join(ROOT, "package.json");
const PNPM_LOCK_PATH = join(ROOT, "pnpm-lock.yaml");
const AGENTS_PATH = join(ROOT, "AGENTS.md");
const WEB_PATH = join(ROOT, "web");

export const CONTRACT_ROOT_KEYS = [
  "environment",
  "sensors",
  "validity",
  "pseudo",
  "pots",
  "actuators",
  "targets",
  "previous",
];

export const ROOT_META_KEYS = ["seed", "profile_id", "title", "enclosure"];

const EXPECTED_OUTPUT_NAMES = [
  "heater",
  "fan",
  "humidifier",
  "dehumidifier",
  "cooler",
  "co2_doser",
  "irrigation_pot_1",
  "irrigation_pot_2",
  "irrigation_pot_3",
  "irrigation_pot_4",
  "nutrient_heater",
  "heat_mat_pot_1",
  "heat_mat_pot_2",
  "heat_mat_pot_3",
  "heat_mat_pot_4",
  "irrigation_pot_5",
  "heat_mat_pot_5",
  "irrigation_pot_6",
  "heat_mat_pot_6",
  "irrigation_pot_7",
  "heat_mat_pot_7",
  "irrigation_pot_8",
  "heat_mat_pot_8",
  "irrigation_pot_9",
  "heat_mat_pot_9",
];

/*
 * SHA-256 of canonical schema.model for the active v4 contract. It locks the
 * feature/output order, names, paths, types, ranges, defaults, and enum
 * encodings. A v4 model change must not silently reach the frontend.
 */
export const EXPECTED_V4_MODEL_SIGNATURE =
  "09a6bed70b4194c28f20578fa9b9cb9450b6e8e93b622532d7c43139bf84128d";

const REQUIRED_WEB_DEPENDENCIES = [
  "react",
  "react-dom",
  "typescript",
  "vite",
  "vitest",
  "tailwindcss",
];

const BANNED_WEB_DEPENDENCIES = new Set([
  "next",
  "@remix-run/react",
  "@remix-run/dev",
  "@mui/material",
  "@chakra-ui/react",
  "antd",
  "@mantine/core",
  "styled-components",
  "@emotion/react",
  "@emotion/styled",
  "vue",
  "svelte",
  "solid-js",
]);

export function isPlainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function isFiniteNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

function isArrayIndex(segment) {
  return /^\d+$/.test(segment);
}

function displayPath(segments) {
  if (!segments.length) return "root";

  let path = "";
  for (const segment of segments) {
    path += isArrayIndex(segment)
      ? `[${segment}]`
      : path
        ? `.${segment}`
        : segment;
  }
  return path;
}

/** Resolve schema path `pots.0.irrigation.available` on nested export JSON. */
export function getBySchemaPath(root, path) {
  let current = root;
  for (const segment of path.split(".")) {
    if (current === null || current === undefined) {
      return { ok: false, value: undefined };
    }

    if (isArrayIndex(segment)) {
      if (!Array.isArray(current) || !hasOwn(current, segment)) {
        return { ok: false, value: undefined };
      }
      current = current[Number(segment)];
      continue;
    }

    if (!isPlainObject(current) || !hasOwn(current, segment)) {
      return { ok: false, value: undefined };
    }
    current = current[segment];
  }
  return { ok: true, value: current };
}

function canonicalJson(value) {
  if (value === null || typeof value !== "object") {
    return JSON.stringify(value);
  }

  if (Array.isArray(value)) {
    return `[${value.map(canonicalJson).join(",")}]`;
  }

  return `{${Object.keys(value)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
    .join(",")}}`;
}

export function modelSignature(model) {
  return createHash("sha256").update(canonicalJson(model)).digest("hex");
}

function push(errors, message) {
  errors.push(message);
}

function validateFeatureDescriptor(feature, index, errors, names, paths) {
  const label = `model.features[${index}]`;
  if (!isPlainObject(feature)) {
    push(errors, `${label} must be an object`);
    return;
  }

  if (typeof feature.name !== "string" || feature.name.length === 0) {
    push(errors, `${label}.name must be a non-empty string`);
  } else if (names.has(feature.name)) {
    push(errors, `duplicate feature name: ${feature.name}`);
  } else {
    names.add(feature.name);
  }

  if (
    typeof feature.path !== "string" ||
    feature.path.length === 0 ||
    feature.path.split(".").some((segment) => segment.length === 0)
  ) {
    push(errors, `${label}.path must be a non-empty dot path`);
  } else if (paths.has(feature.path)) {
    push(errors, `duplicate feature path: ${feature.path}`);
  } else {
    paths.add(feature.path);
  }

  if (!["boolean", "number", "enum"].includes(feature.type)) {
    push(errors, `${label}.type must be boolean, number, or enum`);
    return;
  }

  if (feature.type === "boolean") {
    if (feature.minimum !== 0 || feature.maximum !== 1 || ![0, 1].includes(feature.default)) {
      push(errors, `${label} boolean encoding must use minimum 0, maximum 1, and default 0 or 1`);
    }
  }

  if (feature.type === "number") {
    for (const key of ["minimum", "maximum", "default"]) {
      if (!isFiniteNumber(feature[key])) {
        push(errors, `${label}.${key} must be a finite number`);
      }
    }
    if (
      isFiniteNumber(feature.minimum) &&
      isFiniteNumber(feature.maximum) &&
      feature.minimum > feature.maximum
    ) {
      push(errors, `${label}.minimum must not exceed maximum`);
    }
    if (
      isFiniteNumber(feature.default) &&
      isFiniteNumber(feature.minimum) &&
      isFiniteNumber(feature.maximum) &&
      (feature.default < feature.minimum || feature.default > feature.maximum)
    ) {
      push(errors, `${label}.default must be within minimum/maximum`);
    }
  }

  if (feature.type === "enum") {
    if (!isPlainObject(feature.encoding) || Object.keys(feature.encoding).length === 0) {
      push(errors, `${label}.encoding must be a non-empty object`);
      return;
    }

    const encodingValues = Object.values(feature.encoding);
    if (!encodingValues.every(isFiniteNumber)) {
      push(errors, `${label}.encoding values must be finite numbers`);
    }
    if (!encodingValues.includes(feature.default)) {
      push(errors, `${label}.default must be one of the encoding values`);
    }
  }
}

function validateOutputDescriptor(output, index, errors) {
  if (!isPlainObject(output)) {
    push(errors, `model.outputs[${index}] must be an object`);
    return;
  }

  if (typeof output.name !== "string" || output.name.length === 0) {
    push(errors, `model.outputs[${index}].name must be a non-empty string`);
  }
  for (const key of ["minimum", "maximum", "default"]) {
    if (!isFiniteNumber(output[key])) {
      push(errors, `model.outputs[${index}].${key} must be a finite number`);
    }
  }
  if (
    isFiniteNumber(output.minimum) &&
    isFiniteNumber(output.maximum) &&
    output.minimum > output.maximum
  ) {
    push(errors, `model.outputs[${index}].minimum must not exceed maximum`);
  }
  if (
    isFiniteNumber(output.default) &&
    isFiniteNumber(output.minimum) &&
    isFiniteNumber(output.maximum) &&
    (output.default < output.minimum || output.default > output.maximum)
  ) {
    push(errors, `model.outputs[${index}].default must be within minimum/maximum`);
  }
}

function validateSchema(schema) {
  const errors = [];
  if (!isPlainObject(schema)) {
    return { errors: ["schema root must be an object"], features: [], valid: false };
  }

  if (schema.schema_id !== "environment-controller") {
    push(errors, `schema_id must be "environment-controller" (got ${JSON.stringify(schema.schema_id)})`);
  }
  if (schema.schema_version !== 5) {
    push(errors, `schema_version must be 5 (got ${JSON.stringify(schema.schema_version)})`);
  }
  if (
    schema.status !== "active" ||
    schema.io_status !== "definitive" ||
    schema.sensing_status !== "definitive"
  ) {
    push(errors, "schema must remain active with definitive I/O and sensing status");
  }
  if (!isPlainObject(schema.model)) {
    push(errors, "model must be an object");
    return { errors, features: [], valid: false };
  }

  const features = schema.model.features;
  const outputs = schema.model.outputs;
  if (!Array.isArray(features) || features.length !== 228) {
    push(errors, `model.features must be an array of length 228 (got ${features?.length})`);
  }
  if (!Array.isArray(outputs) || outputs.length !== 25) {
    push(errors, `model.outputs must be an array of length 25 (got ${outputs?.length})`);
  }

  if (!Array.isArray(features) || !Array.isArray(outputs)) {
    return { errors, features: [], valid: false };
  }

  const names = new Set();
  const paths = new Set();
  features.forEach((feature, index) =>
    validateFeatureDescriptor(feature, index, errors, names, paths),
  );
  const outputNameSet = new Set();
  outputs.forEach((output, index) => {
    validateOutputDescriptor(output, index, errors);
    if (typeof output?.name === "string") {
      if (outputNameSet.has(output.name)) {
        push(errors, `duplicate output name: ${output.name}`);
      }
      outputNameSet.add(output.name);
    }
  });

  const outputNames = outputs.map((output) => output?.name);
  for (let index = 0; index < EXPECTED_OUTPUT_NAMES.length; index += 1) {
    if (outputNames[index] !== EXPECTED_OUTPUT_NAMES[index]) {
      push(
        errors,
        `model.outputs[${index}] name must be ${EXPECTED_OUTPUT_NAMES[index]} (got ${JSON.stringify(outputNames[index])})`,
      );
    }
  }

  if (schema.model.normalization !== "minmax_to_zero_one") {
    push(errors, "model.normalization must be \"minmax_to_zero_one\"");
  }

  const signature = modelSignature(schema.model);
  if (signature !== EXPECTED_V4_MODEL_SIGNATURE) {
    push(
      errors,
      `v4 model signature changed (expected ${EXPECTED_V4_MODEL_SIGNATURE}, got ${signature}); bump schema_version and regenerate on main before updating this gate`,
    );
  }

  const nonMlActuators = schema.output_scope?.non_ml_actuators;
  if (schema.output_scope?.ml_output_count !== 25) {
    push(errors, "output_scope.ml_output_count must be 25");
  }
  if (!Array.isArray(nonMlActuators) || nonMlActuators.length !== 1 || nonMlActuators[0] !== "lights") {
    push(errors, "output_scope.non_ml_actuators must be exactly [\"lights\"]");
  }

  return { errors, features, valid: errors.length === 0 };
}

function createNode(kind) {
  return { children: new Map(), feature: null, kind };
}

function buildFeatureTree(features, errors) {
  const root = createNode("object");

  for (const feature of features) {
    if (typeof feature.path !== "string") continue;

    const parts = feature.path.split(".");
    let node = root;
    for (let index = 0; index < parts.length; index += 1) {
      const segment = parts[index];
      const isLeaf = index === parts.length - 1;
      const expectedKind = isLeaf
        ? "leaf"
        : isArrayIndex(parts[index + 1])
          ? "array"
          : "object";
      const existing = node.children.get(segment);

      if (existing && existing.kind !== expectedKind) {
        push(errors, `schema paths disagree on container type at ${displayPath(parts.slice(0, index + 1))}`);
        break;
      }

      const child = existing ?? createNode(expectedKind);
      node.children.set(segment, child);
      node = child;

      if (isLeaf) {
        if (node.feature) {
          push(errors, `schema paths duplicate leaf ${feature.path}`);
        }
        node.feature = feature;
      }
    }
  }

  return root;
}

function validateDocumentShape(value, node, segments, errors, isRoot = false) {
  const label = displayPath(segments);

  if (node.kind === "leaf") return;

  if (node.kind === "array") {
    if (!Array.isArray(value)) {
      push(errors, `${label} must be an array`);
      return;
    }

    const expectedIndices = [...node.children.keys()]
      .map(Number)
      .sort((left, right) => left - right);
    const expectedLength = expectedIndices.length;
    const consecutive = expectedIndices.every((index, expected) => index === expected);
    if (!consecutive) {
      push(errors, `${label} schema array indices must be consecutive from 0`);
      return;
    }
    if (value.length !== expectedLength) {
      push(errors, `${label} must have length ${expectedLength} (got ${value.length})`);
    }

    for (const index of expectedIndices) {
      if (!hasOwn(value, String(index))) {
        push(errors, `${label}[${index}] is missing`);
        continue;
      }
      validateDocumentShape(value[index], node.children.get(String(index)), [...segments, String(index)], errors);
    }
    return;
  }

  if (!isPlainObject(value)) {
    push(errors, `${label} must be an object`);
    return;
  }

  for (const [key, child] of node.children) {
    if (!hasOwn(value, key)) {
      push(errors, `${displayPath([...segments, key])} is missing`);
      continue;
    }
    validateDocumentShape(value[key], child, [...segments, key], errors);
  }

  for (const key of Object.keys(value)) {
    if (node.children.has(key)) continue;
    if (isRoot && ROOT_META_KEYS.includes(key)) continue;
    push(errors, `${displayPath([...segments, key])} is not an allowed export path`);
  }
}

function validateFeatureValue(feature, value, errors) {
  const path = feature.path;
  if (feature.type === "boolean") {
    if (typeof value !== "boolean") {
      push(errors, `${path}: expected boolean, got ${typeof value}`);
    }
    return;
  }

  if (feature.type === "enum") {
    if (typeof value !== "string") {
      push(errors, `${path}: enum must be a JSON string, got ${typeof value}`);
      return;
    }
    if (!hasOwn(feature.encoding, value)) {
      push(errors, `${path}: enum string ${JSON.stringify(value)} is not allowed`);
    }
    return;
  }

  if (!isFiniteNumber(value)) {
    push(errors, `${path}: expected a finite number, got ${JSON.stringify(value)}`);
    return;
  }
  if (value < feature.minimum || value > feature.maximum) {
    push(errors, `${path}: ${value} is outside [${feature.minimum}, ${feature.maximum}]`);
  }
}

function validateFeatureValues(document, features, errors) {
  for (const feature of features) {
    const resolved = getBySchemaPath(document, feature.path);
    if (!resolved.ok) {
      push(errors, `export is missing schema path: ${feature.path}`);
      continue;
    }
    validateFeatureValue(feature, resolved.value, errors);
  }
}

function assertZero(value, path, errors) {
  if (value !== 0) {
    push(errors, `${path} must be 0 in a hardware-template export (got ${JSON.stringify(value)})`);
  }
}

function validateMetadata(document, errors) {
  if (hasOwn(document, "seed") && !Number.isInteger(document.seed)) {
    push(errors, "seed must be an integer when present");
  }
  for (const key of ["profile_id", "title"]) {
    if (hasOwn(document, key) && typeof document[key] !== "string") {
      push(errors, `${key} must be a string when present`);
    }
  }

  if (!hasOwn(document, "enclosure")) return;

  const enclosure = document.enclosure;
  const enclosureKeys = ["width_cm", "depth_cm", "height_cm"];
  if (!isPlainObject(enclosure)) {
    push(errors, "enclosure must be an object when present");
    return;
  }
  for (const key of enclosureKeys) {
    if (!hasOwn(enclosure, key)) {
      push(errors, `enclosure.${key} is required when enclosure is present`);
    } else if (!isFiniteNumber(enclosure[key]) || enclosure[key] <= 0) {
      push(errors, `enclosure.${key} must be a positive finite number`);
    }
  }
  for (const key of Object.keys(enclosure)) {
    if (!enclosureKeys.includes(key)) {
      push(errors, `enclosure.${key} is not an allowed enclosure field`);
    }
  }

  if (!enclosureKeys.every((key) => isFiniteNumber(enclosure[key]) && enclosure[key] > 0)) {
    return;
  }

  const derivedVolume =
    (enclosure.width_cm * enclosure.depth_cm * enclosure.height_cm) / 1_000_000;
  const actualVolume = document.environment?.growbox_volume_m3;
  const tolerance = Math.max(1e-9, Math.abs(derivedVolume) * 1e-9);
  if (!isFiniteNumber(actualVolume) || Math.abs(actualVolume - derivedVolume) > tolerance) {
    push(
      errors,
      `environment.growbox_volume_m3 must equal enclosure volume ${derivedVolume} m3 when enclosure is present`,
    );
  }
}

function validatePotInvariants(document, features, errors) {
  if (!Array.isArray(document.pots)) return;

  for (let index = 0; index < document.pots.length; index += 1) {
    const pot = document.pots[index];
    if (!isPlainObject(pot)) continue;
    const prefix = `pots[${index}]`;
    const irrigation = pot.irrigation;
    const heatMat = pot.heat_mat;

    if (isPlainObject(irrigation) && irrigation.available === false) {
      for (const key of ["flow_ml_s", "maximum_pulse_s", "minimum_interval_s"]) {
        assertZero(irrigation[key], `${prefix}.irrigation.${key}`, errors);
      }
    }
    if (isPlainObject(heatMat) && heatMat.available === false) {
      assertZero(heatMat.max_power_w, `${prefix}.heat_mat.max_power_w`, errors);
    }

    if (pot.available === false) {
      if (pot.validity?.soil_moisture_pct !== false) {
        push(errors, `${prefix} inactive: validity.soil_moisture_pct must be false`);
      }
      if (pot.validity?.soil_temperature_c !== false) {
        push(errors, `${prefix} inactive: validity.soil_temperature_c must be false`);
      }
      if (irrigation?.available !== false) {
        push(errors, `${prefix} inactive: irrigation.available must be false`);
      }
      if (heatMat?.available !== false) {
        push(errors, `${prefix} inactive: heat_mat.available must be false`);
      }
    }
  }

  for (const feature of features) {
    if (!/^pots\.\d+\.previous\./.test(feature.path)) continue;
    const resolved = getBySchemaPath(document, feature.path);
    if (resolved.ok) assertZero(resolved.value, displayPath(feature.path.split(".")), errors);
  }
}

function isGlobalCapabilityField(field) {
  return (
    field === "efficiency" ||
    field.includes("dose") ||
    field.startsWith("max_") ||
    field.startsWith("maximum_")
  );
}

function validateActuatorInvariants(document, features, errors) {
  if (!isPlainObject(document.actuators)) return;

  if (hasOwn(document.actuators, "lights")) {
    push(errors, "actuators.lights is forbidden; use pseudo.lights_active");
  }

  for (const [id, actuator] of Object.entries(document.actuators)) {
    if (!isPlainObject(actuator)) continue;
    if (hasOwn(actuator, "control_type")) {
      push(errors, `actuators.${id}.control_type is forbidden in v4`);
    }
    if (actuator.available !== false) continue;

    for (const [field, value] of Object.entries(actuator)) {
      if (isGlobalCapabilityField(field)) {
        assertZero(value, `actuators.${id}.${field}`, errors);
      }
    }
  }

  for (const feature of features) {
    if (!feature.path.startsWith("previous.")) continue;
    const resolved = getBySchemaPath(document, feature.path);
    if (resolved.ok) assertZero(resolved.value, feature.path, errors);
  }
}

/**
 * Validate a schema-v4 export candidate without reading files.
 */
export function validateContract(schema, document) {
  const schemaResult = validateSchema(schema);
  const errors = [...schemaResult.errors];
  if (!schemaResult.valid) {
    return { errors, featuresChecked: 0, modelSignature: null };
  }

  if (!isPlainObject(document)) {
    push(errors, "export root must be an object");
    return {
      errors,
      featuresChecked: 0,
      modelSignature: modelSignature(schema.model),
    };
  }

  for (const key of CONTRACT_ROOT_KEYS) {
    if (!hasOwn(document, key)) {
      push(errors, `required root contract key ${key} is missing`);
    }
  }

  const featureTree = buildFeatureTree(schemaResult.features, errors);
  validateDocumentShape(document, featureTree, [], errors, true);
  validateFeatureValues(document, schemaResult.features, errors);
  validateMetadata(document, errors);
  validatePotInvariants(document, schemaResult.features, errors);
  validateActuatorInvariants(document, schemaResult.features, errors);

  return {
    errors,
    featuresChecked: schemaResult.features.length,
    modelSignature: modelSignature(schema.model),
  };
}

function dependencyMap(packageJson) {
  return {
    ...(isPlainObject(packageJson?.dependencies) ? packageJson.dependencies : {}),
    ...(isPlainObject(packageJson?.devDependencies) ? packageJson.devDependencies : {}),
  };
}

function requestedMajor(version) {
  if (typeof version !== "string") return null;
  const match = version.match(/\d+/);
  return match ? Number(match[0]) : null;
}

function isBannedWebDependency(dependency) {
  return (
    BANNED_WEB_DEPENDENCIES.has(dependency) ||
    ["@remix-run/", "@mui/", "@chakra-ui/", "@mantine/", "@emotion/", "@angular/"].some(
      (prefix) => dependency.startsWith(prefix),
    )
  );
}

/**
 * Validate the root package and, once present, the future web/ package.
 */
export function validateWorkspace({
  packageJson,
  hasWeb,
  webPackageJson = null,
  webTsconfigSources = [],
  nodeVersion = process.versions.node,
  forbiddenLockfiles = [],
  pnpmLockfile = null,
}) {
  const errors = [];
  if (!isPlainObject(packageJson)) {
    return { errors: ["package.json root must be an object"] };
  }

  if (packageJson.packageManager !== "pnpm@11.10.0") {
    push(
      errors,
      `package.json packageManager must be exactly "pnpm@11.10.0" (got ${JSON.stringify(packageJson.packageManager)})`,
    );
  }
  if (packageJson.engines?.node !== ">=20") {
    push(errors, 'package.json engines.node must be exactly ">=20"');
  }

  const expectedRootGate = hasWeb
    ? "node gate/check-contract.mjs && pnpm --dir web gate"
    : "node gate/check-contract.mjs";
  if (packageJson.scripts?.gate !== expectedRootGate) {
    push(errors, `package.json scripts.gate must be ${JSON.stringify(expectedRootGate)}`);
  }

  const major = Number(String(nodeVersion).split(".")[0]);
  if (!Number.isInteger(major) || major < 20) {
    push(errors, `Node >=20 is required to run the gate (got ${nodeVersion})`);
  }

  for (const lockfile of forbiddenLockfiles) {
    push(errors, `${lockfile} is forbidden; this repository is pnpm-only`);
  }
  if (typeof pnpmLockfile !== "string") {
    push(errors, "pnpm-lock.yaml must exist at the repository root");
  } else if (!/^lockfileVersion:\s*['\"]9\.0['\"]/m.test(pnpmLockfile)) {
    push(errors, "pnpm-lock.yaml must use lockfileVersion 9.0 for pnpm 11");
  }

  if (!hasWeb) return { errors };

  if (!isPlainObject(webPackageJson)) {
    push(errors, "web/package.json must exist and be an object once web/ exists");
    return { errors };
  }
  if (webPackageJson.private !== true) {
    push(errors, "web/package.json must set private to true");
  }

  const webScripts = webPackageJson.scripts;
  if (!isPlainObject(webScripts)) {
    push(errors, "web/package.json scripts must be an object");
  } else {
    for (const script of ["typecheck", "lint", "test", "build", "gate"]) {
      if (typeof webScripts[script] !== "string" || webScripts[script].trim() === "") {
        push(errors, `web/package.json scripts.${script} must be a non-empty string`);
      }
    }
    if (webScripts.typecheck !== "tsc --noEmit") {
      push(errors, 'web/package.json scripts.typecheck must be "tsc --noEmit"');
    }
    if (!/\bvitest\b/.test(webScripts.test ?? "")) {
      push(errors, "web/package.json scripts.test must run Vitest");
    }
    if (!/\bvite\s+build\b/.test(webScripts.build ?? "")) {
      push(errors, "web/package.json scripts.build must run vite build");
    }
    if (webScripts.gate !== "pnpm typecheck && pnpm lint && pnpm test && pnpm build") {
      push(
        errors,
        'web/package.json scripts.gate must be "pnpm typecheck && pnpm lint && pnpm test && pnpm build"',
      );
    }
  }

  const runtimeDependencies = isPlainObject(webPackageJson.dependencies)
    ? webPackageJson.dependencies
    : {};
  for (const dependency of ["react", "react-dom"]) {
    const version = runtimeDependencies[dependency];
    const majorVersion = requestedMajor(version);
    if (majorVersion === null || majorVersion < 18) {
      push(errors, `web/package.json dependencies.${dependency} must target React 18 or newer`);
    }
  }

  const dependencies = dependencyMap(webPackageJson);
  for (const dependency of REQUIRED_WEB_DEPENDENCIES) {
    if (typeof dependencies[dependency] !== "string") {
      push(errors, `web/package.json must declare ${dependency}`);
    }
  }
  for (const dependency of Object.keys(dependencies)) {
    if (isBannedWebDependency(dependency)) {
      push(errors, `web/package.json declares forbidden dependency ${dependency}`);
    }
  }

  if (!webTsconfigSources.some((source) => /["']strict["']\s*:\s*true/.test(source))) {
    push(errors, "web TypeScript configuration must enable strict: true");
  }

  return { errors };
}

function loadJson(path, label, errors) {
  if (!existsSync(path)) {
    push(errors, `missing file: ${label} (${path})`);
    return null;
  }
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    push(errors, `invalid JSON: ${label}: ${error.message}`);
    return null;
  }
}

function loadText(path, label, errors) {
  if (!existsSync(path)) {
    push(errors, `missing file: ${label} (${path})`);
    return null;
  }
  return readFileSync(path, "utf8");
}

function parseArguments(argv) {
  const result = { errors: [], inputPath: GOLDEN_PATH, inputLabel: "golden example" };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--input") {
      const suppliedPath = argv[index + 1];
      if (!suppliedPath || suppliedPath.startsWith("--")) {
        push(result.errors, "--input requires a JSON file path");
      } else {
        result.inputPath = resolve(process.cwd(), suppliedPath);
        result.inputLabel = `export candidate (${suppliedPath})`;
        index += 1;
      }
      continue;
    }
    if (argument === "--help" || argument === "-h") {
      result.help = true;
      continue;
    }
    push(result.errors, `unknown argument: ${argument}`);
  }
  return result;
}

function getWebTsconfigSources(errors) {
  if (!existsSync(WEB_PATH)) return [];
  try {
    return readdirSync(WEB_PATH)
      .filter((name) => /^tsconfig(?:\..+)?\.json$/.test(name))
      .map((name) => readFileSync(join(WEB_PATH, name), "utf8"));
  } catch (error) {
    push(errors, `could not read web TypeScript configuration: ${error.message}`);
    return [];
  }
}

function printResult(errors, result) {
  if (errors.length) {
    console.error("GATE FAILED:");
    for (const error of errors) console.error(`  - ${error}`);
    console.error(`\n${errors.length} error(s).`);
    process.exitCode = 1;
    return;
  }

  console.log("GATE OK: schema v4 + export shape + workspace invariants.");
  console.log(`  features checked: ${result.featuresChecked}`);
  console.log(`  model signature: ${result.modelSignature}`);
}

function main() {
  const args = parseArguments(process.argv.slice(2));
  if (args.help) {
    console.log("Usage: node gate/check-contract.mjs [--input path/to/export.json]");
    return;
  }

  const errors = [...args.errors];
  const schema = loadJson(SCHEMA_PATH, "schema", errors);
  const document = loadJson(args.inputPath, args.inputLabel, errors);
  const packageJson = loadJson(PACKAGE_PATH, "package.json", errors);
  const pnpmLockfile = loadText(PNPM_LOCK_PATH, "pnpm-lock.yaml", errors);
  loadText(AGENTS_PATH, "AGENTS.md", errors);

  const hasWeb = existsSync(WEB_PATH);
  const webPackageJson = hasWeb
    ? loadJson(join(WEB_PATH, "package.json"), "web/package.json", errors)
    : null;
  const forbiddenLockfiles = [
    join(ROOT, "package-lock.json"),
    join(ROOT, "yarn.lock"),
    join(WEB_PATH, "package-lock.json"),
    join(WEB_PATH, "yarn.lock"),
  ].filter((path) => existsSync(path));

  if (packageJson) {
    errors.push(
      ...validateWorkspace({
        packageJson,
        hasWeb,
        webPackageJson,
        webTsconfigSources: getWebTsconfigSources(errors),
        forbiddenLockfiles: forbiddenLockfiles.map((path) => path.slice(ROOT.length + 1)),
        pnpmLockfile,
      }).errors,
    );
  }

  let result = { featuresChecked: 0, modelSignature: null };
  if (schema && document) {
    result = validateContract(schema, document);
    errors.push(...result.errors);
  }

  printResult(errors, result);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main();
}
