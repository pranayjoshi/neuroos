# Job 03 — Intent Engine

**Agent Role:** Intent Engine  
**Language:** Python 3.11  
**Depends on:** Job 00 (schemas), Job 02 (produces FeatureVector this engine classifies)  
**Consumed by:** Job 04 (Platform Core routes IntentEvents to SDK), Job 06 (CI/CD tests)

---

## Purpose

The Intent Engine is the AI brain of NeuroOS. It takes a stream of `FeatureVector` objects from the DSP pipeline and emits `IntentEvent` objects — clean, typed user intentions that developer apps can act on.

This is hardware-agnostic by design: the engine never sees raw signals, only features. Swapping a different DSP pipeline or different hardware does not require changes here.

From BCI2000's model: this corresponds to the translation algorithm stage — *"a translation algorithm translates signal features into control signals."*

---

## Deliverables

All code lives in `packages/intent-engine/` in the NeuroOS monorepo.

### Source files (`src/`)

| File | Class | Responsibility |
|---|---|---|
| `classifiers/base_classifier.py` | `IntentClassifier` | Abstract base for all classifiers |
| `classifiers/lda_classifier.py` | `LDAClassifier` | Fast linear discriminant analysis baseline |
| `classifiers/csp_lda_classifier.py` | `CSPLDAClassifier` | CSP spatial filter + LDA (motor imagery) |
| `classifiers/p300_detector.py` | `P300Detector` | Template matching for P300 speller |
| `classifiers/neural_classifier.py` | `NeuralClassifier` | CNN/LSTM via ONNX runtime |
| `decoders/motor_imagery_decoder.py` | `MotorImageryDecoder` | Left/right/rest 3-class pipeline |
| `decoders/p300_speller_decoder.py` | `P300SpellerDecoder` | 6×6 matrix speller orchestration |
| `postprocessing/intent_normalizer.py` | `IntentNormalizer` | Z-score + adaptive baseline correction |
| `training/online_trainer.py` | `OnlineTrainer` | Streaming LDA adaptation from feedback |
| `engine/intent_engine.py` | `IntentEngine` | Orchestrator: inference loop, emit IntentEvents |
| `engine/engine_config.py` | `EngineConfig` | Dataclass for engine configuration |

### Tests (`tests/`)

- `test_lda_classifier.py`
- `test_csp_lda_classifier.py`
- `test_p300_detector.py`
- `test_intent_normalizer.py`
- `test_online_trainer.py`
- `test_intent_engine.py` — end-to-end: FeatureVector stream → IntentEvent stream
- `test_performance.py` — inference latency budget (<3 ms per vector)

### Models (`models/`)

- `pretrained/motor_imagery_lda.pkl` — pre-trained LDA coefficients for 2-class MI
- `pretrained/p300_template.npy` — canonical P300 waveform template
- `README.md` — model provenance, training data description, performance metrics

---

## Abstract Classifier Interface

```python
from abc import ABC, abstractmethod
import numpy as np
from dataclasses import dataclass

@dataclass
class ClassificationResult:
    label: str                          # winning IntentLabel
    confidence: float                   # posterior of winning class
    posteriors: dict[str, float]        # full posterior distribution
    feature_importance: dict[str, list[float]]  # band → per-channel importance

class IntentClassifier(ABC):
    """
    Abstract base for all NeuroOS intent classifiers.
    Classifiers are stateless at inference time (all state is in fit() output).
    """

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Train or fine-tune the classifier.
        X: [n_trials, n_features]  (flattened band-power feature vector)
        y: [n_trials] integer class labels
        """

    @abstractmethod
    def predict(self, features: np.ndarray) -> ClassificationResult:
        """
        Classify one feature vector.
        features: [n_features] (flattened from FeatureVector)
        Must execute in < 3 ms.
        """

    @abstractmethod
    def get_class_labels(self) -> list[str]:
        """Returns the IntentLabel strings for each class index."""

    def save(self, path: str) -> None: ...
    def load(self, path: str) -> None: ...
```

---

## LDA Classifier

```python
class LDAClassifier(IntentClassifier):
    """
    Linear Discriminant Analysis — the fastest, most interpretable baseline.

    From BCI2000: "The first signal operator is a classifier that performs a
    linear transformation (matrix multiplication of a classification matrix
    with the output of the temporal filtering module)."

    Implementation: sklearn.discriminant_analysis.LinearDiscriminantAnalysis
    with shrinkage='auto' (Ledoit-Wolf) for small training set robustness.

    Feature vector construction from FeatureVector:
    - Alpha and beta band powers at C3, Cz, C4 (6 features for 2-class MI)
    - Optionally include all band powers at all channels (full feature set)
    """
```

**Flattened feature vector layout:**
```
features = [
    alpha_power_C3, alpha_power_Cz, alpha_power_C4,
    beta_power_C3,  beta_power_Cz,  beta_power_C4,
    # optionally: all bands × all channels
]
```

---

## CSP-LDA Classifier

```python
class CSPLDAClassifier(IntentClassifier):
    """
    CSP spatial filtering + log-variance features + LDA classification.
    Standard pipeline for 2-class motor imagery (left vs. right hand).

    Pipeline:
    1. Apply pre-computed CSP filters W (from DSP SpatialFilter)
    2. Compute log-variance of each CSP component: log(var(W^T x))
    3. Classify log-variance features with LDA
    """
```

---

## P300 Detector

