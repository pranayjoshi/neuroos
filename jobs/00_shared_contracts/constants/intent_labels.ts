/**
 * Canonical intent label definitions.
 *
 * These labels are the vocabulary of NeuroOS — every component (Intent Engine,
 * Developer SDK, UI feedback) must use exactly these strings.
 *
 * App developers receive IntentEvents with one of these labels. They should
 * never parse raw signal data; they only react to these typed labels.
 */

import type { IntentLabel } from "../schema/IntentEvent.js";

export interface IntentLabelDefinition {
  label: IntentLabel;
  /** Human-readable display name for UI rendering. */
  displayName: string;
  /** Which BCI paradigm(s) can produce this intent. */
  paradigms: string[];
  /** Typical brain regions and frequency bands involved. */
  neuralBasis: string;
  /** Typical classification accuracy range in well-trained subjects. */
  typicalAccuracyRange: [number, number];
  /** Example application use cases. */
  examples: string[];
}

export const INTENT_LABEL_DEFINITIONS: Record<IntentLabel, IntentLabelDefinition> = {
  motor_imagery_left: {
    label: "motor_imagery_left",
    displayName: "Left Hand Imagery",
    paradigms: ["motor_imagery"],
    neuralBasis: "ERD in alpha (8–12 Hz) and beta (18–26 Hz) over right sensorimotor cortex (C4). ERS over left (C3).",
    typicalAccuracyRange: [0.65, 0.95],
    examples: ["cursor left", "scroll left", "select left option"],
  },
  motor_imagery_right: {
    label: "motor_imagery_right",
    displayName: "Right Hand Imagery",
    paradigms: ["motor_imagery"],
    neuralBasis: "ERD in alpha/beta over left sensorimotor cortex (C3). ERS over right (C4).",
    typicalAccuracyRange: [0.65, 0.95],
    examples: ["cursor right", "scroll right", "select right option", "click"],
  },
  motor_imagery_both_hands: {
    label: "motor_imagery_both_hands",
    displayName: "Both Hands Imagery",
    paradigms: ["motor_imagery"],
    neuralBasis: "Bilateral ERD in alpha/beta over C3 and C4.",
    typicalAccuracyRange: [0.60, 0.90],
    examples: ["zoom in", "confirm", "hold"],
  },
  motor_imagery_feet: {
    label: "motor_imagery_feet",
    displayName: "Feet Imagery",
    paradigms: ["motor_imagery"],
    neuralBasis: "ERD in alpha/beta over central-parietal region (Cz).",
    typicalAccuracyRange: [0.60, 0.88],
    examples: ["scroll down", "accelerate (game)", "select bottom option"],
  },
  motor_imagery_rest: {
    label: "motor_imagery_rest",
    displayName: "Rest / Idle",
    paradigms: ["motor_imagery", "free"],
    neuralBasis: "Resting ERS (alpha/beta synchronization) across sensorimotor cortex.",
    typicalAccuracyRange: [0.75, 0.98],
    examples: ["no action", "pause", "idle state"],
  },
  p300_target: {
    label: "p300_target",
    displayName: "P300 Target",
    paradigms: ["p300_speller"],
    neuralBasis: "Positive deflection ~300 ms post-stimulus over parietal cortex (Pz). Oddball response.",
    typicalAccuracyRange: [0.80, 0.99],
    examples: ["selected character in speller", "chosen menu item"],
  },
  p300_non_target: {
    label: "p300_non_target",
    displayName: "P300 Non-Target",
    paradigms: ["p300_speller"],
    neuralBasis: "No significant P300 component. Standard (frequent) stimulus response.",
    typicalAccuracyRange: [0.80, 0.99],
    examples: ["unselected character", "unchosen stimulus"],
  },
  scp_positive: {
    label: "scp_positive",
    displayName: "Cortical Positivity",
    paradigms: ["scp_control"],
    neuralBasis: "Positive slow cortical potential shift (0.5–10 s) over Cz. Cortical deactivation.",
    typicalAccuracyRange: [0.70, 0.90],
    examples: ["cursor up", "binary yes"],
  },
  scp_negative: {
    label: "scp_negative",
    displayName: "Cortical Negativity",
    paradigms: ["scp_control"],
    neuralBasis: "Negative SCP shift over Cz. Cortical activation, preparatory state.",
    typicalAccuracyRange: [0.70, 0.90],
    examples: ["cursor down", "binary no"],
  },
  attention_high: {
    label: "attention_high",
    displayName: "High Attention",
    paradigms: ["free"],
    neuralBasis: "Alpha suppression (ERD) across parietal and occipital regions. Theta increase at Fz.",
    typicalAccuracyRange: [0.60, 0.80],
    examples: ["focus mode on", "reading mode", "active monitoring"],
  },
  attention_low: {
    label: "attention_low",
    displayName: "Low Attention / Drowsy",
    paradigms: ["free"],
    neuralBasis: "Alpha increase, theta increase at frontal regions. Beta decrease.",
    typicalAccuracyRange: [0.60, 0.80],
    examples: ["break reminder", "alert trigger", "cognitive load relief"],
  },
  blink: {
    label: "blink",
    displayName: "Eye Blink",
    paradigms: ["free"],
    neuralBasis: "Large frontal artifact (Fp1/Fp2), ~200 ms duration. EOG-based detection.",
    typicalAccuracyRange: [0.90, 0.99],
    examples: ["single blink = click", "double blink = back", "coded blink sequences"],
  },
  jaw_clench: {
    label: "jaw_clench",
    displayName: "Jaw Clench",
    paradigms: ["free"],
    neuralBasis: "High-amplitude EMG burst across temporal channels (T3/T4), 20–500 Hz.",
    typicalAccuracyRange: [0.90, 0.99],
    examples: ["emergency stop", "mode switch", "push-to-talk"],
  },
  idle: {
    label: "idle",
    displayName: "Idle",
    paradigms: ["motor_imagery", "p300_speller", "scp_control", "free"],
    neuralBasis: "Below-threshold confidence across all other labels.",
    typicalAccuracyRange: [0.85, 0.99],
    examples: ["no command issued", "system waiting"],
  },
};
