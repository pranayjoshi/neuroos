"""
Tests for OnlineTrainer.

Acceptance criteria:
  - on_feedback() with correct labels for 50 trials improves accuracy by ≥ 5 %.
  - Trainer respects max_adaptation_samples.
  - reset() clears internal state.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.model_selection import train_test_split

from intent_engine.classifiers.lda_classifier import LDAClassifier
from intent_engine.online_trainer import OnlineTrainer

from .conftest import make_mi_dataset


def _accuracy(clf: LDAClassifier, X: np.ndarray, y: np.ndarray) -> float:
    label_map = {"motor_imagery_left": 0, "motor_imagery_right": 1}
    correct = sum(label_map.get(clf.predict(x).label, -1) == yt for x, yt in zip(X, y))
    return correct / len(y)


def test_feedback_improves_accuracy():
    """50 correct feedback samples must improve accuracy by ≥ 5 %."""
    # Use a HARD dataset: small separation between class means and high noise.
    # This ensures the initial classifier is mediocre (< 90 %) so that
    # feedback has meaningful room to improve accuracy.
    hard_left_mean = np.array([0.7, 0.5, 0.3, 0.7, 0.5, 0.3])
    hard_right_mean = np.array([0.3, 0.5, 0.7, 0.3, 0.5, 0.7])
    noise_hard = 0.5  # high noise → overlapping distributions

    rng_train = np.random.RandomState(1)
    # Very small initial training set → poor fit
    n_init = 6
    X_small = np.vstack([
        rng_train.randn(n_init, 6) * noise_hard + hard_left_mean,
        rng_train.randn(n_init, 6) * noise_hard + hard_right_mean,
    ])
    y_small = np.array([0] * n_init + [1] * n_init)

    # Test set with known difficulty
    rng_test = np.random.RandomState(777)
    n_test = 80
    X_test = np.vstack([
        rng_test.randn(n_test, 6) * noise_hard + hard_left_mean,
        rng_test.randn(n_test, 6) * noise_hard + hard_right_mean,
    ])
    y_test = np.array([0] * n_test + [1] * n_test)

    clf = LDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    clf.fit(X_small, y_small)
    acc_before = _accuracy(clf, X_test, y_test)

    trainer = OnlineTrainer(clf, learning_rate=0.15, max_adaptation_samples=500)

    # Feed 50 correctly labelled samples from a cleaner distribution
    rng_fb = np.random.RandomState(42)
    n_fb = 25
    X_feedback = np.vstack([
        rng_fb.randn(n_fb, 6) * 0.3 + hard_left_mean,
        rng_fb.randn(n_fb, 6) * 0.3 + hard_right_mean,
    ])
    y_feedback = np.array([0] * n_fb + [1] * n_fb)
    label_names = ["motor_imagery_left", "motor_imagery_right"]
    for x, yt in zip(X_feedback, y_feedback):
        trainer.on_feedback(x, label_names[yt])

    acc_after = _accuracy(clf, X_test, y_test)
    improvement = acc_after - acc_before

    assert improvement >= 0.05, (
        f"Accuracy before {acc_before:.2%}, after {acc_after:.2%}; "
        f"improvement {improvement:.2%} < 5 %"
    )


def test_max_adaptation_samples_respected():
    X, y = make_mi_dataset(seed=2)
    clf = LDAClassifier()
    clf.fit(X, y)
    trainer = OnlineTrainer(clf, max_adaptation_samples=10)
    label_names = ["motor_imagery_left", "motor_imagery_right"]
    for x, yt in zip(X[:50], y[:50]):
        trainer.on_feedback(x, label_names[yt])
    assert trainer.feedback_count == 10


def test_unknown_label_ignored():
    X, y = make_mi_dataset(seed=3)
    clf = LDAClassifier()
    clf.fit(X, y)
    trainer = OnlineTrainer(clf)
    trainer.on_feedback(X[0], "unknown_label_xyz")
    assert trainer.feedback_count == 0


def test_reset():
    X, y = make_mi_dataset(seed=4)
    clf = LDAClassifier()
    clf.fit(X, y)
    trainer = OnlineTrainer(clf)
    label_names = ["motor_imagery_left", "motor_imagery_right"]
    for x, yt in zip(X[:10], y[:10]):
        trainer.on_feedback(x, label_names[yt])
    assert trainer.feedback_count == 10
    trainer.reset()
    assert trainer.feedback_count == 0
    assert not trainer._initialised
