import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { join } from "node:path";
import {
  ROOT,
  validateContract,
  validateWorkspace,
} from "./check-contract.mjs";

const schema = JSON.parse(
  readFileSync(join(ROOT, "schemas", "environment-controller.json"), "utf8"),
);
const golden = JSON.parse(
  readFileSync(join(ROOT, "docs", "examples", "minimal-single-pot.json"), "utf8"),
);

function candidate() {
  return structuredClone(golden);
}

function errorsFor(document, candidateSchema = schema) {
  return validateContract(candidateSchema, document).errors;
}

function setBySchemaPath(root, schemaPath, value) {
  const segments = schemaPath.split(".");
  let current = root;
  for (const segment of segments.slice(0, -1)) {
    current = /^\d+$/.test(segment) ? current[Number(segment)] : current[segment];
  }
  const leaf = segments.at(-1);
  if (/^\d+$/.test(leaf)) {
    current[Number(leaf)] = value;
  } else {
    current[leaf] = value;
  }
}

function expectError(errors, fragment) {
  assert.ok(
    errors.some((error) => error.includes(fragment)),
    `Expected an error containing ${JSON.stringify(fragment)}; got:\n${errors.join("\n")}`,
  );
}

test("golden export satisfies the complete v4 contract", () => {
  assert.deepEqual(errorsFor(candidate()), []);
});

test("pot control enums must remain JSON strings", () => {
  const document = candidate();
  document.pots[0].irrigation.control_type = 0;

  expectError(errorsFor(document), "enum must be a JSON string");
});

test("an unavailable per-pot actuator cannot retain a capability", () => {
  const document = candidate();
  document.pots[0].irrigation.available = false;
  document.pots[0].irrigation.flow_ml_s = 18;

  expectError(errorsFor(document), "pots[0].irrigation.flow_ml_s must be 0");
});

test("all previous commands are zero, including active pots", () => {
  const document = candidate();
  document.pots[0].previous.irrigation = 0.25;

  expectError(errorsFor(document), "pots[0].previous.irrigation must be 0");
});

test("unknown nested paths cannot silently enter an export", () => {
  const document = candidate();
  document.actuators.heater.control_type = "pwm";

  expectError(errorsFor(document), "actuators.heater.control_type is not an allowed export path");
  expectError(errorsFor(document), "actuators.heater.control_type is forbidden in v4");
});

test("enclosure dimensions must derive the ML chamber volume", () => {
  const document = candidate();
  document.enclosure = {
    width_cm: 100,
    depth_cm: 100,
    height_cm: 80,
  };

  assert.deepEqual(errorsFor(document), []);

  document.environment.growbox_volume_m3 = 0.7;
  expectError(errorsFor(document), "must equal enclosure volume 0.8 m3");
});

test("root metadata has stable, explicit types", () => {
  const document = candidate();
  document.seed = 2.5;
  document.profile_id = 42;

  const errors = errorsFor(document);
  expectError(errors, "seed must be an integer");
  expectError(errors, "profile_id must be a string");
});

test("every v4 feature path is type- and range-validated", () => {
  for (const feature of schema.model.features) {
    const document = candidate();
    const invalidValue =
      feature.type === "boolean"
        ? "not-a-boolean"
        : feature.type === "enum"
          ? "not-an-enum-member"
          : feature.minimum - 1;
    setBySchemaPath(document, feature.path, invalidValue);

    expectError(errorsFor(document), feature.path);
  }
});

test("the gate detects a reordered or changed v4 model", () => {
  const changedSchema = structuredClone(schema);
  [changedSchema.model.features[0], changedSchema.model.features[1]] = [
    changedSchema.model.features[1],
    changedSchema.model.features[0],
  ];

  expectError(errorsFor(candidate(), changedSchema), "v4 model signature changed");
});

test("the future web gate must be chained from the root gate", () => {
  const rootPackage = {
    packageManager: "pnpm@11.10.0",
    engines: { node: ">=20" },
    scripts: { gate: "node gate/check-contract.mjs && pnpm --dir web gate" },
  };
  const webPackage = {
    private: true,
    scripts: {
      typecheck: "tsc --noEmit",
      lint: "eslint .",
      test: "vitest run",
      build: "vite build",
      gate: "pnpm typecheck && pnpm lint && pnpm test && pnpm build",
    },
    dependencies: {
      react: "^19.0.0",
      "react-dom": "^19.0.0",
    },
    devDependencies: {
      typescript: "^5.0.0",
      vite: "^7.0.0",
      vitest: "^3.0.0",
      tailwindcss: "^4.0.0",
    },
  };

  assert.deepEqual(
    validateWorkspace({
      packageJson: rootPackage,
      hasWeb: true,
      webPackageJson: webPackage,
      webTsconfigSources: ['{ "compilerOptions": { "strict": true } }'],
      nodeVersion: "20.0.0",
      pnpmLockfile: "lockfileVersion: '9.0'\n",
    }).errors,
    [],
  );

  rootPackage.scripts.gate = "node gate/check-contract.mjs";
  expectError(
    validateWorkspace({
      packageJson: rootPackage,
      hasWeb: true,
      webPackageJson: webPackage,
      webTsconfigSources: ['{ "compilerOptions": { "strict": true } }'],
      nodeVersion: "20.0.0",
      pnpmLockfile: "lockfileVersion: '9.0'\n",
    }).errors,
    "pnpm --dir web gate",
  );

  rootPackage.scripts.gate = "node gate/check-contract.mjs && pnpm --dir web gate";
  webPackage.dependencies.react = "^17.0.0";
  expectError(
    validateWorkspace({
      packageJson: rootPackage,
      hasWeb: true,
      webPackageJson: webPackage,
      webTsconfigSources: ['{ "compilerOptions": { "strict": true } }'],
      nodeVersion: "20.0.0",
      pnpmLockfile: "lockfileVersion: '9.0'\n",
    }).errors,
    "dependencies.react must target React 18 or newer",
  );

  webPackage.dependencies.react = "^19.0.0";
  webPackage.scripts.test = "node --test";
  expectError(
    validateWorkspace({
      packageJson: rootPackage,
      hasWeb: true,
      webPackageJson: webPackage,
      webTsconfigSources: ['{ "compilerOptions": { "strict": true } }'],
      nodeVersion: "20.0.0",
      pnpmLockfile: "lockfileVersion: '9.0'\n",
    }).errors,
    "scripts.test must run Vitest",
  );

  webPackage.scripts.test = "vitest run";
  expectError(
    validateWorkspace({
      packageJson: rootPackage,
      hasWeb: true,
      webPackageJson: webPackage,
      webTsconfigSources: ['{ "compilerOptions": { "strict": true } }'],
      nodeVersion: "20.0.0",
      pnpmLockfile: "lockfileVersion: '8.0'\n",
    }).errors,
    "pnpm-lock.yaml must use lockfileVersion 9.0",
  );
});
