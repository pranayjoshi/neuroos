"""
Tests for IntentNormalizer.

Acceptance criteria:
  - Output values lie in [0, 1].
  - Output values sum to 1.0 across all labels.
  - EMA adapts running statistics over repeated calls.
"""

from __future__ import annotations

import numpy as np
import pytest

from intent_engine.normalizer import IntentNormalizer


def _uniform_posteriors(labels: list[str]) -> dict[str, float]:
    n = len(labels)
    return {lbl: 1.0 / n for lbl in labels}


def test_output_in_unit_interval():
    norm = IntentNormalizer(alpha=0.05)
    labels = ["motor_imagery_left", "motor_imagery_right"]
    for _ in range(20):
        raw = {"motor_imagery_left": np.random.uniform(0, 1), "motor_imagery_right": np.random.uniform(0, 1)}
        out = norm.normalize(raw)
        for v in out.values():
            assert 0.0 <= v <= 1.0, f"Value {v} out of [0, 1]"


def test_posteriors_sum_to_one():
    norm = IntentNormalizer(alpha=0.01)
    labels = ["motor_imagery_left", "motor_imagery_right", "motor_imagery_rest", "idle"]
    rng = np.random.RandomState(0)
    for _ in range(50):
        raw_vals = rng.dirichlet(np.ones(len(labels))).tolist()
        raw = dict(zip(labels, raw_vals))
        out = norm.normalize(raw)
        total = sum(out.values())
        assert abs(total - 1.0) < 1e-9, f"Sum {total} ≠ 1"


def test_single_label_confidence():
    """Single-label posteriors → that label gets confidence 1.0."""
    norm = IntentNormalizer()
    out = norm.normalize({"motor_imagery_left": 1.0})
    assert abs(out["motor_imagery_left"] - 1.0) < 1e-9


def test_ema_adapts():
    """Running mean should shift toward injected value over many calls."""
    norm = IntentNormalizer(alpha=0.1)
    label = "motor_imagery_left"
    # Inject consistently high value → mean should climb
    for _ in range(100):
        norm.normalize({label: 0.9})
    mean_high = norm._mean[label]

    norm2 = IntentNormalizer(alpha=0.1)
    for _ in range(100):
        norm2.normalize({label: 0.1})
    mean_low = norm2._mean[label]

    assert mean_high > mean_low


def test_reset():
    norm = IntentNormalizer(alpha=0.1)
    for _ in range(50):
        norm.normalize({"a": 0.9, "b": 0.1})
    norm.reset()
    assert len(norm._mean) == 0


def test_invalid_alpha():
    with pytest.raises(ValueError):
        IntentNormalizer(alpha=0.0)

    with pytest.raises(ValueError):
        IntentNormalizer(alpha=1.5)
