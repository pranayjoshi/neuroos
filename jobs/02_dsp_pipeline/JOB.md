# Job 02 — Bio-Signal DSP Pipeline

**Agent Role:** Bio-Signal DSP Engineer  
**Language:** Python 3.11  
**Depends on:** Job 00 (schemas), Job 01 (produces the RawSignalFrame stream this pipeline consumes)  
**Consumed by:** Job 03 (Intent Engine), Job 06 (CI/CD integration tests)

---

## Purpose

Convert raw, noisy bio-signal frames into clean, calibrated, hardware-agnostic feature vectors.

This is the core of BCI2000's signal processing module: a cascade of independent, interchangeable signal operators. Each operator transforms an input signal to an output signal. Operators can be swapped without modifying others — this is the key design principle that makes NeuroOS hardware-agnostic.

From BCI2000 (Schalk et al., 2004): *"The decomposition of signal processing into a sequence of signal operators provides a high level of interchangeability and independence."*

---

## Deliverables

All code lives in `packages/dsp-pipeline/` in the NeuroOS monorepo.

### Source files (`src/`)

| File | Class | Responsibility |
|---|---|---|
| `operators/calibrator.py` | `Calibrator` | A/D units → μV, baseline correction |
| `operators/spatial_filter.py` | `SpatialFilter` | CAR, Laplacian, CSP |
| `operators/artifact_rejector.py` | `ArtifactRejector` | EMG/ocular/saturation detection |
| `operators/temporal_filter.py` | `TemporalFilter` | Bandpass FIR, AR spectral estimation |
| `operators/feature_extractor.py` | `FeatureExtractor` | Band powers, ERD/ERS, evoked response |
| `pipeline/dsp_pipeline.py` | `DSPPipeline` | Orchestrator: chains all operators |
| `pipeline/pipeline_config.py` | `DSPConfig` | Dataclass for pipeline configuration |
| `operators/base_operator.py` | `SignalOperator` | Abstract base with timing instrumentation |

### Tests (`tests/`)

- `test_calibrator.py`
- `test_spatial_filter.py`
- `test_artifact_rejector.py`
- `test_temporal_filter.py`
- `test_feature_extractor.py`
- `test_dsp_pipeline.py` — end-to-end: RawSignalFrame → FeatureVector
- `test_performance.py` — processing latency budget (<5 ms per frame)

---

## Signal Operator Architecture

Every operator inherits from `SignalOperator` and follows this protocol:

```python
from abc import ABC, abstractmethod
import numpy as np

class SignalOperator(ABC):
    """
    Abstract base for all DSP operators.
    An operator transforms an input numpy array into an output numpy array.
    Input/output shape conventions are documented per operator.
    """

    @abstractmethod
    def fit(self, calibration_data: np.ndarray) -> None:
        """
        Fit operator parameters to a calibration dataset.
        Shape: [num_channels, num_samples].
        Called once at session start. Some operators (e.g. Calibrator) require this.
        Others (e.g. BandpassFIR) are parameterized by config only.
        """

    @abstractmethod
    def process(self, signal: np.ndarray) -> np.ndarray:
        """
        Transform one frame of signal data.
        Input shape: [num_channels, samples_per_frame]
        Output shape: operator-specific (documented per class).
        Must execute in < operator_budget_ms milliseconds.
        """

    @property
    @abstractmethod
    def operator_name(self) -> str: ...
```

---

## Calibrator

```python
class Calibrator(SignalOperator):
    """
    Stage 1: Convert raw A/D integer values to microvolts.

    From BCI2000: "The first signal operator is a calibration routine that
    performs a linear transformation of the input matrix so that the input
    signal (in A/D units) is converted to an output signal in units of microvolts."

    Also performs per-channel DC baseline subtraction.
    """

    def fit(self, calibration_data: np.ndarray) -> None:
        # Estimate per-channel gain (μV/unit) and offset from resting data
        ...

    def process(self, signal: np.ndarray) -> np.ndarray:
        # signal_uv = gain * signal + offset
        # signal_uv -= baseline_mean  (DC removal)
        ...
```

**Config fields:** `gain_uv_per_unit: float`, `offset_uv: float`, `baseline_window_sec: float`

---

## SpatialFilter

```python
class SpatialFilter(SignalOperator):
    """
    Stage 2: Reduce volume conduction and improve spatial resolution.

    Implements three methods (selected via config):
    - CAR (Common Average Reference): subtract mean across all channels
    - Laplacian: subtract weighted mean of surrounding channels
    - CSP (Common Spatial Patterns): supervised, maximizes variance ratio
      between two classes. Requires fit() with labeled calibration data.

    From BCI2000: "The second signal operator is a spatial filter that performs
    a linear transformation (matrix multiplication) so that each output channel
    is a linear combination of all input channels."
    """

    def __init__(self, method: Literal["car", "laplacian", "csp"], n_components: int = 6): ...
```

**CSP implementation:** Use generalized eigenvalue decomposition.
`W = eig(Σ1, Σ1 + Σ2)` where Σ1, Σ2 are class covariance matrices.

---

## ArtifactRejector

