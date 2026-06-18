/**
 * RawSignalFrame — the fundamental data unit produced by any BCI hardware adapter.
 *
 * Modeled after the BCI2000 source module output (Schalk et al., 2004).
 * A frame represents one block of samples acquired at a fixed sample rate across
 * all channels. The source module acts as the system clock — downstream modules
 * initiate their processing cycle upon receipt of each frame.
 */

/** Supported signal modalities. */
export type SignalType = "EEG" | "EMG" | "ECoG" | "LFP" | "SPIKE";

/**
 * A single block of multi-channel bio-signal samples.
 *
 * All sample values are in microvolts (μV) after calibration.
 * Raw A/D unit frames (pre-calibration) MUST set `calibrated: false`.
 */
export interface RawSignalFrame {
  /**
   * Unique identifier for the device that produced this frame.
   * Format: `<vendor>:<model>:<serial>` e.g. `"openbci:cyton:SN-1234"`.
   */
  deviceId: string;

  /**
   * Frame sequence number, monotonically increasing per device session.
   * Gaps indicate dropped frames.
   */
  frameIndex: number;

  /**
   * Wall-clock timestamp of the first sample in this frame, in nanoseconds
   * since Unix epoch. Used to compute end-to-end latency.
   */
  timestampNs: bigint;

  /** Signal modality. Determines downstream filter and feature extraction paths. */
  signalType: SignalType;

  /**
   * Sample data: outer array is channels, inner array is samples within this frame.
   * Shape: [numChannels][samplesPerFrame]
   * All values in microvolts (μV) when `calibrated === true`.
   */
  channels: Float32Array[];

  /**
   * Number of samples per channel in this frame.
   * Typical values: 10 (at 160 Hz, 16 Hz update rate), 16 (at 256 Hz).
   */
  samplesPerFrame: number;

  /**
   * Hardware sample rate in Hz.
   * Typical EEG: 160–512 Hz. Typical spike recording: 25 000 Hz.
   */
  sampleRateHz: number;

  /**
   * Channel labels following the 10-20 system (e.g. ["Fp1","Fp2","C3","C4"]).
   * Length must equal `channels.length`.
   */
  channelLabels: string[];

  /**
   * Whether sample values have been converted from A/D units to microvolts.
   * Calibration MUST be applied in the DSP Calibrator before downstream use.
   */
  calibrated: boolean;

  /**
   * Optional event markers co-registered with this frame.
   * Bit-packed event codes (1–16 bits each), consistent with BCI2000 state vector.
   */
  eventMarkers?: EventMarker[];
}

/**
 * An event marker co-registered with a signal frame.
 * Allows full offline reconstruction of the experimental session.
 */
export interface EventMarker {
  /** Human-readable event name, e.g. `"stimulus_onset"`, `"trial_start"`. */
  name: string;
  /** Numeric code (1–65535). */
  code: number;
  /** Sample index within the frame at which this event occurred. */
  sampleOffset: number;
}

/**
 * Metadata emitted once at session start, describing hardware configuration.
 */
export interface DeviceInfo {
  deviceId: string;
  vendor: string;
  model: string;
  firmwareVersion: string;
  numChannels: number;
  sampleRateHz: number;
  signalType: SignalType;
  channelLabels: string[];
  adResolutionBits: number;
  referenceElectrode: string;
}
