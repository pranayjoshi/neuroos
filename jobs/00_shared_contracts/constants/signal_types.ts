/**
 * Signal modality metadata — typical hardware parameters per SignalType.
 *
 * Used by the Data Generator to synthesize realistic signals and by the
 * DSP pipeline to select appropriate filter parameters.
 */

import type { SignalType } from "../schema/RawSignalFrame.js";

export interface SignalTypeProfile {
  type: SignalType;
  /** Typical sample rate range in Hz [min, max]. */
  sampleRateRangeHz: [number, number];
  /** Recommended sample rate for BCI use. */
  recommendedSampleRateHz: number;
  /** Typical amplitude range in μV [min peak, max peak]. */
  amplitudeRangeUV: [number, number];
  /** Frequency content range in Hz [lowest, highest relevant]. */
  frequencyRangeHz: [number, number];
  /** Typical number of acquisition channels. */
  typicalChannelCounts: number[];
  /** Primary electrode locations. */
  electrodeLocations: string;
  /** Brief description of signal origin and BCI use case. */
  description: string;
}

export const SIGNAL_TYPE_PROFILES: Record<SignalType, SignalTypeProfile> = {
  EEG: {
    type: "EEG",
    sampleRateRangeHz: [128, 512],
    recommendedSampleRateHz: 256,
    amplitudeRangeUV: [1, 100],
    frequencyRangeHz: [0.5, 80],
    typicalChannelCounts: [8, 16, 32, 64, 128, 256],
    electrodeLocations: "Scalp (10-20 system)",
    description:
      "Non-invasive scalp EEG. Primary modality for consumer BCI. " +
      "Sensorimotor rhythms, P300, SCP paradigms. 15–25 bit/min information transfer rate.",
  },
  EMG: {
    type: "EMG",
    sampleRateRangeHz: [1000, 10000],
    recommendedSampleRateHz: 2000,
    amplitudeRangeUV: [50, 5000],
    frequencyRangeHz: [20, 500],
    typicalChannelCounts: [2, 4, 8, 16],
    electrodeLocations: "Muscle surface (forearm, face, neck)",
    description:
      "Electromyography: muscle electrical activity. In NeuroOS, used as " +
      "artifact source in EEG (to detect and reject) and as independent " +
      "control signal for users with residual muscle control.",
  },
  ECoG: {
    type: "ECoG",
    sampleRateRangeHz: [1000, 30000],
    recommendedSampleRateHz: 2000,
    amplitudeRangeUV: [50, 1000],
    frequencyRangeHz: [1, 500],
    typicalChannelCounts: [32, 64, 128, 256],
    electrodeLocations: "Cortical surface (subdural grid/strip)",
    description:
      "Electrocorticography: invasive, requires surgery. High spatial " +
      "resolution and SNR. High-gamma band (80–200 Hz) encodes fine motor intent.",
  },
  LFP: {
    type: "LFP",
    sampleRateRangeHz: [1000, 30000],
    recommendedSampleRateHz: 30000,
    amplitudeRangeUV: [10, 500],
    frequencyRangeHz: [1, 300],
    typicalChannelCounts: [16, 32, 64, 128],
    electrodeLocations: "Intracortical (Utah array, tetrodes)",
    description:
      "Local field potentials: average activity of neural populations " +
      "around an intracortical electrode. Intermediate between single-unit and ECoG.",
  },
  SPIKE: {
    type: "SPIKE",
    sampleRateRangeHz: [20000, 40000],
    recommendedSampleRateHz: 30000,
    amplitudeRangeUV: [50, 500],
    frequencyRangeHz: [300, 10000],
    typicalChannelCounts: [16, 32, 96, 192],
    electrodeLocations: "Intracortical (Utah array, microwire)",
    description:
      "Single-unit / multi-unit action potentials. Highest information rate " +
      "(up to 6.5 bit/s per neuron). Requires invasive surgery. " +
      "BCI2000 Table I configuration C: 16 channels at 25 kHz.",
  },
};
