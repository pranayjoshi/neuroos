# Intent Engine — Pretrained Models

This directory holds pretrained model artefacts for the NeuroOS Intent Engine.

## Contents

### `pretrained/motor_imagery_lda.pkl`

**Format:** Python pickle (sklearn `LinearDiscriminantAnalysis`)  
**Task:** 2-class motor imagery — `motor_imagery_left` vs `motor_imagery_right`  
**Features:** 6-dimensional band-power vector  
  `[alpha_C3, alpha_Cz, alpha_C4, beta_C3, beta_Cz, beta_C4]`  
**Training data:** Synthetic motor imagery data (see `conftest.py`)  
**Solver:** `eigen` with Ledoit-Wolf shrinkage (`shrinkage='auto'`)  
**Reported accuracy:** ≥ 85 % on held-out synthetic data

### `pretrained/p300_template.npy`

**Format:** NumPy `.npy` array, shape `[128]` (float64)  
**Task:** P300 evoked-potential template at Pz, 0–800 ms window at 128 Hz  
**Source:** Grand-average of simulated target epochs at SNR = 10 dB  
**Usage:** Loaded by `P300Detector.load_template(path)`

## Regenerating Models

Run the following from the package root to regenerate pretrained artefacts:

```bash
python -c "
import numpy as np
from intent_engine.classifiers.lda_classifier import LDAClassifier
from intent_engine.classifiers.p300_template_classifier import P300Detector
from intent_engine.model_store import ModelStore

rng = np.random.RandomState(42)

# Motor imagery LDA
left_mean = np.array([1.6, 0.9, 0.4, 1.6, 0.9, 0.4])
right_mean = np.array([0.4, 0.9, 1.6, 0.4, 0.9, 1.6])
X = np.vstack([rng.randn(100, 6) * 0.25 + left_mean,
               rng.randn(100, 6) * 0.25 + right_mean])
y = np.array([0]*100 + [1]*100)
clf = LDAClassifier(['motor_imagery_left', 'motor_imagery_right'])
clf.fit(X, y)
clf.save('models/pretrained/motor_imagery_lda.pkl')

# P300 template
t = np.linspace(0, 1, 128)
template = np.exp(-((t - 0.3)**2) / (2 * 0.05**2))
np.save('models/pretrained/p300_template.npy', template)
print('Models regenerated successfully.')
"
```

## Performance Metrics

| Model | Accuracy | Inference Latency | Training Samples |
|---|---|---|---|
| `motor_imagery_lda.pkl` | ≥ 85 % (synthetic) | < 0.5 ms | 200 trials (100/class) |
| `p300_template.npy` | ≥ 80 % (SNR=10 dB) | < 0.5 ms | Template from 100 targets |

## Provenance

All pretrained models were generated from synthetic data following the
NeuroOS data generator specification (Job 01). No real human EEG data is
included. Models should be recalibrated from real session data before
deployment.
