export { NeuroOS, NeuroOSClient } from "./client.js";
export { IntentStream } from "./stream.js";
export type { IntentStreamOptions } from "./stream.js";
export type {
  IntentEvent,
  IntentEventSummary,
  IntentLabel,
  ClassifierType,
  SessionMetadata,
  SessionState,
  PipelineConfig,
  DeviceInfo,
  DeviceState,
  DeviceAdapterConfig,
  DeviceDiagnostics,
  NeuroOSClientConfig,
  SessionStartParams,
  PartialDeviceAdapterConfig,
} from "./types.js";
export {
  NeuroOSError,
  ConnectionError,
  SessionAlreadyActiveError,
  NoActiveSessionError,
  DeviceNotFoundError,
  StreamClosedError,
  ValidationError,
  TimeoutError,
} from "./errors.js";
export type { NeuroOSErrorCode } from "./errors.js";
