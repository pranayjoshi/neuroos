# Signal Parameters Reference — Data Generator Context

This document gives the Data Generator agent the domain knowledge needed to synthesize
realistic EEG and EMG signals. All numerical values come from the BCI literature.

---

## EEG Signal Characteristics

### Amplitude Ranges (μV, scalp EEG)

| Component | Typical Range | Notes |
|---|---|---|
| Background noise floor | 1–5 μV | White noise from amplifier |
| Alpha rhythm (eyes closed) | 10–100 μV | Occipital, parietal; posterior dominant |
| Sensorimotor alpha/mu | 5–20 μV | C3/C4; reduced during movement |
| Beta rhythm | 2–10 μV | Smaller than alpha |
| Slow cortical potential | 10–50 μV | Very slow, 0.5–10 s duration |
| P300 evoked potential | 5–30 μV | Positive peak ~300 ms post-stimulus at Pz |
| Eye blink artifact | 50–500 μV | Fp1, Fp2; ~200 ms duration |
| Eye movement artifact | 10–200 μV | Fp1, Fp2; polarity depends on direction |

### Spatial Correlation (10-20 system, 16-channel cap)

Nearby electrodes are highly correlated (ρ > 0.8). Distant electrodes are less correlated.
Use a spatial covariance matrix when synthesizing multi-channel signals:

```
Channel pairs with high correlation (ρ > 0.7):
  Fp1↔Fp2, F3↔F4, C3↔C4, P3↔P4, O1↔O2
  F3↔C3, F4↔C4 (ipsilateral frontal↔central)
  C3↔P3, C4↔P4 (ipsilateral central↔parietal)

Channel pairs with low correlation (ρ < 0.3):
  Fp1↔O2, F3↔O1, C3↔Fz (contralateral, distant)
```

**Synthesis approach:** Generate independent noise per channel, then convolve with spatial
mixing matrix A where AA^T = desired covariance matrix Σ.

### EEG Frequency Bands — Power Spectral Density Profile

Background EEG (rest, eyes open) follows approximately 1/f^α power spectrum with α ≈ 1.

```
Relative power (normalized to total power):
  delta (0.5–4 Hz):     25–35%
  theta (4–8 Hz):       10–20%
  alpha (8–12 Hz):      20–40%  (eyes closed; drops with eyes open)
  beta  (18–26 Hz):     10–20%
  gamma (30–80 Hz):     5–10%
```

### Motor Imagery ERD/ERS

Event-Related Desynchronization (ERD) = power decrease relative to baseline.
Event-Related Synchronization (ERS) = power increase.

**Left hand imagery:**
- C4 (right sensorimotor): ERD in alpha −20 to −40%, ERD in beta −15 to −30%
- C3 (left sensorimotor): ERS in alpha +10 to +20% (ipsilateral)

**Right hand imagery:**
- C3 (left sensorimotor): ERD in alpha −20 to −40%, ERD in beta −15 to −30%
- C4 (right sensorimotor): ERS in alpha +10 to +20% (ipsilateral)

**Feet imagery:**
- Cz (vertex): ERD in alpha/beta, bilateral

**Synthesis:** Multiply baseline alpha/beta amplitudes at target channels by (1 + erd_factor)
where erd_factor ∈ [−0.4, +0.2] depending on scenario and channel.

### P300 Evoked Potential

- Latency: 250–400 ms post-stimulus (use 300 ms as default)
- Polarity: positive
- Amplitude: 5–30 μV peak
- Topography: maximal at Pz, Cz; minimal at frontal sites
- Waveform shape: approximately Gaussian, FWHM ~150 ms
- Background: averaged over 15+ trials for clean detection

**Synthesis:**
```python
import numpy as np

def p300_component(t_sec: float, onset_sec: float = 0.3, amplitude_uv: float = 10.0) -> float:
    sigma = 0.075  # 75 ms std → ~150 ms FWHM
    return amplitude_uv * np.exp(-0.5 * ((t_sec - onset_sec) / sigma) ** 2)
```

### Slow Cortical Potential (SCP)