```python
class P300Detector(IntentClassifier):
    """
    Template-matching classifier for P300 evoked potential detection.

    Method:
    1. Pearson correlation between incoming epoch and stored P300 template
    2. Template is the grand-average P300 waveform from calibration trials
    3. Classification: target if correlation > threshold, else non-target

    Template shape: [1, time_samples] (Pz channel, 0–800 ms window)

    From BCI2000: "The evoked responses are classified (by the associated signal
    processing module), and the character that the system identifies as the
    desired character is shown on the screen."
    """

    def fit(self, epochs: np.ndarray, labels: np.ndarray) -> None:
        # epochs: [n_epochs, channels, time_samples]
        # labels: [n_epochs] binary (1=target, 0=non-target)
        # Compute mean P300 template from target epochs at Pz
        ...

    def predict(self, features: np.ndarray) -> ClassificationResult:
        # features: evoked response from FeatureVector.evokedResponse
        ...
```

---

## Intent Normalizer

```python
class IntentNormalizer:
    """
    Post-processes classifier output to produce stable, calibrated confidence scores.

    From BCI2000: "The second signal operator in the translation algorithm is a
    normalizer that performs a linear transformation on each output channel in
    order to create signals that have zero mean and a specific value range."

    Also implements adaptive baseline correction: updates running statistics
    to compensate for spontaneous drifts in signal distribution.

    Steps:
    1. Z-score: (raw_score - running_mean) / running_std
    2. Sigmoid: 1 / (1 + exp(-z))  → [0, 1] confidence
    3. Adaptive update: running_mean += α * (raw_score - running_mean)  (EMA)
    """

    def __init__(self, alpha: float = 0.01):  # EMA decay, small = slow adaptation
        ...

    def normalize(self, raw_posteriors: dict[str, float]) -> dict[str, float]:
        """Returns calibrated posteriors summing to 1.0."""
```

---

## Online Trainer

```python
class OnlineTrainer:
    """
    Streaming adaptation: updates classifier parameters from feedback events.

    When the app sends a feedback label (user confirmed or corrected an intent),
    the trainer incorporates that labeled sample into an incremental LDA update.

    Method: Recursive LDA update (updating class means and covariances without
    storing full history). Bounded by max_adaptation_samples to prevent drift.
    """

    def __init__(self, base_classifier: LDAClassifier,
                 learning_rate: float = 0.01,
                 max_adaptation_samples: int = 500): ...

    def on_feedback(self, features: np.ndarray, true_label: str) -> None:
        """Update classifier with one confirmed labeled sample."""
```

---

## Intent Engine Orchestrator

```python
class IntentEngine:
    """
    Main orchestrator. Runs an async inference loop at configured Hz rate.

    Pipeline:
    1. Receive FeatureVector from DSP pipeline (via asyncio queue)
    2. Build flattened feature array from FeatureVector
    3. Run active classifier → ClassificationResult
    4. Apply IntentNormalizer → calibrated posteriors
    5. Apply confidence threshold (suppress below-threshold events)
    6. Emit IntentEvent dict (matches JSON schema)

    Inference rate: 16 Hz default (configurable 1–50 Hz)
    Inference budget: <3 ms per vector (excluding I/O)
    End-to-end latency target: <15 ms from sample acquisition
    """

    async def run(self, feature_stream: AsyncIterator[dict]) -> AsyncIterator[dict]:
        """
        Async generator: consumes FeatureVector stream, yields IntentEvent dicts.
        """
```

---

## Motor Imagery Decoder (High-Level)

```python
class MotorImageryDecoder:
    """
    Complete pipeline for 3-class motor imagery: left / right / rest.

    Wraps CSPLDAClassifier with domain-specific feature extraction
    and confidence calibration optimized for motor imagery paradigm.

    Calibration protocol:
    1. Collect ~20 trials per class (rest / left / right) during calibration session
    2. Fit CSP filters W from left vs. right epochs
    3. Fit LDA from CSP log-variance features
    4. Fit IntentNormalizer from calibration trial scores
    """
```

---

## Dependencies

```
numpy>=1.26
scipy>=1.12
scikit-learn>=1.4      # LDA, CSP utilities
onnxruntime>=1.17      # Neural classifier inference
torch>=2.2             # Model training (optional; only for neural classifier training)
pytest>=7.4
pytest-benchmark
```

---

## Acceptance Criteria

- [ ] `pytest tests/ -v` passes with zero failures
- [ ] `LDAClassifier` achieves ≥70% accuracy on held-out motor imagery features generated from Job 01 simulator (`motor_imagery_left` vs. `motor_imagery_right` scenarios)
- [ ] `P300Detector` achieves ≥80% accuracy on simulated P300 epochs with SNR=10 dB
- [ ] `test_performance.py`: mean inference latency <3 ms for LDA on 6-feature vector (measured over 1000 calls)
- [ ] `IntentNormalizer` output confidence values lie in [0, 1] and sum to 1.0 across all labels
- [ ] `IntentEngine` end-to-end test: processes 100 `motor_imagery_left` FeatureVectors, emits ≥65% `motor_imagery_left` IntentEvents with confidence ≥0.6
- [ ] All output dicts pass JSON Schema validation against `../00_shared_contracts/json-schema/IntentEvent.schema.json`
- [ ] `OnlineTrainer.on_feedback()` call with correct labels for 50 trials improves accuracy by ≥5%

---

## Must NOT Do

- Apply DSP filtering or spatial filtering (Job 02)
- Synthesize signal data (Job 01)
- Open network sockets, serve HTTP, or handle SDK requests (Job 04)
- Modify `FeatureVector` structure — consume it as-is
- Import from any job folder except `00_shared_contracts`
