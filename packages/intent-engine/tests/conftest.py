"""
Shared test fixtures and synthetic data generators.

Motor imagery synthetic data:
  - Left imagery:  ERD in alpha/beta over C4; ERS over C3
    → features [alpha_C3=high, alpha_Cz=mid, alpha_C4=low, beta_C3=high, beta_Cz=mid, beta_C4=low]
  - Right imagery: ERD in alpha/beta over C3; ERS over C4
    → features [alpha_C3=low, alpha_Cz=mid, alpha_C4=high, beta_C3=low, beta_Cz=mid, beta_C4=high]

The class separation is set so that LDA achieves ≥ 70 % held-out accuracy.
"""

from __future__ import annotations

import numpy as np
import pytest

from intent_engine.classifiers.lda_classifier import LDAClassifier
from intent_engine.classifiers.p300_template_classifier import P300Detector


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

N_PER_CLASS = 80
NOISE_STD = 0.25
FEATURE_DIM = 6

LEFT_MEAN = np.array([1.6, 0.9, 0.4, 1.6, 0.9, 0.4], dtype=np.float64)
RIGHT_MEAN = np.array([0.4, 0.9, 1.6, 0.4, 0.9, 1.6], dtype=np.float64)


# ------------------------------------------------------------------
# Synthetic data generators
# ------------------------------------------------------------------

def make_mi_dataset(
    n_per_class: int = N_PER_CLASS,
    noise_std: float = NOISE_STD,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (X, y) for 2-class motor imagery (left=0, right=1)."""
    rng = np.random.RandomState(seed)
    X_left = rng.randn(n_per_class, FEATURE_DIM) * noise_std + LEFT_MEAN
    X_right = rng.randn(n_per_class, FEATURE_DIM) * noise_std + RIGHT_MEAN
    X = np.vstack([X_left, X_right])
    y = np.array([0] * n_per_class + [1] * n_per_class)
    return X, y


def make_p300_dataset(
    n_epochs: int = 100,
    time_samples: int = 128,
    snr_db: float = 10.0,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (X, y) for P300 detection at Pz.

    Target epochs contain a P300 bump at t ≈ 40 samples (300 ms at 128 Hz).
    SNR = signal_power / noise_power is set to snr_db.
    """
    rng = np.random.RandomState(seed)
    t = np.linspace(0, 1, time_samples)

    # Canonical P300 template: positive bump centred at ~300 ms
    template = np.exp(-((t - 0.3) ** 2) / (2 * 0.05**2))

    # Noise power → signal power from SNR
    noise_std = 1.0
    signal_std = noise_std * (10 ** (snr_db / 20.0))

    X = rng.randn(n_epochs, time_samples) * noise_std
    y = rng.randint(0, 2, size=n_epochs)  # 50/50 target vs. non-target

    # Add P300 template to target epochs
    for i, label in enumerate(y):
        if label == 1:
            X[i] += template * signal_std

    return X, y


def make_csp_features(
    n_per_class: int = 80,
    n_components: int = 6,
    noise_std: float = 0.2,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Synthetic CSP log-variance features for 2-class MI."""
    rng = np.random.RandomState(seed)
    left_mean = np.linspace(-2, 2, n_components)
    right_mean = left_mean[::-1]
    X_left = rng.randn(n_per_class, n_components) * noise_std + left_mean
    X_right = rng.randn(n_per_class, n_components) * noise_std + right_mean
    X = np.vstack([X_left, X_right])
    y = np.array([0] * n_per_class + [1] * n_per_class)
    return X, y


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def mi_dataset():
    return make_mi_dataset()


@pytest.fixture
def p300_dataset():
    return make_p300_dataset()


@pytest.fixture
def fitted_lda() -> LDAClassifier:
    """Pre-fitted LDAClassifier on synthetic MI data."""
    X, y = make_mi_dataset()
    clf = LDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    clf.fit(X, y)
    return clf


@pytest.fixture
def fitted_p300() -> P300Detector:
    """Pre-fitted P300Detector on synthetic P300 data."""
    X, y = make_p300_dataset()
    det = P300Detector(threshold=0.3)
    det.fit(X, y)
    return det


def make_feature_vector(
    label: str = "motor_imagery_left",
    seed: int = 0,
    artifact: bool = False,
) -> dict:
    """Build a minimal FeatureVector dict for the given motor imagery class."""
    rng = np.random.RandomState(seed)
    if label == "motor_imagery_left":
        mean = LEFT_MEAN
    else:
        mean = RIGHT_MEAN
    features = rng.randn(6) * NOISE_STD + mean

    alpha = list(features[:3])
    beta = list(features[3:])

    return {
        "vectorId": f"00000000-0000-0000-0000-{seed:012d}",
        "sourceFrameIndices": [seed * 16],
        "timestampNs": str(seed * 62_500_000),
        "deviceId": "test-device",
        "signalType": "EEG",
        "bandPowers": {
            "delta": [0.1, 0.1, 0.1],
            "theta": [0.2, 0.2, 0.2],
            "alpha": alpha,
            "beta": beta,
            "gamma": [0.05, 0.05, 0.05],
            "high_gamma": [0.01, 0.01, 0.01],
        },
        "spatialFeatures": [],
        "erd": {
            "alpha": [0.0, 0.0, 0.0],
            "beta": [0.0, 0.0, 0.0],
        },
        "evokedResponse": None,
        "artifactFlag": artifact,
        "processingLatencyMs": 1.5,
        "channelLabels": ["C3", "Cz", "C4"],
    }
