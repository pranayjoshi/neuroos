/**
 * SessionMetadata — lifecycle data for a NeuroOS recording session.
 *
 * A session corresponds to one continuous recording run: one device,
 * one pipeline configuration, one subject. Sessions are persisted by the
 * Platform Core's SessionManager and included in the .ndf file header.
 *
 * Modeled after BCI2000's operator module concept: parameters are defined
 * at session start and remain constant throughout a data file.
 */

import type { DeviceInfo } from "./RawSignalFrame";

/** Possible states for a session lifecycle. */
export type SessionState =
  | "initializing"
  | "active"
  | "paused"
  | "completed"
  | "error";

/**
 * Snapshot of pipeline configuration active for a session.
 * Mirrors neuroos.config.yaml structure for reproducibility.
 */
export interface PipelineConfig {
  /** DSP pipeline parameters. */
  dsp: {
    spatialFilterType: "car" | "laplacian" | "csp" | "none";
    temporalFilterType: "bandpass_fir" | "autoregressive" | "p300_average" | "slow_wave";
    /** Bandpass cutoff frequencies [low, high] in Hz. */
    bandpassHz: [number, number];
    /** Analysis window length in seconds. */
    windowLengthSec: number;
    /** Window step size in seconds (overlap = windowLength - stepSize). */
    windowStepSec: number;
  };

  /** Intent engine parameters. */
  intent: {
    classifierType: "lda" | "csp_lda" | "p300_template" | "cnn" | "lstm" | "ensemble";
    /** Path to saved model weights, relative to workspace root. */
    modelPath: string | null;
    /** Inference rate in Hz (how often IntentEvents are emitted). */
    inferenceRateHz: number;
    /** Minimum confidence threshold; events below this are suppressed. */
    confidenceThreshold: number;
  };

  /** Paradigm-specific settings. */
  paradigm: {
    type: "motor_imagery" | "p300_speller" | "scp_control" | "free";
    /** Trial length in seconds, null for self-paced paradigms. */
    trialLengthSec: number | null;
    /** Inter-trial interval in seconds. */
    itiSec: number;
  };
}

/**
 * Full metadata for one NeuroOS session.
 */
export interface SessionMetadata {
  /** Unique session identifier, UUID v4. */
  sessionId: string;

  /** Human-readable session name, set by operator. */
  sessionName: string;

  /** Subject identifier (anonymized). */
  subjectId: string;

  /** Current lifecycle state of the session. */
  state: SessionState;

  /** Milliseconds since Unix epoch when recording started. */
  startedAtMs: number;

  /** Milliseconds since Unix epoch when recording ended. Null if ongoing. */
  endedAtMs: number | null;

  /** Total frames acquired in this session. */
  totalFrames: number;

  /** Frames dropped due to acquisition errors. */
  droppedFrames: number;

  /** Device metadata snapshot taken at session start. */
  deviceInfo: DeviceInfo;

  /** Pipeline configuration active for this session. */
  pipelineConfig: PipelineConfig;

  /** Free-form notes added by the operator. */
  notes: string;

  /** NeuroOS version string. */
  neuroosVersion: string;
}
