"""
Confidence score calibration for IntentEngine outputs.

Implements the IntentNormalizer described in JOB.md:

  From BCI2000: "The second signal operator in the translation algorithm is a
  normalizer that performs a linear transformation on each output channel in
  order to create signals that have zero mean and a specific value range."

Pipeline per label:
  1. Z-score:   z = (raw_score - running_mean) / (running_std + ε)
  2. Sigmoid:   σ(z)  →  [0, 1]
  3. EMA update running statistics (adaptive baseline correction).
  4. Re-normalise the full posterior dict so probabilities sum to 1.0.
"""

from __future__ import annotations

import math
from collections import defaultdict


class IntentNormalizer:
    """
    EMA-based confidence normalizer with Platt-style sigmoid calibration.

    Parameters
    ----------
    alpha:
        EMA decay for running mean/variance. Smaller = slower adaptation.
        Range [0.001, 0.1] is typical; default 0.01 follows BCI2000 convention.
    eps:
        Small constant for numerical stability in std computation.
    """

    def __init__(
        self,
        alpha: float = 0.01,
        eps: float = 1e-6,
        init_mean: float = 0.5,
        init_var: float = 0.01,
    ) -> None:
        if not (0 < alpha <= 1):
            raise ValueError(f"alpha must be in (0, 1], got {alpha}")
        self._alpha = alpha
        self._eps = eps
        self._init_mean = init_mean
        self._init_var = init_var
        # Per-label running statistics.
        # mean initialised at 0.5 (centre of posterior space) and
        # var at 0.01 (std=0.1) so that high-confidence posteriors (>0.75)
        # produce z-scores > 2.5, mapping through sigmoid to >0.92.
        self._mean: dict[str, float] = defaultdict(lambda: init_mean)
        self._var: dict[str, float] = defaultdict(lambda: init_var)
        self._n_seen: dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def normalize(self, raw_posteriors: dict[str, float]) -> dict[str, float]:
        """
        Calibrate raw classifier posteriors into stable confidence scores.

        Steps
        -----
        1. Z-score each raw probability using per-label EMA statistics.
        2. Apply sigmoid to map ℝ → [0, 1].
        3. Update running statistics with the raw values.
        4. Re-normalise calibrated values so they sum to 1.0.

        Parameters
        ----------
        raw_posteriors:
            Dict of {intent_label: raw_probability}.

        Returns
        -------
        dict[str, float]
            Calibrated posteriors summing to 1.0, each in [0, 1].
        """
        calibrated: dict[str, float] = {}

        for label, raw in raw_posteriors.items():
            z = (raw - self._mean[label]) / (math.sqrt(self._var[label]) + self._eps)
            cal = self._sigmoid(z)
            calibrated[label] = cal
            self._update_stats(label, raw)

        # Re-normalise
        total = sum(calibrated.values())
        if total > 0:
            calibrated = {k: v / total for k, v in calibrated.items()}
        else:
            n = len(calibrated)
            calibrated = {k: 1.0 / n for k in calibrated}

        return calibrated

    def reset(self, labels: list[str] | None = None) -> None:
        """Reset running statistics (all labels or a specific subset)."""
        if labels is None:
            self._mean.clear()   # defaultdict will re-initialise on next access
            self._var.clear()
            self._n_seen.clear()
        else:
            for lbl in labels:
                self._mean.pop(lbl, None)
                self._var.pop(lbl, None)
                self._n_seen.pop(lbl, None)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_stats(self, label: str, raw: float) -> None:
        """Exponential moving average update of mean and variance."""
        alpha = self._alpha
        old_mean = self._mean[label]
        self._mean[label] += alpha * (raw - old_mean)
        self._var[label] = (1 - alpha) * (self._var[label] + alpha * (raw - old_mean) ** 2)
        self._n_seen[label] += 1

    @staticmethod
    def _sigmoid(z: float) -> float:
        """Numerically stable sigmoid."""
        if z >= 0:
            return 1.0 / (1.0 + math.exp(-z))
        e = math.exp(z)
        return e / (1.0 + e)
