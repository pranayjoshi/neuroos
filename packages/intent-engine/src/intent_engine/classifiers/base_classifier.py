"""
Abstract base for all NeuroOS intent classifiers.

From BCI2000: "a translation algorithm translates signal features into control signals."
Classifiers are stateless at inference time — all state is in fit() output.
"""

from __future__ import annotations

import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class ClassificationResult:
    """Single-trial classification output."""

    label: str
    """Winning IntentLabel string (canonical, from intent_labels.ts)."""

    confidence: float
    """Posterior probability of the winning class, in [0, 1]."""

    posteriors: dict[str, float]
    """Full posterior distribution over all labels (sums to 1.0)."""

    feature_importance: dict[str, list[float]] = field(default_factory=dict)
    """Band → per-channel importance weights (interpretability)."""


# Canonical label set — must match jobs/00_shared_contracts/constants/intent_labels.ts exactly.
INTENT_LABELS: list[str] = [
    "motor_imagery_left",
    "motor_imagery_right",
    "motor_imagery_both_hands",
    "motor_imagery_feet",
    "motor_imagery_rest",
    "p300_target",
    "p300_non_target",
    "scp_positive",
    "scp_negative",
    "attention_high",
    "attention_low",
    "blink",
    "jaw_clench",
    "idle",
]


class IntentClassifier(ABC):
    """
    Abstract base for all NeuroOS intent classifiers.

    Subclasses must implement fit(), predict(), and get_class_labels().
    The predict() method MUST execute in <3 ms for real-time operation.
    """

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Train or fine-tune the classifier.

        Parameters
        ----------
        X:
            [n_trials, n_features] — flattened band-power feature vectors.
        y:
            [n_trials] — integer class labels mapping to get_class_labels() indices.
        """

    @abstractmethod
    def predict(self, features: np.ndarray) -> ClassificationResult:
        """
        Classify one feature vector. Must complete in <3 ms.

        Parameters
        ----------
        features:
            [n_features] — flattened from FeatureVector.
        """

    @abstractmethod
    def get_class_labels(self) -> list[str]:
        """Return the IntentLabel strings indexed by integer class label."""

    def save(self, path: str) -> None:
        """Pickle the classifier to disk."""
        with open(path, "wb") as fh:
            pickle.dump(self, fh)

    def load(self, path: str) -> None:
        """Load state from a pickled classifier."""
        with open(path, "rb") as fh:
            state = pickle.load(fh)
        self.__dict__.update(state.__dict__)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _uniform_posteriors(class_labels: list[str]) -> dict[str, float]:
        """Return a uniform prior over the given labels (sums to 1)."""
        p = 1.0 / len(class_labels)
        return {lbl: p for lbl in class_labels}

    @staticmethod
    def _softmax(logits: np.ndarray) -> np.ndarray:
        e = np.exp(logits - logits.max())
        return e / e.sum()
