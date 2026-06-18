# DSP Operators Reference — DSP Pipeline Context

Algorithms and reference implementations for each operator in the NeuroOS DSP pipeline.
All values are grounded in the BCI2000 paper (Schalk et al., 2004) and standard EEG literature.

---

## 1. Calibration

### A/D to μV Conversion

BCI2000's first signal operator: linear transform of raw A/D integer samples to microvolts.

```
signal_uv[ch, t] = (raw_adu[ch, t] × gain_uv_per_adu) + offset_uv[ch]
```

**Typical gain values:**
- OpenBCI Cyton: 4.5 V / (2^23 × 24) ≈ 0.022 μV/count
- BrainProducts: device-specific, stored in device header

**DC removal (baseline correction):**
```python
# Sliding window baseline (500 ms default)
baseline = np.mean(baseline_buffer, axis=1, keepdims=True)  # [channels, 1]
signal_uv -= baseline
```

BCI2000: *"Subsequently, a baseline correction procedure subtracts the average
signal amplitude prior to output."*

---

## 2. Spatial Filters

### Common Average Reference (CAR)

Subtract the instantaneous mean across all channels. Reduces common-mode noise.
Equivalent to referencing each electrode to the average of all electrodes.

```python
def car(signal: np.ndarray) -> np.ndarray:
    # signal: [channels, samples]
    return signal - signal.mean(axis=0, keepdims=True)
```

**When to use:** General purpose, always safe. Default for NeuroOS.

### Small Laplacian

Subtract weighted average of surrounding channels. Improves spatial resolution.

```python
def laplacian(signal: np.ndarray, adjacency: dict[int, list[int]]) -> np.ndarray:
    # adjacency: {channel_idx: [neighbor_indices]}
    out = signal.copy()
    for ch, neighbors in adjacency.items():
        out[ch] -= signal[neighbors].mean(axis=0)
    return out
```

Standard adjacency for C3 (motor imagery): neighbors = [FC5, FC1, CP5, CP1]

**When to use:** Motor imagery, when channel layout is known.

### Common Spatial Patterns (CSP)

Supervised: finds spatial filters that maximize variance ratio between two classes.
Used for motor imagery classification.

```
Objective: W = argmax W^T Σ1 W / W^T (Σ1 + Σ2) W

Solution: generalized eigenvalue problem
  Σ1 W = λ (Σ1 + Σ2) W

Take first m and last m eigenvectors → 2m spatial filters
```

```python
from scipy.linalg import eigh

def fit_csp(X1: np.ndarray, X2: np.ndarray, n_components: int = 6):
    # X1, X2: [trials, channels, samples]
    cov1 = np.mean([x @ x.T / x.shape[1] for x in X1], axis=0)
    cov2 = np.mean([x @ x.T / x.shape[1] for x in X2], axis=0)
    eigenvalues, eigenvectors = eigh(cov1, cov1 + cov2)
    # Take m lowest and m highest eigenvalue filters
    idx = np.concatenate([np.arange(n_components//2), np.arange(-n_components//2, 0)])
    return eigenvectors[:, idx]  # W: [channels, n_components]

def apply_csp(signal: np.ndarray, W: np.ndarray) -> np.ndarray:
    # signal: [channels, samples]; W: [channels, n_components]
    return W.T @ signal  # → [n_components, samples]
```

**When to use:** Motor imagery (2-class). Requires calibration data from both classes.

---

## 3. Artifact Rejection

### EMG Burst Detection

High-frequency power ratio method (frequency-domain):

```python
def detect_emg(signal_uv: np.ndarray, sample_rate: int, threshold_sd: float = 3.0) -> bool:
    # signal: [channels, samples]
    # Compute power in EMG band (40–100 Hz) vs. EEG band (1–40 Hz)
    from scipy.signal import welch
    freqs, psd = welch(signal_uv, fs=sample_rate, nperseg=min(128, signal_uv.shape[1]))
    emg_power = psd[:, (freqs >= 40) & (freqs <= 100)].mean(axis=1)
    eeg_power = psd[:, (freqs >= 1) & (freqs <= 40)].mean(axis=1)
    ratio = emg_power / (eeg_power + 1e-10)
    # Flag if ratio exceeds running mean + threshold_sd * running_std
    return float(ratio.max()) > threshold_sd  # simplified; use z-score in production
```

### Ocular Artifact Detection

```python
def detect_ocular(signal_uv: np.ndarray, fp1_idx: int, fp2_idx: int,
                  threshold_uv: float = 100.0) -> bool:
    fp_amplitude = np.abs(signal_uv[[fp1_idx, fp2_idx]]).max()
    return float(fp_amplitude) > threshold_uv
```

### Amplifier Saturation

```python
def detect_saturation(signal_uv: np.ndarray, clip_level_uv: float = 400.0) -> bool:
    return bool(np.any(np.abs(signal_uv) >= clip_level_uv))
```

---

## 4. Temporal Filters

### FIR Bandpass Filter

Zero-phase filtering using `scipy.signal.firwin` + `filtfilt`:

```python
from scipy.signal import firwin, filtfilt

def design_bandpass_fir(low_hz: float, high_hz: float, sample_rate: int,
                         num_taps: int | None = None) -> np.ndarray:
    if num_taps is None:
        # Rule of thumb: at least 3 cycles of the lowest frequency
        num_taps = int(3 * sample_rate / low_hz)
        num_taps = num_taps if num_taps % 2 == 1 else num_taps + 1  # odd
    nyquist = sample_rate / 2
    return firwin(num_taps, [low_hz / nyquist, high_hz / nyquist], pass_zero=False)

def apply_bandpass(signal: np.ndarray, h: np.ndarray) -> np.ndarray:
    # signal: [channels, samples]
    return filtfilt(h, [1.0], signal, axis=1)
```

