"""Stage 1: A/D units to microvolts with DC baseline correction."""

from __future__ import annotations

import numpy as np

from base_operator import SignalOperator
from utils.ring_buffer import RingBuffer


class Calibrator(SignalOperator):
    """
    Convert raw A/D integer values to microvolts and subtract per-channel DC baseline.

    When input is already calibrated (μV), only baseline correction is applied.
    """

    def __init__(
        self,
        gain_uv_per_unit: float = 0.022351744781086523,
        offset_uv: float = 0.0,
        baseline_window_sec: float = 0.5,
    ) -> None:
        super().__init__()
        self.gain_uv_per_unit = gain_uv_per_unit
        self.offset_uv = offset_uv
        self.baseline_window_sec = baseline_window_sec
        self._baseline_buffer: RingBuffer | None = None
        self._sample_rate_hz: float | None = None
        self._fitted = False

    @property
    def operator_name(self) -> str:
        return "calibrator"

    def fit(self, calibration_data: np.ndarray) -> None:
        if calibration_data.ndim != 2:
            raise ValueError("calibration_data must be [channels, samples]")
        self._fitted = True

    def configure(self, sample_rate_hz: float, num_channels: int) -> None:
        capacity = max(1, int(self.baseline_window_sec * sample_rate_hz))
        if (
            self._baseline_buffer is None
            or self._baseline_buffer.capacity != capacity
            or self._baseline_buffer._num_channels != num_channels
        ):
            self._baseline_buffer = RingBuffer(capacity, num_channels)
        self._sample_rate_hz = sample_rate_hz

    def process(self, signal: np.ndarray, *, already_calibrated: bool = False) -> np.ndarray:
        return self._timed_process(
            lambda x: self._process_impl(x, already_calibrated=already_calibrated),
            signal,
        )

    def _process_impl(self, signal: np.ndarray, *, already_calibrated: bool) -> np.ndarray:
        if signal.ndim != 2:
            raise ValueError("signal must be [channels, samples]")

        if already_calibrated:
            output = signal.astype(np.float64, copy=True)
        else:
            output = signal.astype(np.float64) * self.gain_uv_per_unit + self.offset_uv

        if self._baseline_buffer is not None:
            self._baseline_buffer.append(output)
            window = self._baseline_buffer.get_window()
            baseline = window.mean(axis=1, keepdims=True)
            output -= baseline

        return output
