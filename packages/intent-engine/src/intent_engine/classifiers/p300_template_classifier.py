"""
P300 Template Matching Classifier.

Detects P300 evoked potentials by Pearson correlation against a calibration
grand-average template stored at Pz (0–800 ms window).

From BCI2000: "The evoked responses are classified (by the associated signal
processing module), and the character that the system identifies as the desired
character is shown on the screen."

Expected accuracy: ≥80 % at SNR=10 dB (see acceptance criteria).
"""

from __future__ import annotations

import numpy as np
from scipy.stats import pearsonr

from .base_classifier import ClassificationResult, IntentClassifier

_P300_LABELS = ["p300_non_target", "p300_target"]


class P300Detector(IntentClassifier):
    """
    Template-matching P300 detector.

    Fits a grand-average P300 waveform from calibration target epochs at Pz,
    then classifies by Pearson correlation against that template.

    Parameters
    ----------
    threshold:
        Correlation threshold above which a trial is classified as *target*.
        Default 0.4 (from BCI2000 reference implementation).
    """

    def __init__(self, threshold: float = 0.4) -> None:
        self.threshold = threshold
        self._template: np.ndarray | None = None  # [time_samples]
        self._fitted = False

    # ------------------------------------------------------------------
    # IntentClassifier interface
    # ------------------------------------------------------------------

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Build P300 template from calibration epochs.

        Parameters
        ----------
        X:
            [n_epochs, time_samples] — single-channel (Pz) epoch matrix.
            Also accepts [n_epochs, 1, time_samples] (will be squeezed).
        y:
            [n_epochs] — binary labels: 1 = P300 target, 0 = non-target.
        """
        epochs = np.asarray(X, dtype=np.float64)
        if epochs.ndim == 3:
            epochs = epochs[:, 0, :]  # take first (Pz) channel
        labels = np.asarray(y)
        target_epochs = epochs[labels == 1]
        if len(target_epochs) == 0:
            raise ValueError("No target epochs provided; cannot build P300 template.")
        self._template = target_epochs.mean(axis=0)  # [time_samples]
        self._fitted = True

    def predict(self, features: np.ndarray) -> ClassificationResult:
        """
        Classify one [time_samples] evoked-response vector.

        Uses Pearson r against the stored template.
        confidence = (r + 1) / 2  →  maps [-1, 1] to [0, 1].
        """
        if not self._fitted or self._template is None:
            raise RuntimeError("P300Detector has not been fitted yet.")
        epoch = np.asarray(features, dtype=np.float64).ravel()
        tpl = self._template.ravel()
        # Truncate or pad to matching length
        min_len = min(len(epoch), len(tpl))
        r_val, _ = pearsonr(epoch[:min_len], tpl[:min_len])
        r_val = float(np.clip(r_val, -1.0, 1.0))

        confidence_target = (r_val + 1.0) / 2.0
        confidence_nontarget = 1.0 - confidence_target

        label = "p300_target" if r_val > self.threshold else "p300_non_target"
        posteriors = {
            "p300_target": confidence_target,
            "p300_non_target": confidence_nontarget,
        }

        return ClassificationResult(
            label=label,
            confidence=posteriors[label],
            posteriors=posteriors,
            feature_importance={},
        )

    def get_class_labels(self) -> list[str]:
        return list(_P300_LABELS)

    # ------------------------------------------------------------------
    # Template I/O
    # ------------------------------------------------------------------

    def save_template(self, path: str) -> None:
        """Save template to a .npy file."""
        if self._template is None:
            raise RuntimeError("No template to save.")
        np.save(path, self._template)

    def load_template(self, path: str) -> None:
        """Load template from a .npy file."""
        self._template = np.load(path)
        self._fitted = True

    @property
    def template(self) -> np.ndarray | None:
        return self._template

    @property
    def is_fitted(self) -> bool:
        return self._fitted
