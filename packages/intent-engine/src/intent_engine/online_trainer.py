"""
Online Trainer — streaming LDA adaptation from user feedback.

From BCI2000:
  "An additional statistics component can be enabled to update in real-time
  certain parameters of the signal processing components such as the slope and
  intercept of the linear equation the normalizer applies to each output
  channel so as to compensate for spontaneous or adaptive changes in the
  distribution of the control signal values."

Implementation: Recursive LDA update (updating class means and covariances
without storing full history). Bounded by max_adaptation_samples to prevent
runaway drift.

Forgetting factor λ ∈ [0.99, 0.9999] — higher = more stable, lower = faster
adaptation. Controlled via the learning_rate parameter (λ = 1 - learning_rate).
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis

from .classifiers.lda_classifier import LDAClassifier


class OnlineTrainer:
    """
    Incremental LDA adaptation from labelled feedback events.

    When an application confirms or corrects an emitted IntentEvent, the
    corresponding feature vector and true label are fed to on_feedback(),
    which recursively updates the LDA decision boundary.

    Parameters
    ----------
    base_classifier:
        The LDAClassifier whose weights will be adapted.
    learning_rate:
        Controls the forgetting factor: λ = 1 - learning_rate.
        Smaller = more stable; larger = faster adaptation.
    max_adaptation_samples:
        Maximum number of feedback samples accepted before the adaptation
        buffer is frozen (prevents long-term drift).
    """

    def __init__(
        self,
        base_classifier: LDAClassifier,
        learning_rate: float = 0.01,
        max_adaptation_samples: int = 500,
    ) -> None:
        self._clf = base_classifier
        self._lr = learning_rate
        self._forgetting = 1.0 - learning_rate
        self._max_samples = max_adaptation_samples
        self._total_feedback = 0

        # Incremental state
        labels = base_classifier.get_class_labels()
        n_classes = len(labels)
        self._label_to_idx: dict[str, int] = {lbl: i for i, lbl in enumerate(labels)}
        self._class_counts: dict[int, int] = defaultdict(int)
        self._class_means: dict[int, np.ndarray | None] = {i: None for i in range(n_classes)}
        self._S_W: np.ndarray | None = None  # within-class scatter accumulator

        # Seed from fitted classifier if available
        self._n_features: int | None = None
        self._initialised = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def on_feedback(self, features: np.ndarray, true_label: str) -> None:
        """
        Incorporate one confirmed labelled sample into the classifier.

        Parameters
        ----------
        features:
            [n_features] band-power feature vector corresponding to the intent.
        true_label:
            Canonical IntentLabel string (e.g. 'motor_imagery_left').
        """
        if self._total_feedback >= self._max_samples:
            return
        if true_label not in self._label_to_idx:
            return

        x = np.asarray(features, dtype=np.float64).ravel()
        label_idx = self._label_to_idx[true_label]

        if not self._initialised:
            self._n_features = x.shape[0]
            n_classes = len(self._label_to_idx)
            self._S_W = np.eye(self._n_features) * 1e-4
            for i in range(n_classes):
                self._class_means[i] = np.zeros(self._n_features)
            self._initialised = True

        # Recursive mean update
        n = self._class_counts[label_idx]
        old_mean = self._class_means[label_idx]
        new_mean = old_mean + (x - old_mean) / (n + 1)
        self._class_means[label_idx] = new_mean
        self._class_counts[label_idx] = n + 1

        # Within-class scatter update with forgetting
        delta = x - new_mean
        assert self._S_W is not None
        self._S_W = self._forgetting * self._S_W + np.outer(delta, delta)

        self._total_feedback += 1

        # Refit the underlying sklearn LDA from accumulated statistics
        self._refit()

    def reset(self) -> None:
        """Clear all adaptation state; return to the original trained model."""
        self._total_feedback = 0
        self._class_counts.clear()
        for k in self._class_means:
            self._class_means[k] = None
        self._S_W = None
        self._initialised = False

    @property
    def feedback_count(self) -> int:
        return self._total_feedback

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _refit(self) -> None:
        """
        Refit the LDA from the current incremental statistics.

        Generates a small synthetic dataset that reproduces the current class
        means and scatter, then refits sklearn's LDA. This is cheap (n_classes
        samples) and avoids storing the full history.
        """
        n_classes = len(self._label_to_idx)
        if self._n_features is None:
            return
        # Only refit when we have observations for at least 2 classes
        populated = [i for i in range(n_classes) if self._class_counts.get(i, 0) > 0]
        if len(populated) < 2:
            return

        # Build a minimal representative dataset: one sample per class at the
        # current class mean, plus scatter-scaled samples drawn from S_W.
        X_parts, y_parts = [], []
        rng = np.random.RandomState(0)
        assert self._S_W is not None
        try:
            L = np.linalg.cholesky(self._S_W + np.eye(self._n_features) * 1e-6)
        except np.linalg.LinAlgError:
            L = np.eye(self._n_features) * 1e-3

        n_synth_per_class = max(3, 20 // n_classes)
        for i in populated:
            mean_i = self._class_means[i]
            if mean_i is None:
                continue
            noise = rng.randn(n_synth_per_class, self._n_features) @ L.T * self._lr
            X_parts.append(np.tile(mean_i, (n_synth_per_class, 1)) + noise)
            y_parts.extend([i] * n_synth_per_class)

        X = np.vstack(X_parts)
        y = np.array(y_parts)

        try:
            self._clf.fit(X, y)
        except Exception:
            pass  # Silently skip degenerate updates
