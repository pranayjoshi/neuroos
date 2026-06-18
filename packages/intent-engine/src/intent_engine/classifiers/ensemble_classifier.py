"""
Ensemble Classifier — weighted combination of multiple IntentClassifiers.

Each sub-classifier produces a posterior distribution over its own label set.
The ensemble merges them into a global posterior by:
  1. Expanding each sub-posterior to cover all global labels (0.0 for missing ones).
  2. Combining with per-classifier weights (weighted average).
  3. Re-normalising so posteriors sum to 1.

From context/classification_methods.md:
    combined[label] = lda_weight * p_lda + (1 - lda_weight) * p_nn
    total = sum(combined.values())
    combined = {k: v / total for k, v in combined.items()}
"""

from __future__ import annotations

import numpy as np

from .base_classifier import ClassificationResult, IntentClassifier


class EnsembleClassifier(IntentClassifier):
    """
    Weighted ensemble of IntentClassifier instances.

    Parameters
    ----------
    classifiers:
        List of fitted IntentClassifier objects.
    weights:
        Per-classifier weights (must be same length as classifiers).
        Will be normalised internally.  Defaults to uniform weights.
    global_labels:
        Ordered list of all possible IntentLabel strings.
        Defaults to the union of all sub-classifier label sets.
    """

    def __init__(
        self,
        classifiers: list[IntentClassifier],
        weights: list[float] | None = None,
        global_labels: list[str] | None = None,
    ) -> None:
        if not classifiers:
            raise ValueError("At least one classifier is required.")
        self._classifiers = classifiers
        raw_w = np.array(weights if weights is not None else [1.0] * len(classifiers), dtype=float)
        self._weights = raw_w / raw_w.sum()

        if global_labels is not None:
            self._global_labels = global_labels
        else:
            seen: dict[str, None] = {}
            for clf in classifiers:
                for lbl in clf.get_class_labels():
                    seen[lbl] = None
            self._global_labels = list(seen)

        self._fitted = all(getattr(clf, "is_fitted", True) for clf in classifiers)

    # ------------------------------------------------------------------
    # IntentClassifier interface
    # ------------------------------------------------------------------

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Fit all sub-classifiers on the same feature matrix.

        Note: this assumes all sub-classifiers share the same feature space.
        For heterogeneous ensembles, fit each sub-classifier individually before
        constructing the EnsembleClassifier.
        """
        for clf in self._classifiers:
            clf.fit(X, y)
        self._fitted = True

    def predict(self, features: np.ndarray) -> ClassificationResult:
        """Weighted ensemble prediction from a single feature vector."""
        combined: dict[str, float] = {lbl: 0.0 for lbl in self._global_labels}

        results = [clf.predict(features) for clf in self._classifiers]

        for weight, result in zip(self._weights, results):
            for lbl, prob in result.posteriors.items():
                if lbl in combined:
                    combined[lbl] += weight * prob
                # Labels not in global set are silently dropped

        total = sum(combined.values())
        if total > 0:
            combined = {k: v / total for k, v in combined.items()}
        else:
            n = len(combined)
            combined = {k: 1.0 / n for k in combined}

        best_label = max(combined, key=combined.__getitem__)

        merged_importance: dict[str, list[float]] = {}
        for result in results:
            for band, vals in result.feature_importance.items():
                if band not in merged_importance:
                    merged_importance[band] = list(vals)
                else:
                    merged_importance[band] = [
                        a + b for a, b in zip(merged_importance[band], vals)
                    ]

        return ClassificationResult(
            label=best_label,
            confidence=combined[best_label],
            posteriors=dict(combined),
            feature_importance=merged_importance,
        )

    def get_class_labels(self) -> list[str]:
        return list(self._global_labels)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def classifiers(self) -> list[IntentClassifier]:
        return self._classifiers

    @property
    def weights(self) -> np.ndarray:
        return self._weights.copy()

    def set_weights(self, weights: list[float]) -> None:
        raw = np.array(weights, dtype=float)
        self._weights = raw / raw.sum()

    @property
    def is_fitted(self) -> bool:
        return self._fitted