- Duration: 0.5–10 s (use 2 s for cursor control paradigm)
- Amplitude: 10–50 μV
- Reference: vertex (Cz) referenced to mastoids
- Negativity = cortical activation; positivity = cortical deactivation

**Synthesis:** Use a sigmoidal ramp reaching target amplitude over 500 ms, held for
remaining trial duration, then ramped back.

---

## EMG Signal Characteristics

### Amplitude Ranges (μV, surface EMG)

| Contraction level | Typical Range |
|---|---|
| Rest (no contraction) | 5–20 μV (noise floor) |
| Mild contraction | 200–500 μV |
| Strong contraction (jaw clench) | 1000–5000 μV |
| Max voluntary contraction | 2000–10000 μV |

### Frequency Content

- Bandwidth: 20–500 Hz (use 20 Hz highpass + 500 Hz lowpass)
- Peak power: 50–150 Hz
- Spectrum: broadband, roughly Gaussian in log-frequency

### Artifact Contamination of EEG

EMG from jaw/temporal muscles contaminates EEG channels T3, T4, F7, F8.
EMG from neck/occiput contaminates O1, O2, T5, T6.

**Spatial spread model:** Artifact amplitude decreases with electrode distance:
```
artifact_at_ch = base_amplitude * exp(-distance_cm / decay_constant)
decay_constant ≈ 3 cm for jaw EMG
```

---

## 10-20 Channel Labels (Standard Sets)

**8-channel set:** `["Fp1","F3","C3","P3","Fz","Cz","Pz","Oz"]`

**16-channel set:** `["Fp1","Fp2","F3","F4","C3","C4","P3","P4","O1","O2","F7","F8","T3","T4","T5","T6"]`

**64-channel set:** Use full 10-10 system (`["Fp1","Fpz","Fp2","AF7","AF3","AFz","AF4","AF8", ...]`)

**Motor imagery critical channels:** C3, Cz, C4 (sensorimotor cortex)
**P300 critical channels:** Pz, Cz, Fz
**SCP critical channel:** Cz (referenced to both mastoids A1+A2)

---

## Timing Parameters (BCI2000 Reference)

From BCI2000 Table I (Schalk et al., 2004):

| Configuration | Channels | Sample Rate | Samples/Frame | Frame Rate | Output Latency | Jitter |
|---|---|---|---|---|---|---|
| A (EEG typical) | 16 | 160 Hz | 10 | 16 Hz | 15.11 ms | 0.75 ms |
| B (EEG high-density) | 64 | 160 Hz | 10 | 16 Hz | ~15 ms | ~1 ms |
| C (spike recording) | 16 | 25000 Hz | 1000 | 25 Hz | ~15 ms | ~0.75 ms |

The Data Generator must reproduce Configuration A timing as the default.

---

## Noise Floor and SNR

Target SNR for realistic simulation:

| Scenario | SNR (dB) | Notes |
|---|---|---|
| Ideal (for unit tests) | 20–30 dB | Clean signal, minimal noise |
| Typical lab | 10–15 dB | Normal conditions |
| Poor electrode contact | 3–8 dB | High impedance (>20 kΩ) |
| Artifact heavy | <5 dB | EMG or motion contamination |

**SNR definition used:** `SNR_dB = 10 * log10(P_signal / P_noise)`
where `P_signal` = band power of interest, `P_noise` = broadband noise power.

---

## .ndf File Format

```
[ASCII Header — JSON on a single line, terminated by \r\n\r\n]
{"neuroos_version":"0.1.0","session_id":"...","device_info":{...},"pipeline_config":{...},...}

[Binary Body — little-endian float32]
Layout: [frame_0_ch0_s0, frame_0_ch0_s1, ..., frame_0_ch1_s0, ..., frame_0_chN_sM,
         frame_1_ch0_s0, ...]
Strides: samples_per_frame (innermost) → channels → frames (outermost)

[Sidecar — events file: recording.ndf.events]
JSON Lines: one EventMarker dict per line, with frameIndex field added
```

This format mirrors BCI2000's data storage: ASCII header + binary body + all event markers,
allowing full offline reconstruction of the session.
