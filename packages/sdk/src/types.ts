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
} from "@neuroos/shared-contracts/schema";

import type {
  DeviceAdapterConfig,
  DeviceDiagnostics,
  DeviceInfo,
  DeviceState,
  IntentLabel,
  SessionMetadata,
} from "@neuroos/shared-contracts/schema";

export interface NeuroOSClientConfig {
  baseUrl?: string;
  timeout?: number;
  reconnect?: boolean;
  reconnectDelayMs?: number;
}

export interface RegisterDeviceResponse {
  deviceId: string;
  state: DeviceState;
}

export interface ListDevicesResponse {
  devices: Array<{
    deviceId: string;
    adapterName: string;
    state: DeviceState;
  }>;
}

export interface SessionStartParams {
  deviceId: string;
  subjectId: string;
  sessionName: string;
  paradigm: "motor_imagery" | "p300_speller" | "scp_control" | "free";
}

export interface DiagnosticsResponse {
  device: {
    deviceId: string | null;
    adapterName: string | null;
    state: DeviceState | null;
    diagnostics: DeviceDiagnostics | null;
  };
  pipeline: {
    meanLatencyMs: number;
    p95LatencyMs: number;
    p99LatencyMs: number;
    maxLatencyMs: number;
    jitterMs: number;
    droppedFrames: number;
    currentScenario: string | null;
  };
  session: SessionMetadata | null;
}

export type PartialDeviceAdapterConfig = Partial<
  Omit<DeviceAdapterConfig, "driverOptions"> & {
    driverOptions?: Record<string, unknown>;
    pluginPath?: string;
  }
>;

export interface DeviceListItem {
  deviceId: string;
  adapterName: string;
  state: DeviceState;
}

export type ServerMessage =
  | { type: "connected"; sessionId: string | null; deviceId: string | null; version: string }
  | { type: "intent"; data: Record<string, unknown> }
  | { type: "session_started"; session: SessionMetadata }
  | { type: "session_stopped"; sessionId: string; totalFrames: number }
  | { type: "feedback_ack"; intentId: string }
  | { type: "error"; code: string; message: string };

export type ClientMessage =
  | { type: "feedback"; intentId: string; trueLabel: IntentLabel }
  | { type: "ping" };
