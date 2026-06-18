# Classification Methods Reference — Intent Engine Context

Detailed algorithms and worked examples for every classifier in the NeuroOS Intent Engine.
Values and approaches drawn from BCI2000 paper and standard EEG-BCI literature.

---

## 1. Linear Discriminant Analysis (LDA)

### When to Use
- Motor imagery 2-class (left vs. right)
- Any binary or multi-class intent with linear decision boundaries
- Real-time operation with <1 ms inference requirement
- Small training datasets (≥20 trials per class)

### Algorithm

Given training data `X ∈ R^(N×d)` with labels `y ∈ {0, 1}`:

```
1. Compute class means: μ_k = mean(X[y==k])
2. Compute within-class scatter: S_W = Σ_k Σ_{i: y_i=k} (x_i - μ_k)(x_i - μ_k)^T
3. Compute between-class scatter: S_B = Σ_k n_k (μ_k - μ)(μ_k - μ)^T
4. Solve generalized eigenvalue problem: S_B w = λ S_W w
5. Projection: z = w^T x  (scalar for 2-class)
6. Posterior: P(class=1 | x) = σ(z - threshold)
```

For multi-class: use softmax over K discriminant functions.

**Shrinkage regularization (Ledoit-Wolf):**
```python
from sklearn.covariance import ledoit_wolf

def compute_regularized_sw(X_centered: np.ndarray) -> np.ndarray:
    cov, alpha = ledoit_wolf(X_centered)
    return cov
```

Prevents singularity with small sample sizes (common in BCI: ~20 trials/class).

### Feature Vector for Motor Imagery LDA

```
Minimal (6 features): alpha_C3, alpha_Cz, alpha_C4, beta_C3, beta_Cz, beta_C4

Extended (18 features): above + same for theta and gamma bands

Full (64 features for 16-ch cap): alpha × 16 channels + beta × 16 channels
```

Typical accuracy with minimal features: 70–85% in well-trained subjects.

---

## 2. Common Spatial Patterns + LDA (CSP-LDA)

### When to Use
- Motor imagery (specifically designed for this paradigm)
- Higher accuracy than plain LDA when >10 trials per class are available

### Feature Extraction Pipeline

```python
# After fitting CSP filters W ∈ R^(channels × n_components):
def extract_csp_features(epoch: np.ndarray, W: np.ndarray) -> np.ndarray:
    """
    epoch: [channels, time_samples] — one trial window (typically 2–4 s)
    Returns: [n_components] log-variance features
    """
    projected = W.T @ epoch  # [n_components, time_samples]
    variances = np.var(projected, axis=1)  # [n_components]
    return np.log(variances / variances.sum())  # log-normalized variance
```

These log-variance features are then fed to LDA.

**Why log?** The log transform makes variance approximately Gaussian distributed,
satisfying LDA's normality assumption.

### Accuracy Benchmark

From literature and BCI competition data:
- 2-class motor imagery (left vs. right): 75–92% correct with CSP-LDA
- Typical information transfer rate: 20–35 bits/min

---

## 3. P300 Template Matching

### When to Use
- P300 speller paradigm (oddball detection)
- Evoked potential detection in any stimulus-response paradigm

### Algorithm

```python
def match_p300_template(epoch: np.ndarray, template: np.ndarray,
                         threshold: float = 0.4) -> tuple[str, float]:
    """
    epoch: [1, time_samples] — Pz channel, 0–800 ms window
    template: [1, time_samples] — grand-average P300 from calibration
    Returns: (label, confidence)
    """
    from scipy.stats import pearsonr
    r, _ = pearsonr(epoch.ravel(), template.ravel())
    confidence = (r + 1) / 2  # map [-1, 1] → [0, 1]
    label = "p300_target" if r > threshold else "p300_non_target"
    return label, confidence
```

**P300 Speller Logic (Donchin paradigm, implemented in BCI2000):**

```
6×6 character matrix: rows and columns flash randomly, 5.7 Hz rate.
For each row/column flash:
  - Collect EEG epoch (−100 to +800 ms)
  - Detect P300 vs. non-target
After all rows and columns flash (15× averages per row/column):
  - Find row and column with highest P300 score
  - Selected character = intersection
```

Expected accuracy with 15 averages: 90–99% (from BCI2000 Fig. 4C).
Information transfer rate: 20–25 bits/min.

---

## 4. Neural Classifier (CNN/LSTM via ONNX)

### Architecture

**EEGNet** (Lawhern et al., 2018) — compact CNN designed for EEG classification:

