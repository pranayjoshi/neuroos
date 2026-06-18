"""
Performance tests for IntentEngine.

Acceptance criteria (JOB.md):
  - Mean inference latency < 3 ms for LDA on 6-feature vector (1000 calls).
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from intent_engine.classifiers.lda_classifier import LDAClassifier

from .conftest import make_mi_dataset

N_WARMUP = 10
N_CALLS = 1000
LATENCY_BUDGET_MS = 3.0


@pytest.fixture(scope="module")
def trained_lda() -> LDAClassifier:
    X, y = make_mi_dataset(n_per_class=100, seed=0)
    clf = LDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    clf.fit(X, y)
    return clf


def test_lda_inference_latency(trained_lda):
    """Mean inference latency must be < 3 ms over 1000 calls."""
    rng = np.random.RandomState(42)
    vectors = [rng.randn(6).astype(np.float64) for _ in range(N_CALLS + N_WARMUP)]

    # Warm-up
    for v in vectors[:N_WARMUP]:
        trained_lda.predict(v)

    # Timed calls
    latencies_ms = []
    for v in vectors[N_WARMUP:]:
        t0 = time.perf_counter()
        trained_lda.predict(v)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    mean_ms = float(np.mean(latencies_ms))
    p99_ms = float(np.percentile(latencies_ms, 99))

    assert mean_ms < LATENCY_BUDGET_MS, (
        f"Mean LDA latency {mean_ms:.3f} ms exceeds budget of {LATENCY_BUDGET_MS} ms"
    )
    # Log for visibility (does not fail)
    print(f"\nLDA latency — mean: {mean_ms:.3f} ms, p99: {p99_ms:.3f} ms")


def test_engine_inference_latency():
    """End-to-end engine.process() should complete in < 10 ms (< 15 ms total budget)."""
    from intent_engine.engine import EngineConfig, IntentEngine
    from intent_engine.normalizer import IntentNormalizer
    from .conftest import make_feature_vector

    X, y = make_mi_dataset(n_per_class=100, seed=0)
    clf = LDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    clf.fit(X, y)
    engine = IntentEngine(
        classifier=clf,
        config=EngineConfig(confidence_threshold=0.5),
        normalizer=IntentNormalizer(),
    )

    fvs = [make_feature_vector("motor_imagery_left", seed=i) for i in range(N_CALLS + N_WARMUP)]

    # Warm-up
    for fv in fvs[:N_WARMUP]:
        engine.process(fv)

    latencies_ms = []
    for fv in fvs[N_WARMUP:]:
        t0 = time.perf_counter()
        engine.process(fv)
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)

    mean_ms = float(np.mean(latencies_ms))
    print(f"\nEngine latency — mean: {mean_ms:.3f} ms, p99: {float(np.percentile(latencies_ms, 99)):.3f} ms")
    # Engine latency budget is generous (includes normalizer EMA + dict building)
    assert mean_ms < 10.0, f"Engine mean latency {mean_ms:.3f} ms > 10 ms"
