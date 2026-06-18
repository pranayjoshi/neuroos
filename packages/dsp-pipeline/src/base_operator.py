"""Abstract base class for all DSP signal operators."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

import numpy as np


class SignalOperator(ABC):
    """Transform input numpy arrays into output numpy arrays with timing instrumentation."""

    def __init__(self) -> None:
        self._last_process_ns: int = 0

    @abstractmethod
    def fit(self, calibration_data: np.ndarray) -> None:
        """Fit operator parameters from calibration data [channels, samples]."""

    @abstractmethod
    def process(self, signal: np.ndarray) -> np.ndarray:
        """Transform one frame [channels, samples_per_frame]."""

    @property
    @abstractmethod
    def operator_name(self) -> str: ...

    @property
    def last_process_ms(self) -> float:
        return self._last_process_ns / 1_000_000.0

    def _timed_process(self, func, signal: np.ndarray) -> np.ndarray:
        start = time.perf_counter_ns()
        result = func(signal)
        self._last_process_ns = time.perf_counter_ns() - start
        return result
