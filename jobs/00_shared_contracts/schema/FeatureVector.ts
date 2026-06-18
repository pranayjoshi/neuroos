/**
 * FeatureVector — the output of the DSP Pipeline.
 *
 * Represents extracted signal features from one or more RawSignalFrames.
 * Modeled after BCI2000's signal processing module output (Schalk et al., 2004):
 * calibration → spatial filter → temporal filter → feature extraction.
 *
 * The FeatureVector is intentionally hardware-agnostic: the Intent Engine
 * only ever sees this structure, never raw samples.
 */

import type { SignalType } from "./RawSignalFrame.js";

/** Canonical EEG frequency band names. */
export type BandName = "delta" | "theta" | "alpha" | "beta" | "gamma" | "high_gamma";

/**
 * Band power values per channel, in dB or normalized units.
 * Map key is the BandName; value is an array with one entry per channel.
 */
export type BandPowerMap = Record<BandName, Float32Array>;

/**
 * Processed feature vector produced by the DSP pipeline for one analysis window.
 */
export interface FeatureVector {
  /**
   * Unique ID for this feature vector. Should be traceable back to the
   * source RawSignalFrame(s) via `sourceFrameIndices`.
   */
  vectorId: string;

  /**
   * Indices of the source RawSignalFrames that contributed to this vector.
   * Typically a sliding window (e.g. last 10 frames = 625 ms at 160 Hz).
   */
  sourceFrameIndices: number[];

  /**
   * Timestamp of the most recent sample included, nanoseconds since Unix epoch.
   * Used for end-to-end latency computation.
   */
  timestampNs: bigint;

  /** Device that produced the underlying raw signal. */
  deviceId: string;

  /** Signal modality of the underlying data. */
  signalType: SignalType;

  /**
   * Per-band, per-channel power estimates.
   * Shape of each Float32Array: [numChannels].
   * Computed via autoregressive spectral estimation (Burg method) or FFT.
   */
  bandPowers: BandPowerMap;

  /**
   * Output of the spatial filter stage.
   * One value per virtual channel (after CAR, Laplacian, or CSP).
   */
  spatialFeatures: Float32Array;

  /**
   * Event-related (de)synchronization values per band per channel.
   * ERD is negative (power decrease), ERS is positive (power increase).
   * Shape of each Float32Array: [numChannels].
   */
  erd: Partial<BandPowerMap>;

  /**
   * For P300-paradigm use: averaged evoked response waveform at Pz.
   * Length = number of time-domain samples in the averaging window.
   * Null when not in a P300 paradigm session.
   */
  evokedResponse: Float32Array | null;

  /**
   * True if an artifact (EMG burst, eye movement, amplifier saturation)
   * was detected in the contributing frames. The Intent Engine should
   * weight this vector's confidence accordingly.
   */
  artifactFlag: boolean;

  /**
   * Artifact category when `artifactFlag` is true.
   */
  artifactType?: "emg" | "ocular" | "saturation" | "motion";

  /**
   * Time elapsed from first sample acquisition to feature vector emission, in ms.
   * DSP pipeline budget: <5 ms per frame.
   */
  processingLatencyMs: number;

  /**
   * Channel labels after spatial filtering.
   * May differ from raw labels when virtual channels are computed (e.g. CSP).
   */
  channelLabels: string[];
}
