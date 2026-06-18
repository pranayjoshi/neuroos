"""Common Average Reference spatial filter."""

from __future__ import annotations

import numpy as np

from base_operator import SignalOperator


class CARFilter(SignalOperator):
    """Subtract the instantaneous mean across all channels."""

    def __init__(self) -> None:
        super().__init__()
        self._fitted = True

    @property
    def operator_name(self) -> str:
        return "car_filter"

    def fit(self, calibration_data: np.ndarray) -> None:
        self._fitted = True

    def process(self, signal: np.ndarray) -> np.ndarray:
        return self._timed_process(self._process_impl, signal)

    @staticmethod
    def _process_impl(signal: np.ndarray) -> np.ndarray:
        return signal - signal.mean(axis=0, keepdims=True)
