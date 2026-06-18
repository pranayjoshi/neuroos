"""
Tests for P300Detector.

Acceptance criteria:
  - ≥ 80 % accuracy on simulated P300 epochs with SNR = 10 dB.
  - posteriors sum to 1.0.
  - Template save / load round-trip.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.model_selection import train_test_split

from intent_engine.classifiers.p300_template_classifier import P300Detector

from .conftest import make_p300_dataset


def test_fit_predict_basic(fitted_p300):
    X, y = make_p300_dataset(seed=99)
    result = fitted_p300.predict(X[0])
    assert result.label in ["p300_target", "p300_non_target"]
    assert 0.0 <= result.confidence <= 1.0


def test_posteriors_sum_to_one(fitted_p300):
    X, y = make_p300_dataset(seed=10)
    for x in X[:20]:
        result = fitted_p300.predict(x)
        total = sum(result.posteriors.values())
        assert abs(total - 1.0) < 1e-9, f"Posteriors do not sum to 1: {total}"


def test_accuracy_geq_80_percent_snr10():
    """P300Detector must achieve ≥ 80 % at SNR = 10 dB."""
    X, y = make_p300_dataset(n_epochs=200, time_samples=128, snr_db=10.0, seed=42)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.4, random_state=0, stratify=y
    )
    det = P300Detector(threshold=0.3)
    det.fit(X_train, y_train)

    label_map = {"p300_target": 1, "p300_non_target": 0}
    correct = sum(label_map[det.predict(x).label] == yt for x, yt in zip(X_test, y_test))
    acc = correct / len(y_test)
    assert acc >= 0.80, f"P300 accuracy {acc:.2%} < 80 %"


def test_no_target_epochs_raises():
    X = np.random.randn(10, 64)
    y = np.zeros(10, dtype=int)
    det = P300Detector()
    with pytest.raises(ValueError):
        det.fit(X, y)


def test_unfitted_raises():
    det = P300Detector()
    with pytest.raises(RuntimeError):
        det.predict(np.zeros(64))


def test_template_save_load(tmp_path, fitted_p300):
    path = str(tmp_path / "p300_template.npy")
    fitted_p300.save_template(path)

    det2 = P300Detector(threshold=fitted_p300.threshold)
    det2.load_template(path)

    X, _ = make_p300_dataset(seed=7)
    for x in X[:10]:
        r1 = fitted_p300.predict(x)
        r2 = det2.predict(x)
        assert r1.label == r2.label


def test_3d_epoch_input(fitted_p300):
    """fit() should accept [n_epochs, 1, time_samples]."""
    X, y = make_p300_dataset(n_epochs=40, seed=5)
    X_3d = X[:, np.newaxis, :]  # [40, 1, 128]
    det = P300Detector()
    det.fit(X_3d, y)
    assert det.is_fitted
