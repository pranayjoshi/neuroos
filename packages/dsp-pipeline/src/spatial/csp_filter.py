"""Common Spatial Patterns (CSP) spatial filter."""

from __future__ import annotations

import numpy as np
from scipy.linalg import eigh

from base_operator import SignalOperator


class CSPFilter(SignalOperator):
    """
    Supervised spatial filter maximizing variance ratio between two classes.

    Solution via generalized eigenvalue decomposition:
        cov1 W = lambda (cov1 + cov2) W
    """

    def __init__(self, n_components: int = 6) -> None:
        super().__init__()
        self.n_components = n_components
        self._W: np.ndarray | None = None
        self._output_labels: list[str] = []

    @property
    def operator_name(self) -> str:
        return "csp_filter"

    @property
    def output_labels(self) -> list[str]:
        return self._output_labels

    def fit(self, calibration_data: np.ndarray) -> None:
        raise NotImplementedError("Use fit_classes with labeled trial data for CSP.")

    def fit_classes(
        self,
        class1_trials: np.ndarray,
        class2_trials: np.ndarray,
    ) -> None:
        """
        Fit CSP filters from labeled trials.

        class1_trials, class2_trials: [trials, channels, samples]
        """
        if class1_trials.ndim != 3 or class2_trials.ndim != 3:
            raise ValueError("trial arrays must be [trials, channels, samples]")

        cov1 = _average_covariance(class1_trials)
        cov2 = _average_covariance(class2_trials)
        eigenvalues, eigenvectors = eigh(cov1, cov1 + cov2)

        half = self.n_components // 2
        low_idx = np.arange(half)
        high_idx = np.arange(-half, 0)
        idx = np.concatenate([low_idx, high_idx])
        self._W = eigenvectors[:, idx]
        self._output_labels = [f"CSP{i + 1}" for i in range(self.n_components)]

    def process(self, signal: np.ndarray) -> np.ndarray:
        return self._timed_process(self._process_impl, signal)

    def _process_impl(self, signal: np.ndarray) -> np.ndarray:
        if self._W is None:
            return signal
        return self._W.T @ signal


def _average_covariance(trials: np.ndarray) -> np.ndarray:
    covs = [trial @ trial.T / trial.shape[1] for trial in trials]
    return np.mean(covs, axis=0)
