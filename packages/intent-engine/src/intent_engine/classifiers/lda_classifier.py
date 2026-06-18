"""
LDA Classifier — fast linear discriminant analysis for motor imagery.

From BCI2000: "The first signal operator is a classifier that performs a linear
transformation (matrix multiplication of a classification matrix with the output
of the temporal filtering module)."

Implementation: sklearn LinearDiscriminantAnalysis with shrinkage='auto'
(Ledoit-Wolf regularisation) for robustness on small BCI training sets (~20 trials/class).

Feature vector layout (minimal, 6 features for 2-class MI):
    [alpha_C3, alpha_Cz, alpha_C4, beta_C3, beta_Cz, beta_C4]
"""

from __future__ import annotations

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

from .base_classifier import ClassificationResult, IntentClassifier

# Default labels for 2-class motor imagery
_MI_2CLASS = ["motor_imagery_left", "motor_imagery_right"]


class LDAClassifier(IntentClassifier):
    """
    Linear Discriminant Analysis classifier.

    Parameters
    ----------
    class_labels:
        Ordered list of IntentLabel strings, one per integer class (0-indexed).
        Defaults to left/right motor imagery for 2-class MI.
    solver:
        'svd' (no shrinkage) or 'eigen' (supports shrinkage).
    shrinkage:
        'auto' uses Ledoit-Wolf estimator; None disables shrinkage.
    """

    def __init__(
        self,
        class_labels: list[str] | None = None,
        solver: str = "eigen",
        shrinkage: str | None = "auto",
    ) -> None:
        self._class_labels: list[str] = list(class_labels or _MI_2CLASS)
        self._lda = LinearDiscriminantAnalysis(solver=solver, shrinkage=shrinkage)
        self._fitted = False

    # ------------------------------------------------------------------
    # IntentClassifier interface
    # ------------------------------------------------------------------

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Fit LDA on band-power feature matrix.

        X: [n_trials, n_features]
        y: [n_trials] integer class labels (0 → class_labels[0], etc.)
        """
        self._lda.fit(X.astype(np.float64), y)
        self._fitted = True

    def predict(self, features: np.ndarray) -> ClassificationResult:
        """Classify one [n_features] vector. Executes in <1 ms."""
        if not self._fitted:
            raise RuntimeError("LDAClassifier has not been fitted yet.")
        x = features.reshape(1, -1).astype(np.float64)
        proba = self._lda.predict_proba(x)[0]

        posteriors: dict[str, float] = {
            self._class_labels[int(cls)]: float(p)
            for cls, p in zip(self._lda.classes_, proba)
        }

        best_label = max(posteriors, key=posteriors.__getitem__)
        fi = self._feature_importance()

        return ClassificationResult(
            label=best_label,
            confidence=posteriors[best_label],
            posteriors=posteriors,
            feature_importance=fi,
        )

    def get_class_labels(self) -> list[str]:
        return list(self._class_labels)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _feature_importance(self) -> dict[str, list[float]]:
        if not hasattr(self._lda, "coef_") or self._lda.coef_ is None:
            return {}
        coef = self._lda.coef_
        weights = np.abs(coef[0] if coef.ndim > 1 else coef).tolist()
        return {"lda_weights": weights}

    # ------------------------------------------------------------------
    # Convenience / ONNX export handled via model_store
    # ------------------------------------------------------------------

    @property
    def sklearn_model(self) -> LinearDiscriminantAnalysis:
        """Expose the underlying sklearn model for ONNX export."""
        return self._lda

    @property
    def is_fitted(self) -> bool:
        return self._fitted
