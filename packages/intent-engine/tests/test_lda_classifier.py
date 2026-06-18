"""
Tests for LDAClassifier.

Acceptance criteria:
  - fit/predict round-trip works.
  - ≥ 70 % accuracy on held-out motor imagery features.
  - predict() returns ClassificationResult with valid fields.
  - posteriors sum to 1.0.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.model_selection import train_test_split

from intent_engine.classifiers.lda_classifier import LDAClassifier
from intent_engine.classifiers.base_classifier import ClassificationResult

from .conftest import make_mi_dataset, FEATURE_DIM


def test_fit_predict_basic():
    X, y = make_mi_dataset(n_per_class=50, seed=0)
    clf = LDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    clf.fit(X, y)
    result = clf.predict(X[0])
    assert isinstance(result, ClassificationResult)
    assert result.label in ["motor_imagery_left", "motor_imagery_right"]
    assert 0.0 <= result.confidence <= 1.0


def test_posteriors_sum_to_one():
    X, y = make_mi_dataset(n_per_class=50, seed=1)
    clf = LDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    clf.fit(X, y)
    for x in X[:20]:
        result = clf.predict(x)
        total = sum(result.posteriors.values())
        assert abs(total - 1.0) < 1e-6, f"Posteriors sum to {total}"


def test_accuracy_geq_70_percent():
    """LDAClassifier must achieve ≥ 70 % on held-out MI features."""
    X, y = make_mi_dataset(n_per_class=100, noise_std=0.25, seed=7)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
    clf = LDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    clf.fit(X_train, y_train)

    labels_map = {"motor_imagery_left": 0, "motor_imagery_right": 1}
    correct = sum(
        labels_map[clf.predict(x).label] == yt
        for x, yt in zip(X_test, y_test)
    )
    accuracy = correct / len(y_test)
    assert accuracy >= 0.70, f"LDA accuracy {accuracy:.2%} < 70 %"


def test_unfitted_raises():
    clf = LDAClassifier()
    with pytest.raises(RuntimeError):
        clf.predict(np.zeros(FEATURE_DIM))


def test_get_class_labels():
    labels = ["motor_imagery_left", "motor_imagery_right"]
    clf = LDAClassifier(class_labels=labels)
    assert clf.get_class_labels() == labels


def test_feature_importance_returned():
    X, y = make_mi_dataset(seed=3)
    clf = LDAClassifier()
    clf.fit(X, y)
    result = clf.predict(X[0])
    assert isinstance(result.feature_importance, dict)


def test_save_load_roundtrip(tmp_path):
    X, y = make_mi_dataset(seed=5)
    clf = LDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    clf.fit(X, y)
    path = tmp_path / "lda.pkl"
    clf.save(str(path))
    clf2 = LDAClassifier()
    clf2.load(str(path))
    # Predictions should match
    for x in X[:10]:
        assert clf.predict(x).label == clf2.predict(x).label
