/**
 * Canonical EEG frequency band definitions.
 *
 * Used by the DSP pipeline for spectral estimation and by the Intent Engine
 * for feature selection. All agents must use these constants — never hardcode
 * frequency ranges inline.
 *
 * Reference: standard clinical and BCI literature band definitions,
 * consistent with BCI2000 implementations (Schalk et al., 2004).
 */

import type { BandName } from "../schema/FeatureVector.js";

export interface BandDefinition {
  /** Band name, matches the BandName union type. */
  name: BandName;
  /** Lower cutoff frequency in Hz (inclusive). */
  lowHz: number;
  /** Upper cutoff frequency in Hz (inclusive). */
  highHz: number;
  /** Typical BCI relevance — what this band encodes. */
  description: string;
}

/**
 * Ordered list of all canonical EEG bands, from lowest to highest frequency.
 */
export const SIGNAL_BANDS: Record<BandName, BandDefinition> = {
  delta: {
    name: "delta",
    lowHz: 0.5,
    highHz: 4,
    description: "Deep sleep, slow cortical potentials (SCP). Used in SCP-BCI paradigms.",
  },
  theta: {
    name: "theta",
    lowHz: 4,
    highHz: 8,
    description: "Drowsiness, memory encoding, frontal midline activity.",
  },
  alpha: {
    name: "alpha",
    lowHz: 8,
    highHz: 12,
    description: "Sensorimotor idle rhythm (mu). ERD during motor imagery = left/right control.",
  },
  beta: {
    name: "beta",
    lowHz: 18,
    highHz: 26,
    description: "Active motor control, cognitive engagement. ERS after movement cessation.",
  },
  gamma: {
    name: "gamma",
    lowHz: 30,
    highHz: 80,
    description: "High-level cognitive binding, attention. Sensitive to muscle artifact.",
  },
  high_gamma: {
    name: "high_gamma",
    lowHz: 80,
    highHz: 200,
    description: "Broadband high-gamma: primary cortex activity in ECoG. Not reliably in scalp EEG.",
  },
};

/**
 * The two bands most critical for motor imagery BCI classification.
 * BCI2000 cursor control uses power in these bands at sensorimotor cortex (C3/C4).
 */
export const MOTOR_IMAGERY_BANDS: BandName[] = ["alpha", "beta"];

/**
 * Bands used for P300 evoked potential detection.
 * P300 is a broadband response peaking ~300 ms post-stimulus, prominent in delta/theta.
 */
export const P300_BANDS: BandName[] = ["delta", "theta"];

/**
 * Bands most susceptible to EMG artifact contamination.
 * Artifact rejection should be applied before computing these bands.
 */
export const EMG_CONTAMINATED_BANDS: BandName[] = ["gamma", "high_gamma"];
