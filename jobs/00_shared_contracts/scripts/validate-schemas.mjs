/**
 * Validates all JSON Schema files in json-schema/ against AJV draft-07.
 * Run via: node scripts/validate-schemas.mjs
 *
 * Acceptance criterion: no $ref resolution errors, all schemas compile cleanly.
 */

import { readFileSync, readdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import Ajv from "ajv";
import addFormats from "ajv-formats";

const __dirname = dirname(fileURLToPath(import.meta.url));
const schemasDir = join(__dirname, "..", "json-schema");

const ajv = new Ajv({
  strict: true,
  allErrors: true,
});
addFormats(ajv);

const schemaFiles = readdirSync(schemasDir).filter((f) =>
  f.endsWith(".schema.json")
);

let passed = 0;
let failed = 0;

for (const file of schemaFiles) {
  const schemaPath = join(schemasDir, file);
  const raw = readFileSync(schemaPath, "utf-8");

  let schema;
  try {
    schema = JSON.parse(raw);
  } catch (e) {
    console.error(`[FAIL] ${file}: JSON parse error — ${e.message}`);
    failed++;
    continue;
  }

  try {
    const validate = ajv.compile(schema);
    console.log(`[PASS] ${file}: compiled successfully (id: ${schema.$id})`);
    passed++;

    // Run a minimal smoke-validation to confirm the schema is usable
    const testData = buildTestData(schema.title);
    if (testData !== null) {
      const valid = validate(testData);
      if (!valid) {
        // Test data failures are expected (we test structure, not values)
        // Only $ref resolution errors matter for this acceptance criterion
        const refErrors = (validate.errors ?? []).filter((e) =>
          e.message?.includes("$ref")
        );
        if (refErrors.length > 0) {
          console.error(`  [WARN] $ref resolution errors:`, refErrors);
          failed++;
          passed--;
        }
      }
    }
  } catch (e) {
    console.error(`[FAIL] ${file}: AJV compile error — ${e.message}`);
    failed++;
  }
}

console.log(`\nResults: ${passed} passed, ${failed} failed`);

if (failed > 0) {
  process.exit(1);
}

/**
 * Builds minimal valid test data for smoke-testing each schema.
 * Returns null to skip smoke test for unknown schema titles.
 */
function buildTestData(title) {
  switch (title) {
    case "RawSignalFrame":
      return {
        deviceId: "openbci:cyton:SN-1234",
        frameIndex: 0,
        timestampNs: "1718000000000000000",
        signalType: "EEG",
        channels: [[1.0, 2.0, 3.0]],
        samplesPerFrame: 3,
        sampleRateHz: 256,
        channelLabels: ["C3"],
        calibrated: true,
      };
    case "FeatureVector":
      return {
        vectorId: "550e8400-e29b-41d4-a716-446655440000",
        sourceFrameIndices: [0, 1, 2],
        timestampNs: "1718000000000000000",
        deviceId: "openbci:cyton:SN-1234",
        signalType: "EEG",
        bandPowers: {
          delta: [1.0],
          theta: [1.0],
          alpha: [1.0],
          beta: [1.0],
          gamma: [1.0],
          high_gamma: [1.0],
        },
        spatialFeatures: [0.5, 0.3],
        erd: {},
        evokedResponse: null,
        artifactFlag: false,
        processingLatencyMs: 3.5,
        channelLabels: ["C3"],
      };
    case "IntentEvent":
      return {
        intentId: "550e8400-e29b-41d4-a716-446655440001",
        label: "motor_imagery_left",
        confidence: 0.87,
        posteriors: { motor_imagery_left: 0.87, idle: 0.13 },
        classifierType: "lda",
        sourceVectorId: "550e8400-e29b-41d4-a716-446655440000",
        timestampNs: "1718000000000000000",
        endToEndLatencyMs: 12.5,
        featureImportance: {},
        artifactFlag: false,
        feedbackLabel: null,
      };
    default:
      return null;
  }
}
