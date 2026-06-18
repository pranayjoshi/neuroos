/**
 * Shared Contracts — central export point.
 *
 * All agents import types from this file:
 *   import type { RawSignalFrame, FeatureVector, IntentEvent } from '../00_shared_contracts/schema';
 */

export type {
  SignalType,
  RawSignalFrame,
  EventMarker,
  DeviceInfo,
} from "./RawSignalFrame.js";

export type {
  BandName,
  BandPowerMap,
  FeatureVector,
} from "./FeatureVector.js";

export type {
  IntentLabel,
  ClassifierType,
  IntentEvent,
  IntentEventSummary,
} from "./IntentEvent.js";

export type {
  DeviceState,
  DeviceAdapterEvents,
  DeviceAdapterError,
  DeviceErrorCode,
  DeviceAdapterConfig,
  DeviceAdapter,
  DeviceDiagnostics,
} from "./DeviceAdapter.js";

export type {
  SessionState,
  PipelineConfig,
  SessionMetadata,
} from "./SessionMetadata.js";
