"""
CSP + LDA Classifier for 2-class motor imagery.

Pipeline:
  1. (Calibration) Fit CSP spatial filters W from per-class epochs.
  2. Project epochs: W^T @ epoch  →  [n_components, time_samples]
  3. Compute log-normalised variance: log(var / sum(var))  →  [n_components]
  4. Fit LDA on log-variance features.

In production the DSP pipeline (Job 02) applies the pre-computed W and emits
spatialFeatures (the log-variance vector) in the FeatureVector. The engine
then calls predict(spatial_features) on this classifier.

Typical accuracy: 75–92 % (2-class MI) per BCI literature.
"""

from __future__ import annotations

import numpy as np
import scipy.linalg
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

from .base_classifier import ClassificationResult, IntentClassifier

_MI_2CLASS = ["motor_imagery_left", "motor_imagery_right"]


class _CSPFilter:
    """
    Common Spatial Patterns spatial filter.

    Solves the generalised eigenvalue problem:
        Σ_left w = λ (Σ_left + Σ_right) w

    Selects first and last n_components//2 eigenvectors (max-variance components
    for each class).
    """

    def __init__(self, n_components: int = 6) -> None:
        self.n_components = n_components
        self.W: np.ndarray | None = None  # [channels, n_components]

    def fit(self, epochs_a: np.ndarray, epochs_b: np.ndarray) -> None:
        """
        Fit CSP filters from two classes.

        Parameters
        ----------
        epochs_a, epochs_b:
            [n_trials, channels, time_samples] raw epoch arrays.
        """
        cov_a = self._mean_cov(epochs_a)
        cov_b = self._mean_cov(epochs_b)
        # Solve: cov_a w = λ (cov_a + cov_b) w
        eigenvalues, eigenvectors = scipy.linalg.eigh(cov_a, cov_a + cov_b)
        idx = np.argsort(eigenvalues)[::-1]
        eigenvectors = eigenvectors[:, idx]
        half = self.n_components // 2
        kept = list(range(half)) + list(range(-half, 0))
        self.W = eigenvectors[:, kept]  # [channels, n_components]

    def transform(self, epoch: np.ndarray) -> np.ndarray:
        """
        Extract log-normalised variance features from one epoch.

        Parameters
        ----------
        epoch:
            [channels, time_samples]

        Returns
        -------
        np.ndarray:
            [n_components] log-variance features.
        """
        if self.W is None:
            raise RuntimeError("CSPFilter not fitted.")
        projected = self.W.T @ epoch  # [n_components, time_samples]
        variances = np.var(projected, axis=1)  # [n_components]
        return np.log(variances / (variances.sum() + 1e-10))

    def transform_batch(self, epochs: np.ndarray) -> np.ndarray:
        """
        Transform a batch of epochs.

        Parameters
        ----------
        epochs:
            [n_trials, channels, time_samples]

        Returns
        -------
        np.ndarray:
            [n_trials, n_components]
        """
        return np.stack([self.transform(ep) for ep in epochs])

    # ------------------------------------------------------------------
    @staticmethod
    def _mean_cov(epochs: np.ndarray) -> np.ndarray:
        """Compute trial-averaged normalised covariance matrix."""
        covs = []
        for ep in epochs:
            # ep: [channels, time_samples]
            c = ep @ ep.T  # [channels, channels]
            covs.append(c / (np.trace(c) + 1e-10))
        return np.mean(covs, axis=0)


class CSPLDAClassifier(IntentClassifier):
    """
    CSP spatial filter + LDA pipeline for motor imagery classification.

    Two fitting modes:
    - ``fit_epochs(epochs, y)``: full CSP + LDA training from raw epochs.
    - ``fit(X, y)``: LDA-only fitting when CSP features are pre-extracted.
      Use this when the DSP pipeline already outputs log-variance features
      (FeatureVector.spatialFeatures).
    """

    def __init__(
        self,
        class_labels: list[str] | None = None,
        n_components: int = 6,
    ) -> None:
        self._class_labels: list[str] = list(class_labels or _MI_2CLASS)
        self._csp = _CSPFilter(n_components=n_components)
        self._lda = LinearDiscriminantAnalysis(solver="eigen", shrinkage="auto")
        self._fitted = False
        self._csp_fitted = False

    # ------------------------------------------------------------------
    # IntentClassifier interface
    # ------------------------------------------------------------------

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Fit LDA on pre-extracted CSP log-variance features.

        X: [n_trials, n_csp_components]
        y: [n_trials] integer class labels
        """
        self._lda.fit(X.astype(np.float64), y)
        self._fitted = True

    def predict(self, features: np.ndarray) -> ClassificationResult:
        """
        Classify using pre-extracted CSP features (from spatialFeatures).

        features: [n_components] log-variance vector
        """
        if not self._fitted:
            raise RuntimeError("CSPLDAClassifier has not been fitted yet.")
        x = features.reshape(1, -1).astype(np.float64)
        proba = self._lda.predict_proba(x)[0]

        posteriors: dict[str, float] = {
            self._class_labels[int(cls)]: float(p)
            for cls, p in zip(self._lda.classes_, proba)
        }
        best_label = max(posteriors, key=posteriors.__getitem__)

        return ClassificationResult(
            label=best_label,
            confidence=posteriors[best_label],
            posteriors=posteriors,
            feature_importance={},
        )

    def get_class_labels(self) -> list[str]:
        return list(self._class_labels)

    # ------------------------------------------------------------------
    # Extended API for calibration sessions
    # ------------------------------------------------------------------

    def fit_epochs(self, epochs: np.ndarray, y: np.ndarray) -> None:
        """
        Full CSP + LDA fitting from raw epochs.

        Parameters
        ----------
        epochs:
            [n_trials, channels, time_samples]
        y:
            [n_trials] integer class labels (exactly 2 classes supported).
        """
        classes = np.unique(y)
        if len(classes) != 2:
            raise ValueError("CSP requires exactly 2 classes.")
        epochs_a = epochs[y == classes[0]]
        epochs_b = epochs[y == classes[1]]
        self._csp.fit(epochs_a, epochs_b)
        self._csp_fitted = True
        X_csp = self._csp.transform_batch(epochs)
        self.fit(X_csp, y)

    def predict_epoch(self, epoch: np.ndarray) -> ClassificationResult:
        """
        Classify from a raw [channels, time_samples] epoch using fitted CSP.
        """
        if not self._csp_fitted:
            raise RuntimeError("CSP filter not fitted. Call fit_epochs() first.")
        features = self._csp.transform(epoch)
        return self.predict(features)

    @property
    def csp_filter(self) -> _CSPFilter:
        return self._csp

    @property
    def sklearn_model(self) -> LinearDiscriminantAnalysis:
        return self._lda

    @property
    def is_fitted(self) -> bool:
        return self._fitted
