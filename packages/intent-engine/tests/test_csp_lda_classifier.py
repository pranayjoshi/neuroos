"""
Tests for CSPLDAClassifier.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.model_selection import train_test_split

from intent_engine.classifiers.csp_lda_classifier import CSPLDAClassifier

from .conftest import make_csp_features, make_mi_dataset


def test_fit_predict_csp_features():
    """Fit on pre-extracted CSP log-variance features."""
    X, y = make_csp_features(n_per_class=60, seed=0)
    clf = CSPLDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    clf.fit(X, y)
    result = clf.predict(X[0])
    assert result.label in ["motor_imagery_left", "motor_imagery_right"]
    assert 0.0 <= result.confidence <= 1.0


def test_posteriors_sum_to_one():
    X, y = make_csp_features(seed=1)
    clf = CSPLDAClassifier()
    clf.fit(X, y)
    for x in X[:20]:
        result = clf.predict(x)
        total = sum(result.posteriors.values())
        assert abs(total - 1.0) < 1e-6


def test_accuracy_geq_70_percent():
    X, y = make_csp_features(n_per_class=100, noise_std=0.2, seed=9)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    clf = CSPLDAClassifier()
    clf.fit(X_train, y_train)

    label_map = {"motor_imagery_left": 0, "motor_imagery_right": 1}
    correct = sum(label_map[clf.predict(x).label] == yt for x, yt in zip(X_test, y_test))
    acc = correct / len(y_test)
    assert acc >= 0.70, f"CSP-LDA accuracy {acc:.2%} < 70 %"


def test_fit_epochs_pipeline():
    """Full CSP fitting from raw synthetic epochs."""
    rng = np.random.RandomState(42)
    n_trials, channels, time_samples = 40, 8, 64
    # Simple two-class structure: left has high variance in first channel, right in last
    epochs_left = rng.randn(n_trials, channels, time_samples)
    epochs_left[:, 0, :] *= 4.0
    epochs_right = rng.randn(n_trials, channels, time_samples)
    epochs_right[:, -1, :] *= 4.0
    epochs = np.concatenate([epochs_left, epochs_right], axis=0)
    y = np.array([0] * n_trials + [1] * n_trials)

    clf = CSPLDAClassifier(
        class_labels=["motor_imagery_left", "motor_imagery_right"],
        n_components=4,
    )
    clf.fit_epochs(epochs, y)
    assert clf.is_fitted

    # predict_epoch should work
    result = clf.predict_epoch(epochs[0])
    assert result.label in ["motor_imagery_left", "motor_imagery_right"]


def test_unfitted_raises():
    clf = CSPLDAClassifier()
    with pytest.raises(RuntimeError):
        clf.predict(np.zeros(6))


def test_get_class_labels():
    clf = CSPLDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    assert clf.get_class_labels() == ["motor_imagery_left", "motor_imagery_right"]
