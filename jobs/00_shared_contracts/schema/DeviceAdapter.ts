/**
 * DeviceAdapter — the hardware abstraction interface.
 *
 * Every BCI device driver (real or simulated) must implement this interface.
 * The Platform Core's DeviceRegistry validates adapters against this contract
 * at registration time.
 *
 * This is NeuroOS's equivalent of iOS's ExternalAccessory framework —
 * it defines exactly what the OS expects from any connected device,
 * making the system hardware-agnostic.
 *
 * Inspired by BCI2000's source module design: the adapter acts as the
 * system clock by controlling the acquisition rate.
 */

import type { DeviceInfo, RawSignalFrame } from "./RawSignalFrame";

/** Lifecycle state of a device adapter. */
export type DeviceState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "recording"
  | "paused"
  | "error";

/** Events emitted by a DeviceAdapter. */
export interface DeviceAdapterEvents {
  /** Emitted for each acquired frame. The primary data event. */
  frame: (frame: RawSignalFrame) => void;
  /** Emitted when device connection state changes. */
  stateChange: (state: DeviceState, previousState: DeviceState) => void;
  /** Emitted when a recoverable error occurs (e.g. transient packet loss). */
  error: (error: DeviceAdapterError) => void;
  /** Emitted once after successful connection with device metadata. */
  deviceInfo: (info: DeviceInfo) => void;
}

/** Error structure for device-level failures. */
export interface DeviceAdapterError {
  /** Machine-readable error code. */
  code: DeviceErrorCode;
  /** Human-readable description. */
  message: string;
  /** Whether the error is fatal (requires reconnect) or transient. */
  fatal: boolean;
  /** Optional underlying cause. */
  cause?: unknown;
}

export type DeviceErrorCode =
  | "CONNECTION_FAILED"
  | "PACKET_LOSS"
  | "HARDWARE_FAULT"
  | "UNSUPPORTED_SAMPLE_RATE"
  | "CALIBRATION_FAILED"
  | "TIMEOUT"
  | "UNKNOWN";

/**
 * Configuration passed to a DeviceAdapter at registration time.
 * Comes from `neuroos.config.yaml` via the Platform Core ConfigStore.
 */
export interface DeviceAdapterConfig {
  /** Desired sample rate. Adapter must validate against hardware capabilities. */
  sampleRateHz: number;
  /** Number of channels to acquire. */
  numChannels: number;
  /** Specific channel labels to acquire, or null for all channels. */
  channelLabels: string[] | null;
  /** Samples to include in each emitted RawSignalFrame. */
  samplesPerFrame: number;
  /** Whether to apply hardware-level bandpass filtering (if supported). */
  hardwareFilter: boolean;
  /** Hardware-specific options passed through opaquely. */
  driverOptions: Record<string, unknown>;
}

/**
 * The abstract interface every BCI device driver must implement.
 *
 * Usage pattern:
 * ```ts
 * const adapter = new MyBCIAdapter(config);
 * adapter.on("frame", (frame) => pipeline.process(frame));
 * await adapter.connect();
 * await adapter.startRecording();
 * // ... later ...
 * await adapter.stopRecording();
 * await adapter.disconnect();
 * ```
 */
export interface DeviceAdapter {
  /** Unique adapter identifier, matches DeviceInfo.deviceId format. */
  readonly deviceId: string;

  /** Human-readable adapter name shown in developer tools. */
  readonly adapterName: string;

  /** Current device lifecycle state. */
  readonly state: DeviceState;

  /**
   * Register an event listener. Must support at minimum the events
   * defined in DeviceAdapterEvents.
   */
  on<K extends keyof DeviceAdapterEvents>(
    event: K,
    listener: DeviceAdapterEvents[K]
  ): this;

  off<K extends keyof DeviceAdapterEvents>(
    event: K,
    listener: DeviceAdapterEvents[K]
  ): this;

  /**
   * Establish connection to the hardware device.
   * Resolves when the device is ready to record.
   * Rejects with DeviceAdapterError on failure.
   */
  connect(): Promise<DeviceInfo>;

  /**
   * Begin emitting RawSignalFrame events at the configured sample rate.
   * Device must be in `connected` state before calling.
   */
  startRecording(): Promise<void>;

  /**
   * Pause frame emission without disconnecting.
   * Resume with startRecording().
   */
  pauseRecording(): Promise<void>;

  /**
   * Stop frame emission and release hardware buffers.
   */
  stopRecording(): Promise<void>;

  /**
   * Disconnect from hardware and release all resources.
   */
  disconnect(): Promise<void>;

  /**
   * Return the most recent device diagnostics (impedance, battery, signal
   * quality). Useful for operator dashboards.
   */
  getDiagnostics(): Promise<DeviceDiagnostics>;
}

/** Hardware health metrics returned by getDiagnostics(). */
export interface DeviceDiagnostics {
  /** Per-channel impedance in kΩ. High impedance = poor contact. */
  impedanceKOhm: number[];
  /** Battery level 0–100, or null if not applicable. */
  batteryPercent: number | null;
  /** Signal quality index 0–1 per channel. */
  signalQuality: number[];
  /** Frames dropped since recording start. */
  droppedFrames: number;
  /** Timestamp of this diagnostic snapshot. */
  timestampMs: number;
}
