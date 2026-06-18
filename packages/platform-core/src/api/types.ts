import type {
  IntentEvent,
  IntentLabel,
  SessionMetadata,
  DeviceState,
} from "@neuroos/shared-contracts/schema";

// ── Device routes ──────────────────────────────────────────────────────────

export interface RegisterDeviceBody {
  adapterName: string;
  config?: {
    numChannels?: number;
    sampleRateHz?: number;
    samplesPerFrame?: number;
    hardwareFilter?: boolean;
    channelLabels?: string[] | null;
    driverOptions?: Record<string, unknown>;
    pluginPath?: string;
  };
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

// ── Session routes ─────────────────────────────────────────────────────────

export interface StartSessionBody {
  deviceId: string;
  subjectId: string;
  sessionName: string;
  paradigm: "motor_imagery" | "p300_speller" | "scp_control" | "free";
}

export interface ListSessionsResponse {
  sessions: SessionMetadata[];
}

// ── WebSocket message types ────────────────────────────────────────────────

export type ServerMessage =
  | { type: "connected"; sessionId: string | null; deviceId: string | null; version: string }
  | { type: "intent"; data: IntentEvent }
  | { type: "session_started"; session: SessionMetadata }
  | { type: "session_stopped"; sessionId: string; totalFrames: number }
  | { type: "feedback_ack"; intentId: string }
  | { type: "error"; code: string; message: string };

export type ClientMessage =
  | { type: "feedback"; intentId: string; trueLabel: IntentLabel }
  | { type: "ping" };

// ── Operator routes ────────────────────────────────────────────────────────

export interface DiagnosticsResponse {
  device: {
    deviceId: string | null;
    adapterName: string | null;
    state: DeviceState | null;
    diagnostics: unknown;
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

export interface SignalResponse {
  frames: unknown[];
}

export interface FeaturesResponse {
  vectors: unknown[];
}

// ── Error responses ────────────────────────────────────────────────────────

export interface ErrorResponse {
  error: string;
  message: string;
  details?: unknown;
}
