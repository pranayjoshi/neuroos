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
} from "./RawSignalFrame";

export type {
  BandName,
  BandPowerMap,
  FeatureVector,
} from "./FeatureVector";

export type {
  IntentLabel,
  ClassifierType,
  IntentEvent,
  IntentEventSummary,
} from "./IntentEvent";

export type {
  DeviceState,
  DeviceAdapterEvents,
  DeviceAdapterError,
  DeviceErrorCode,
  DeviceAdapterConfig,
  DeviceAdapter,
  DeviceDiagnostics,
} from "./DeviceAdapter";

export type {
  SessionState,
  PipelineConfig,
  SessionMetadata,
} from "./SessionMetadata";