**Note for real-time:** `filtfilt` is not causal. For online use, implement a causal IIR
filter (Butterworth) instead. Use `filtfilt` only for offline analysis.

Online alternative:
```python
from scipy.signal import iirfilter, sosfilt, sosfilt_zi

sos = iirfilter(4, [low_hz, high_hz], fs=sample_rate, btype='band', ftype='butter', output='sos')
zi = sosfilt_zi(sos)  # per-channel initial conditions (maintain across frames)
filtered, zi = sosfilt(sos, signal, zi=zi, axis=1)
```

### Autoregressive (AR) Spectral Estimation — Burg Method

BCI2000's primary spectral estimation method for sensorimotor rhythm control.

```python
def burg_ar(x: np.ndarray, order: int) -> tuple[np.ndarray, float]:
    """
    Burg's method for AR parameter estimation.
    Returns AR coefficients and noise variance.
    x: 1D signal of length N
    """
    N = len(x)
    ef = x.copy().astype(float)
    eb = x.copy().astype(float)
    a = np.zeros(order)
    P = np.dot(x, x) / N

    for m in range(order):
        num = -2 * np.dot(eb[m+1:], ef[m:N-1])  # Burg reflection coeff
        den = np.dot(ef[m:N-1], ef[m:N-1]) + np.dot(eb[m+1:], eb[m+1:])
        km = num / (den + 1e-10)
        ef_new = ef[m:N-1] + km * eb[m+1:]
        eb_new = eb[m+1:] + km * ef[m:N-1]
        ef[m:N-1] = ef_new
        eb[m+1:] = eb_new
        a_new = np.zeros(m + 1)
        a_new[:m] = a[:m] + km * a[:m][::-1]
        a_new[m] = km
        a = a_new
        P *= (1 - km**2)
    return a, P

def ar_psd(a: np.ndarray, sigma2: float, nfft: int, sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    """Power spectral density from AR coefficients."""
    import numpy as np
    freqs = np.fft.rfftfreq(nfft, d=1/sample_rate)
    z = np.exp(1j * 2 * np.pi * freqs / sample_rate)
    H = 1 / (1 + sum(a[k] * z**(-(k+1)) for k in range(len(a))))
    psd = sigma2 * np.abs(H)**2
    return freqs, psd
```

**Default AR order:** 16 (BCI2000 default for EEG at 160 Hz).

### P300 Epoch Averaging

```python
class P300Averager:
    def __init__(self, epoch_start_sec: float = -0.1, epoch_end_sec: float = 0.8,
                 sample_rate: int = 256):
        self.pre_samples = int(-epoch_start_sec * sample_rate)
        self.post_samples = int(epoch_end_sec * sample_rate)
        self.buffer: list[np.ndarray] = []

    def add_epoch(self, signal: np.ndarray, stimulus_onset_sample: int) -> None:
        start = stimulus_onset_sample - self.pre_samples
        end = stimulus_onset_sample + self.post_samples
        if start >= 0 and end <= signal.shape[1]:
            self.buffer.append(signal[:, start:end])

    def get_average(self) -> np.ndarray | None:
        if not self.buffer:
            return None
        return np.mean(self.buffer, axis=0)  # [channels, time_samples]
```

### Slow Wave (SCP) Filter

```python
def slow_wave_filter(signal: np.ndarray, window_samples: int,
                     baseline_samples: int) -> np.ndarray:
    # Moving average (low-pass)
    from scipy.ndimage import uniform_filter1d
    smoothed = uniform_filter1d(signal, size=window_samples, axis=1)
    # Baseline subtraction: subtract mean of baseline period
    baseline = smoothed[:, :baseline_samples].mean(axis=1, keepdims=True)
    return smoothed - baseline
```

---

## 5. Feature Extraction

### Band Power Computation

```python
def compute_band_powers(psd: np.ndarray, freqs: np.ndarray,
                         bands: dict[str, tuple[float, float]]) -> dict[str, np.ndarray]:
    """
    psd: [channels, freq_bins]
    freqs: [freq_bins]
    bands: {"alpha": (8, 12), "beta": (18, 26), ...}
    Returns: dict of band_name → [channels] power array
    """
    result = {}
    df = freqs[1] - freqs[0]  # frequency resolution
    for name, (low, high) in bands.items():
        mask = (freqs >= low) & (freqs <= high)
        result[name] = np.trapz(psd[:, mask], freqs[mask], axis=1)  # integrate PSD
    return result
```

### ERD/ERS Computation

```python
def compute_erd(current_power: np.ndarray, baseline_power: np.ndarray) -> np.ndarray:
    """
    ERD(%) = (A - R) / R × 100
    A = current band power, R = reference (baseline) band power
    Negative = ERD (desynchronization), Positive = ERS (synchronization)
    """
    return (current_power - baseline_power) / (baseline_power + 1e-10) * 100.0
```

---

## Processing Latency Budget

Total budget: <5 ms per frame at 16-channel EEG, 160 Hz, 10 samples/frame.

| Operator | Target | Notes |
|---|---|---|
| Calibrator | <0.1 ms | Simple linear transform |
| SpatialFilter (CAR) | <0.2 ms | One matrix operation |
| SpatialFilter (CSP) | <0.5 ms | 6-component matrix multiply |
| ArtifactRejector | <0.5 ms | Variance + amplitude checks |
| TemporalFilter (AR) | <2 ms | Burg AR order 16, 16 channels |
| FeatureExtractor | <1 ms | Band integration over PSD |
| Overhead (Python) | <0.7 ms | Function calls, dict assembly |
| **Total** | **<5 ms** | |

Use `time.perf_counter_ns()` for timing instrumentation. NumPy vectorization is mandatory —
no Python loops over channels or samples in hot paths.
