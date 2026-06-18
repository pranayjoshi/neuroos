"""
Entry point: python -m intent_engine

Reads FeatureVector JSONL from stdin, writes IntentEvent JSONL to stdout.

Subprocess communication protocol:
  - One JSON object per line on stdin (FeatureVector)
  - One JSON object per line on stdout (IntentEvent)
  - Empty lines are ignored
  - JSON parse errors are logged to stderr and skipped

Example (single shot):
    echo '{"vectorId":"...","bandPowers":{"alpha":[1,2,3],...},...}' |
        python -m intent_engine

Example (streaming):
    cat features.jsonl | python -m intent_engine > intents.jsonl
"""

from __future__ import annotations

import json
import sys

import numpy as np

from .classifiers.lda_classifier import LDAClassifier
from .engine import EngineConfig, IntentEngine
from .normalizer import IntentNormalizer


def _build_default_engine() -> IntentEngine:
    """
    Build a default IntentEngine pre-trained on a small synthetic dataset.

    The default classifier covers 2-class motor imagery. Real deployments
    should load a serialised classifier from disk (see model_store.py).
    """
    rng = np.random.RandomState(42)

    # Synthetic 6-feature (alpha+beta @ C3/Cz/C4) motor imagery training set
    # Left:  alpha/beta suppression at C4 (right hemisphere)
    # Right: alpha/beta suppression at C3 (left hemisphere)
    n_per_class = 60
    left_mean = np.array([1.5, 0.8, 0.5, 1.5, 0.8, 0.5])
    right_mean = np.array([0.5, 0.8, 1.5, 0.5, 0.8, 1.5])
    X_left = rng.randn(n_per_class, 6) * 0.3 + left_mean
    X_right = rng.randn(n_per_class, 6) * 0.3 + right_mean
    X = np.vstack([X_left, X_right])
    y = np.array([0] * n_per_class + [1] * n_per_class)

    clf = LDAClassifier(class_labels=["motor_imagery_left", "motor_imagery_right"])
    clf.fit(X, y)

    config = EngineConfig(
        classifier_type="lda",
        confidence_threshold=0.50,
    )
    normalizer = IntentNormalizer(alpha=0.01)
    return IntentEngine(classifier=clf, config=config, normalizer=normalizer)


def main() -> None:
    engine = _build_default_engine()

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            fv = json.loads(line)
        except json.JSONDecodeError as exc:
            print(f"[intent_engine] JSON parse error: {exc}", file=sys.stderr)
            continue

        try:
            event = engine.process(fv)
        except Exception as exc:
            print(f"[intent_engine] Classification error: {exc}", file=sys.stderr)
            continue

        if event is not None:
            sys.stdout.write(json.dumps(event) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
