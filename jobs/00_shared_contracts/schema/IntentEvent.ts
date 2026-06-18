/**
 * IntentEvent — the output of the Intent Engine.
 *
 * Represents a decoded user intention extracted from processed brain signals.
 * This is the primary developer-facing data type: app developers subscribe to
 * IntentEvent streams via the NeuroOS SDK without knowing anything about
 * signal processing or ML internals.
 *
 * Analogous to a UIEvent in iOS — the OS abstracts hardware complexity
 * and delivers clean, typed intent objects to application code.
 */

import type { BandName } from "./FeatureVector";

/** Canonical set of supported intent labels. See `constants/intent_labels.ts`. */
export type IntentLabel =
  | "motor_imagery_left"
  | "motor_imagery_right"
  | "motor_imagery_both_hands"
  | "motor_imagery_feet"
  | "motor_imagery_rest"
  | "p300_target"
  | "p300_non_target"
  | "scp_positive"
  | "scp_negative"
  | "attention_high"
  | "attention_low"
  | "blink"
  | "jaw_clench"
  | "idle";

/** Classification method that produced this intent. */
export type ClassifierType =
  | "lda"
  | "csp_lda"
  | "p300_template"
  | "cnn"
  | "lstm"
  | "transformer"
  | "ensemble";

/**
 * A decoded user intent, emitted by the Intent Engine at the configured
 * inference rate (default: 16 Hz).
 */
export interface IntentEvent {
  /**
   * Unique identifier for this event, UUID v4.
   */
  intentId: string;

  /**
   * Decoded intent label with the highest posterior probability.
   */
  label: IntentLabel;

  /**
   * Posterior probability of the winning label, in [0, 1].
   * Values below the session-configured threshold are suppressed.
   */
  confidence: number;

  /**
   * Full posterior distribution over all intent labels.
   * Probabilities sum to 1.0. Enables downstream apps to implement
   * their own thresholding or soft-decision logic.
   */
  posteriors: Partial<Record<IntentLabel, number>>;

  /**
   * Classifier model that produced this intent.
   */
  classifierType: ClassifierType;

  /**
   * ID of the FeatureVector that was classified to produce this event.
   */
  sourceVectorId: string;

  /**
   * Timestamp of the most recent sample that contributed to this event,
   * in nanoseconds since Unix epoch. Used to compute end-to-end latency.
   */
  timestampNs: bigint;

  /**
   * End-to-end latency: time from first sample acquisition to IntentEvent
   * emission, in milliseconds. BCI2000 benchmark target: <15 ms.
   */
  endToEndLatencyMs: number;

  /**
   * The band-power features that most influenced this classification.
   * Useful for real-time feedback and adaptive training.
   * Keys are band names; values are per-channel importance weights.
   */
  featureImportance: Partial<Record<BandName, Float32Array>>;

  /**
   * True when this event was produced during an artifact-flagged window.
   * Apps should treat high-artifact events as lower quality.
   */
  artifactFlag: boolean;

  /**
   * Feedback label provided by the application after displaying this intent.
   * Populated by `OnlineTrainer` when the user confirms or corrects the intent.
   * Null until feedback arrives.
   */
  feedbackLabel: IntentLabel | null;
}

/**
 * Lightweight summary of an IntentEvent, used in SDK streaming responses
 * where full feature data is not needed.
 */
export interface IntentEventSummary {
  intentId: string;
  label: IntentLabel;
  confidence: number;
  endToEndLatencyMs: number;
  timestampNs: bigint;
  artifactFlag: boolean;
}