```python
class ArtifactRejector(SignalOperator):
    """
    Detect and flag frames contaminated by artifacts before feature extraction.

    Detection methods (all run in parallel, any positive → artifact_flag=True):
    - EMG detection: high-frequency power (>40 Hz) exceeds z-score threshold
    - Ocular detection: large amplitude at Fp1/Fp2 (>100 μV)
    - Saturation detection: any channel at amplifier clipping level (±500 μV typical)
    - Motion detection: broadband amplitude spike across all channels simultaneously

    Does NOT remove artifact — sets artifact_flag and artifact_type on the frame.
    Downstream operators still process the frame; Intent Engine weights it lower.
    """

    def process(self, signal: np.ndarray) -> tuple[np.ndarray, bool, str | None]:
        # Returns: (signal_unchanged, artifact_flag, artifact_type)
        ...
```

---

## TemporalFilter

```python
class TemporalFilter(SignalOperator):
    """
    Stage 3: Extract time-domain or frequency-domain features.

    Implements four methods (selected via config):

    1. bandpass_fir: Zero-phase FIR bandpass filter (scipy.signal.firwin2)
       Config: low_hz, high_hz, num_taps (odd, ≥3× sample_rate/low_hz)

    2. autoregressive: AR spectral estimation (Burg method)
       Config: ar_order (default 16), spectral resolution
       Returns power spectral density estimate per channel.
       From BCI2000: "Autoregressive spectral estimation" for SMR cursor control.

    3. p300_average: Epoch averaging for P300 detection.
       Config: epoch_start_sec (-0.1), epoch_end_sec (0.8), num_averages (15)
       Accumulates epochs triggered by event markers, returns running average.

    4. slow_wave: Moving average low-pass for SCP.
       Config: window_sec (0.5), baseline_sec (2.0)
       From BCI2000: "The low-pass slow wave filter calculates a moving average
       of the past 500 ms. Subsequently, a baseline correction procedure subtracts
       the average signal amplitude prior to output."
    """
```

---

## FeatureExtractor

```python
class FeatureExtractor(SignalOperator):
    """
    Stage 4: Assemble the FeatureVector from filtered signals.

    Computes:
    - Band powers: power in each canonical band (delta/theta/alpha/beta/gamma)
      from the AR spectral estimate or FFT of the filtered signal
    - ERD/ERS: (current_power - baseline_power) / baseline_power × 100%
      Baseline estimated from first N seconds of session (configurable)
    - Evoked response: averaged epoch (from p300_average operator)
    - Spatial features: output of the SpatialFilter stage

    Output: FeatureVector dict matching JSON schema in 00_shared_contracts.
    """
```

---

## DSPPipeline

```python
class DSPPipeline:
    """
    Orchestrates the full signal processing cascade.

    Pipeline: RawSignalFrame → Calibrator → SpatialFilter →
              ArtifactRejector → TemporalFilter → FeatureExtractor → FeatureVector

    Enforces per-frame processing budget: raises PipelineLatencyError if
    total processing time exceeds 5 ms.

    Usage:
        pipeline = DSPPipeline(config)
        pipeline.calibrate(calibration_frames)  # fit all operators
        async for frame in device.frame_stream():
            feature_vector = pipeline.process(frame)
            yield feature_vector
    """

    def calibrate(self, frames: list[dict]) -> None:
        """Fit all operators that require calibration data (Calibrator, CSP)."""

    def process(self, frame: dict) -> dict:
        """
        Process one RawSignalFrame dict.
        Returns a FeatureVector dict matching the JSON schema.
        Thread-safe.
        """
```

---

## Performance Requirements

- **Per-frame latency:** <5 ms (enforced by `DSPPipeline`)
- **Frame rate:** must keep up with 16 Hz update rate (62.5 ms per frame)
- **Memory:** no unbounded accumulation — use ring buffers for windowing
- **Thread safety:** `DSPPipeline.process()` must be safe to call from a single thread

---

## Dependencies

```
numpy>=1.26
scipy>=1.12
scikit-learn>=1.4   # CSP, LDA utilities
mne>=1.6            # EEG preprocessing reference implementations
pytest>=7.4
pytest-benchmark    # for test_performance.py
```

---

## Acceptance Criteria

- [ ] `pytest tests/ -v` passes with zero failures
- [ ] `test_performance.py`: mean processing latency <5 ms for 16-channel EEG at 160 Hz (measured over 1000 frames)
- [ ] `SpatialFilter(method="car")` reduces cross-channel correlation (mean pairwise ρ decreases by ≥10%)
- [ ] `ArtifactRejector` detects injected EMG bursts with ≥90% sensitivity and ≤10% false positive rate on clean data
- [ ] `TemporalFilter(method="autoregressive")` produces alpha band power estimates that correlate ≥0.9 with scipy Welch's method on the same data
- [ ] `DSPPipeline` end-to-end test: processes `motor_imagery_left` scenario frames and produces `alpha` band ERD at C4 ≤ −15% vs. `rest`
- [ ] All output dicts pass JSON Schema validation against `../00_shared_contracts/json-schema/FeatureVector.schema.json`

---

## Must NOT Do

- Load or run any ML model (classification is Job 03)
- Open network connections or emit HTTP/WebSocket traffic (Job 04)
- Synthesize or generate signal data (Job 01)
- Import from any job folder except `00_shared_contracts`