```
Input: [1, channels, time_samples]  e.g. [1, 16, 128]

Layer 1: Temporal convolution
  Conv2D(1→8, kernel=(1, 64), padding='same')  # temporal filter
  BatchNorm → ELU

Layer 2: Depthwise spatial convolution
  DepthwiseConv2D(8→16, kernel=(channels, 1))  # spatial filter
  BatchNorm → ELU → AvgPool2D(1,4) → Dropout(0.5)

Layer 3: Separable convolution
  SeparableConv2D(16→16, kernel=(1, 16), padding='same')
  BatchNorm → ELU → AvgPool2D(1,8) → Dropout(0.5)

Flatten → Dense(n_classes) → Softmax
```

Total parameters: ~2,000 (extremely lightweight, <0.1 ms inference).

### ONNX Export and Inference

```python
import onnxruntime as ort

class NeuralClassifier:
    def __init__(self, model_path: str):
        self.session = ort.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider']
        )

    def predict(self, features: np.ndarray) -> ClassificationResult:
        # features: raw epoch [channels, time_samples]
        x = features[np.newaxis, np.newaxis].astype(np.float32)  # [1,1,ch,t]
        logits = self.session.run(None, {'input': x})[0][0]  # [n_classes]
        posteriors = softmax(logits)
        label_idx = posteriors.argmax()
        return ClassificationResult(
            label=self.class_labels[label_idx],
            confidence=float(posteriors[label_idx]),
            posteriors=dict(zip(self.class_labels, posteriors.tolist())),
            feature_importance={},  # TODO: Grad-CAM for interpretability
        )
```

---

## 5. Ensemble Classifier

Combines LDA and neural classifier by averaging their posterior distributions:

```python
def ensemble_predict(lda_result: ClassificationResult,
                     neural_result: ClassificationResult,
                     lda_weight: float = 0.5) -> ClassificationResult:
    all_labels = set(lda_result.posteriors) | set(neural_result.posteriors)
    combined = {}
    for label in all_labels:
        p_lda = lda_result.posteriors.get(label, 0.0)
        p_nn  = neural_result.posteriors.get(label, 0.0)
        combined[label] = lda_weight * p_lda + (1 - lda_weight) * p_nn
    # Normalize
    total = sum(combined.values())
    combined = {k: v / total for k, v in combined.items()}
    best_label = max(combined, key=combined.__getitem__)
    return ClassificationResult(
        label=best_label,
        confidence=combined[best_label],
        posteriors=combined,
        feature_importance={},
    )
```

---

## 6. Online Adaptation (Recursive LDA Update)

### Why Needed

EEG signals drift over time (fatigue, impedance changes, attention). A fixed classifier
trained at session start degrades. Online adaptation corrects for this.

From BCI2000: *"An additional statistics component can be enabled to update in real-time
certain parameters of the signal processing components such as the slope and intercept
of the linear equation the normalizer applies to each output channel so as to compensate
for spontaneous or adaptive changes in the distribution of the control signal values."*

### Recursive Update Rule

```python
class RecursiveLDA:
    """Incremental LDA update without storing all training samples."""

    def update(self, x: np.ndarray, label: int) -> None:
        """Add one labeled sample with exponential forgetting."""
        n = self.class_counts[label]
        # Update class mean with EMA
        self.class_means[label] += (x - self.class_means[label]) / (n + 1)
        self.class_counts[label] += 1
        # Update within-class covariance incrementally
        delta = x - self.class_means[label]
        self.S_W += np.outer(delta, delta) * self.forgetting_factor
        self.S_W *= self.forgetting_factor
        # Recompute LDA weights
        self._refit()
```

**Forgetting factor λ ∈ [0.99, 0.9999]:** higher = more stable, lower = faster adaptation.

---

## Performance Targets Summary

| Classifier | Inference Latency | Typical Accuracy | Training Data |
|---|---|---|---|
| LDA | <0.5 ms | 70–85% (MI) | ≥20 trials/class |
| CSP-LDA | <1 ms | 75–92% (MI) | ≥20 trials/class |
| P300 Template | <0.5 ms | 90–99% (P300) | ≥10 target epochs |
| Neural (ONNX) | <2 ms | 75–90% (MI) | ≥100 trials/class |
| Ensemble | <3 ms | 78–93% (MI) | Both above |

End-to-end latency budget from BCI2000 benchmark: **<15 ms** total.
Intent engine contribution (inference only): **<3 ms**.
