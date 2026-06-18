"""Zero-phase FIR bandpass filter."""

from __future__ import annotations

import numpy as np
from scipy.signal import filtfilt, firwin

from base_operator import SignalOperator


class BandpassFIR(SignalOperator):
    """FIR bandpass filter using firwin + filtfilt (zero-phase)."""

    def __init__(
        self,
        low_hz: float,
        high_hz: float,
        sample_rate_hz: float,
        num_taps: int | None = None,
    ) -> None:
        super().__init__()
        self.low_hz = low_hz
        self.high_hz = high_hz
        self.sample_rate_hz = sample_rate_hz
        self.num_taps = num_taps
        self._coefficients: np.ndarray | None = None
        self._design_filter()

    @property
    def operator_name(self) -> str:
        return "bandpass_fir"

    def _design_filter(self) -> None:
        taps = self.num_taps
        if taps is None:
            taps = int(3 * self.sample_rate_hz / self.low_hz)
            if taps % 2 == 0:
                taps += 1
        nyquist = self.sample_rate_hz / 2.0
        self._coefficients = firwin(
            taps,
            [self.low_hz / nyquist, self.high_hz / nyquist],
            pass_zero=False,
        )

    def fit(self, calibration_data: np.ndarray) -> None:
        return

    def process(self, signal: np.ndarray) -> np.ndarray:
        return self._timed_process(self._process_impl, signal)

    def _process_impl(self, signal: np.ndarray) -> np.ndarray:
        if self._coefficients is None:
            raise RuntimeError("FIR coefficients not designed")
        if signal.shape[1] < len(self._coefficients):
            return signal.copy()
        return filtfilt(self._coefficients, [1.0], signal, axis=1)
