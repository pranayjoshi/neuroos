# Job 00 — Shared Contracts

**Role:** Prerequisite agent — defines the typed data contracts all other agents import.  
**Must complete before:** Jobs 01, 02, 03, 04, 05, 06

---

## Scope

Create the `schema/` and `constants/` directories with fully typed TypeScript definitions and JSON Schema equivalents for every inter-module data boundary in NeuroOS.

Do NOT implement any logic, generators, filters, classifiers, or API handlers. This job is pure types and constants.

---

## Deliverables

### `schema/`
- `RawSignalFrame.ts` — the data frame emitted by hardware adapters / data generators
- `FeatureVector.ts` — the processed output of the DSP pipeline
- `IntentEvent.ts` — the classified intent emitted by the Intent Engine
- `DeviceAdapter.ts` — abstract interface all hardware drivers must implement
- `SessionMetadata.ts` — session lifecycle data (start time, device info, config snapshot)
- `index.ts` — re-exports all of the above

### `constants/`
- `signal_bands.ts` — canonical EEG frequency band definitions
- `signal_types.ts` — supported signal modalities and their typical parameters
- `intent_labels.ts` — canonical intent label strings shared across engine and SDK
- `index.ts` — re-exports all constants

### `json-schema/`
- `RawSignalFrame.schema.json` — JSON Schema draft-07 version for runtime validation
- `FeatureVector.schema.json`
- `IntentEvent.schema.json`

---

## Acceptance Criteria

- [ ] `tsc --noEmit` passes with zero errors on all `.ts` files in this folder
- [ ] All exported types have JSDoc comments explaining every field
- [ ] JSON Schema files validate correctly against `ajv` (no `$ref` resolution errors)
- [ ] `schema/index.ts` exports every type so consumers can `import { RawSignalFrame } from '../00_shared_contracts/schema'`
- [ ] No logic code (functions, classes with methods, loops) — types and `const` objects only

---

## Must NOT Do

- Implement any runtime logic, generators, or processors
- Import from any other job folder
- Pull in npm packages (output is pure TypeScript, zero runtime dependencies)
